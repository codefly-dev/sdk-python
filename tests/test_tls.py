"""CertificateReloader serves the leaf on disk now, proven through real TLS handshakes."""

import itertools
import os
import shutil
import socket
import ssl
import subprocess
import threading
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

import pytest

from codefly_sdk import CertificateReloader
from codefly_sdk.tls import CertificateReloader as ReloaderFromModule

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None,
                                reason="the tests mint certificate pairs with the openssl CLI")

GARBAGE = b"-----BEGIN CERTIFICATE-----\nnot a certificate\n-----END CERTIFICATE-----\n"

# Distinct modification times, a second apart. A filesystem with coarse
# timestamps could stamp two writes in one tick alike; the projection this
# mirrors writes a fresh file minutes apart, so pin the mtime instead of sleeping.
_mtimes = itertools.count(1_700_000_000_000_000_000, 1_000_000_000)


def install(path: Path, data: bytes) -> None:
    """Replace path atomically with data, as a Secret projection swaps in a fresh file."""
    staged = path.with_name(path.name + ".staged")
    staged.write_bytes(data)
    os.replace(staged, path)
    stamp = next(_mtimes)
    os.utime(path, ns=(stamp, stamp))


class Pair(NamedTuple):
    """A minted self-signed pair and the identity a client sees it served as."""
    cert: bytes
    key: bytes
    der: bytes
    serial: int

    @property
    def identity(self) -> Tuple[bytes, int]:
        return self.der, self.serial


def mint(directory: Path, name: str) -> Pair:
    """Mint a self-signed pair valid for localhost and 127.0.0.1."""
    cert, key = directory / f"{name}.crt", directory / f"{name}.key"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                    "-nodes", "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", f"/CN={name}",
                    "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                   check=True, capture_output=True)
    serial = subprocess.run(["openssl", "x509", "-in", str(cert), "-noout", "-serial"],
                            check=True, capture_output=True, text=True).stdout
    return Pair(cert.read_bytes(), key.read_bytes(),
                ssl.PEM_cert_to_DER_cert(cert.read_text()), int(serial.split("=", 1)[1], 16))


class Mount:
    """The projected cert/key files a service is handed, plus a trust bundle for its clients."""

    def __init__(self, directory: Path, initial: Pair, *trusted: Pair):
        directory.mkdir()
        self.cert, self.key = directory / "tls.crt", directory / "tls.key"
        self.trust = directory / "trust.pem"
        self.trust.write_bytes(b"".join(pair.cert for pair in trusted))
        self.rotate(initial)

    def rotate(self, pair: Pair) -> None:
        install(self.cert, pair.cert)
        install(self.key, pair.key)


class EchoServer:
    """A threaded TLS echo server wrapped once with the context under test, as a real listener is."""

    def __init__(self, context: ssl.SSLContext):
        self.context = context
        self.errors: List[BaseException] = []
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(0.05)
        self.port = self._listener.getsockname()[1]
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []

    def __enter__(self) -> "EchoServer":
        self._threads.append(threading.Thread(target=self._accept_loop, daemon=True))
        self._threads[0].start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(5)
        self._listener.close()

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._listener.accept()
            except TimeoutError:
                continue
            thread = threading.Thread(target=self._serve, args=(conn,), daemon=True)
            self._threads.append(thread)
            thread.start()

    def _serve(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(5)
            try:
                with self.context.wrap_socket(conn, server_side=True) as tls:
                    tls.sendall(tls.recv(64))
            except BaseException as error:  # a handshake failure is the finding, not a crash
                self.errors.append(error)


def handshake(port: int, trust: Path, server_hostname: Optional[str] = None,
              alpn: Optional[List[str]] = None) -> Tuple[bytes, int]:
    """Complete a TLS 1.3 handshake and an echo, and return the served leaf's DER and serial.

    The echo keeps the connection open until the server has written its
    session tickets; a client that closes straight after the handshake would
    make the server's ticket write fail and report a false handshake error.
    """
    context = ssl.create_default_context(cafile=str(trust))
    if server_hostname is None:
        context.check_hostname = False  # no SNI, as a peer addressed by IP sends none
    if alpn is not None:
        context.set_alpn_protocols(alpn)
    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname=server_hostname) as tls:
            tls.sendall(b"hello")
            assert tls.recv(64) == b"hello"
            assert tls.version() == "TLSv1.3"
            if alpn is not None:
                assert tls.selected_alpn_protocol() == alpn[0]
            return tls.getpeercert(binary_form=True), int(tls.getpeercert()["serialNumber"], 16)


