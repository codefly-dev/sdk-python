"""Serve a rotated TLS leaf without a process restart.

A service that terminates TLS is handed a certificate/key pair as files
projected into its container, for example a cert-manager Certificate written
to a Kubernetes Secret. The usual pattern loads that pair once at startup into
an :class:`ssl.SSLContext` and presents the boot-time leaf for the life of the
process. Short-lived workload leaves are rotated well before expiry, so the
files on disk are fresh while the running process keeps presenting the stale
leaf; once that leaf expires every handshake fails even though a valid
certificate is already mounted. Issuance signals stay green throughout, because
the issuer did its job. Only the served certificate is stale.

:class:`CertificateReloader` re-reads the mounted files when their content
changes, rebuilds the context from the new pair and hands it to the next
handshake. A malformed or half-written replacement is rejected and the last
good context keeps serving, so a rotation in progress never fails a handshake
the process could otherwise complete.

This is the Python counterpart of sdk-go's ``CertificateReloader``. Go serves
the fresh leaf through ``tls.Config.GetCertificate``, a callback consulted on
every handshake. Python cannot swap the certificate inside an existing
:class:`ssl.SSLContext`, so the equivalent seam is the context's
``sni_callback``: it runs on every handshake before the certificate is
selected, whether or not the client sent a server name, and may point the
connection at a different context. The reloader installs one that swaps in the
context built from the pair on disk now.
"""

import os
import ssl
import threading
from typing import Callable, NamedTuple, Optional, Tuple, Union

PathLike = Union[str, "os.PathLike[str]"]

Signature = Tuple[int, int, int, int]
"""Modification time (ns) and size of the certificate file, then of the key file."""


class _Loaded(NamedTuple):
    """The context in service and what it was built from, swapped as one immutable value."""
    context: ssl.SSLContext
    signature: Signature
    cert: bytes
    key: bytes


class CertificateReloader:
    """Serve the pair mounted at ``cert_file`` and ``key_file``, reloaded in-process on rotation.

    Construction loads the pair once and raises on failure: a listener must
    never come up without a valid leaf. From then on every handshake refreshes
    first, so the leaf on disk now is the leaf served, and any failure to read
    or parse a replacement keeps the last good context serving.

    ``min_version`` is the protocol floor of every context built, TLS 1.3 by
    default. ``configure`` is applied to every context built, initially and on
    each rotation, and is where the caller sets anything else the listener
    needs, such as client-certificate verification or ALPN. Configure the
    context there rather than on the one :meth:`server_context` returns: a
    rotation replaces that context for the connection being handshaken, and a
    setting applied to the returned context alone would not follow.

    Thread-safe: the loaded state is one immutable value swapped atomically,
    and refreshes are serialised so concurrent handshakes share one rebuild.

    A client-side counterpart, sdk-go's ``GetClientCertificate``, would hand
    :meth:`current` to each outbound connection as it is wrapped; it is out of
    scope here.
    """

    def __init__(self, cert_file: PathLike, key_file: PathLike, *,
                 min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3,
                 configure: Optional[Callable[[ssl.SSLContext], None]] = None) -> None:
        self._cert_file = os.fspath(cert_file)
        self._key_file = os.fspath(key_file)
        self._min_version = min_version
        self._configure = configure
        self._refresh_lock = threading.Lock()
        signature = self._signature()
        cert, key = self._read()
        self._loaded = _Loaded(self._build_context(), signature, cert, key)

    def server_context(self) -> ssl.SSLContext:
        """Return the :class:`ssl.SSLContext` to wrap a listening socket with.

        This is the Python equivalent of sdk-go's ``tls.Config.GetCertificate``.
        Python cannot replace the certificate inside a context, so the returned
        context's ``sni_callback``, which OpenSSL invokes on every handshake
        whether or not the client sent a server name, swaps the connection's
        context for the one holding the pair on disk now. The returned context
        also carries the pair itself, so a handshake never depends on the
        callback having run, and one context can wrap the listener for the life
        of the process.
        """
        return self.current()

    def current(self) -> ssl.SSLContext:
        """Return the context a handshake would serve now, refreshing first."""
        self.refresh()
        return self._loaded.context

    def refresh(self) -> bool:
        """Re-read the mounted pair if it changed; True when a new context was installed.

        The common path is a stat of both files compared with the signature
        the current context was built from. ``os.stat`` follows the symlink
        swap a Kubernetes projected Secret performs on update, so a rotation is
        observed. Only a changed signature reads the files, and only changed
        bytes rebuild the context: a touch or an identical re-projection keeps
        the context and remembers the new signature. Any stat, read or parse
        failure (``ssl.SSLError`` is an ``OSError``) keeps the last good
        context, and a half-written replacement is picked up on a later
        handshake once both files settle.
        """
        with self._refresh_lock:
            loaded = self._loaded
            try:
                signature = self._signature()
                if signature == loaded.signature:
                    return False
                cert, key = self._read()
                if (cert, key) == (loaded.cert, loaded.key):
                    self._loaded = loaded._replace(signature=signature)
                    return False
                context = self._build_context()
            except OSError:
                return False
            self._loaded = _Loaded(context, signature, cert, key)
            return True

    def _sni_callback(self, ssl_object: ssl.SSLObject, server_name: Optional[str],
                      context: ssl.SSLContext) -> None:
        # Runs on every handshake before OpenSSL selects the certificate;
        # server_name is None when the client sent no SNI, as a peer addressed
        # by IP does. Returning None lets the handshake continue.
        ssl_object.context = self.current()
        return None

    def _build_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = self._min_version
        context.load_cert_chain(self._cert_file, self._key_file)
        if self._configure is not None:
            self._configure(context)
        context.sni_callback = self._sni_callback
        return context

    def _signature(self) -> Signature:
        cert, key = os.stat(self._cert_file), os.stat(self._key_file)
        return cert.st_mtime_ns, cert.st_size, key.st_mtime_ns, key.st_size

    def _read(self) -> Tuple[bytes, bytes]:
        with open(self._cert_file, "rb") as cert, open(self._key_file, "rb") as key:
            return cert.read(), key.read()