def test_is_exported_from_the_package():
    assert CertificateReloader is ReloaderFromModule


def test_construction_fails_closed_without_a_valid_pair(tmp_path):
    with pytest.raises(FileNotFoundError):
        CertificateReloader(tmp_path / "missing.crt", tmp_path / "missing.key")

    one, two = mint(tmp_path, "one"), mint(tmp_path, "two")
    mount = Mount(tmp_path / "live", one)
    install(mount.cert, GARBAGE)
    with pytest.raises(ssl.SSLError):
        CertificateReloader(mount.cert, mount.key)

    install(mount.cert, one.cert)
    install(mount.key, two.key)
    with pytest.raises(ssl.SSLError):
        CertificateReloader(mount.cert, mount.key)


def test_rotation_is_served_on_the_next_handshake(tmp_path):
    one, two = mint(tmp_path, "one"), mint(tmp_path, "two")
    assert one.serial != two.serial
    mount = Mount(tmp_path / "live", one, one, two)
    reloader = CertificateReloader(mount.cert, mount.key)

    with EchoServer(reloader.server_context()) as server:
        assert handshake(server.port, mount.trust) == one.identity
        assert handshake(server.port, mount.trust, server_hostname="localhost") == one.identity

        # The issuer rotates the leaf: both files swapped, the next handshake serves it.
        mount.rotate(two)
        assert handshake(server.port, mount.trust) == two.identity
        assert handshake(server.port, mount.trust, server_hostname="localhost") == two.identity

        # A malformed replacement certificate is rejected; the last good leaf keeps serving.
        install(mount.cert, GARBAGE)
        assert handshake(server.port, mount.trust) == two.identity

        # A half-written key is rejected the same way.
        install(mount.cert, two.cert)
        install(mount.key, two.key[: len(two.key) // 2])
        assert handshake(server.port, mount.trust) == two.identity

        # The files settle back to the pair already loaded: fresh mtimes, same
        # bytes, so nothing is rebuilt and the context in service is unchanged.
        in_service = reloader.current()
        mount.rotate(two)
        assert reloader.refresh() is False
        assert reloader.current() is in_service
        assert handshake(server.port, mount.trust) == two.identity

    assert server.errors == []


def test_refresh_reads_the_files_only_when_their_stat_changed(tmp_path, monkeypatch):
    one, two = mint(tmp_path, "one"), mint(tmp_path, "two")
    mount = Mount(tmp_path / "live", one)
    reloader = CertificateReloader(mount.cert, mount.key)
    in_service = reloader.current()

    def not_expected(self):
        pytest.fail("read the files although their mtime and size were unchanged")

    monkeypatch.setattr(CertificateReloader, "_read", not_expected)
    assert reloader.refresh() is False
    assert reloader.current() is in_service

    monkeypatch.undo()
    mount.rotate(two)
    assert reloader.refresh() is True
    assert reloader.current() is not in_service
    assert reloader.refresh() is False


def test_configure_is_applied_to_every_context_built(tmp_path):
    one, two = mint(tmp_path, "one"), mint(tmp_path, "two")
    mount = Mount(tmp_path / "live", one, one, two)
    reloader = CertificateReloader(mount.cert, mount.key,
                                   configure=lambda context: context.set_alpn_protocols(["echo/1"]))
    with EchoServer(reloader.server_context()) as server:
        assert handshake(server.port, mount.trust, alpn=["echo/1"]) == one.identity
        mount.rotate(two)
        assert handshake(server.port, mount.trust, alpn=["echo/1"]) == two.identity
    assert server.errors == []


def test_concurrent_handshakes_across_a_rotation_all_complete(tmp_path):
    one, two = mint(tmp_path, "one"), mint(tmp_path, "two")
    mount = Mount(tmp_path / "live", one, one, two)
    reloader = CertificateReloader(mount.cert, mount.key)
    seen: List[Tuple[bytes, int]] = []
    failures: List[BaseException] = []

    def client() -> None:
        for _ in range(8):
            try:
                seen.append(handshake(server.port, mount.trust))
            except BaseException as error:
                failures.append(error)

    with EchoServer(reloader.server_context()) as server:
        clients = [threading.Thread(target=client) for _ in range(4)]
        for thread in clients:
            thread.start()
        mount.rotate(two)
        for thread in clients:
            thread.join(30)
        assert handshake(server.port, mount.trust) == two.identity

    assert failures == []
    assert server.errors == []
    assert len(seen) == 32
    assert set(seen) <= {one.identity, two.identity}
