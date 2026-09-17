"""Fixture principals declared by the module packages a workspace composes."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel

FIXTURE = "CODEFLY__FIXTURE"
WORKSPACE_CONFIGURATION_NAME = "workspace.codefly.yaml"
LOCAL_OVERLAY_CONFIGURATION_NAME = "codefly.local.yaml"
PACKAGE_MANIFEST_NAME = "module.package.codefly.yaml"


class FixtureError(Exception):
    """A fixture cannot be resolved against the composed packages."""


class UnknownFixtureError(FixtureError):
    """No composed package declares the selected fixture."""


class UnknownPrincipalError(FixtureError):
    """The fixture seeds no principal for the requested role."""


class FixtureCollisionError(FixtureError):
    """Two composed packages declare the same fixture name."""


class FixturePrincipal(BaseModel):
    """One identity a fixture seeds.

    The role is the lookup key, unique within the fixture, and the token is the
    credential a test presents to authenticate as this principal.
    """
    id: str
    email: str
    role: str
    token: str


class ProvidedFixture(BaseModel):
    """One named seed a module package ships, with the principals it creates."""
    name: str
    description: Optional[str] = None
    principals: List[FixturePrincipal] = []

    def principal(self, role: str) -> FixturePrincipal:
        """Return the identity this fixture seeds for role."""
        seeded = []
        for principal in self.principals:
            if principal.role == role:
                return principal
            seeded.append(principal.role)
        if not seeded:
            raise UnknownPrincipalError(
                f'module fixture seeds no principal for the role: fixture "{self.name}" seeds no principals')
        raise UnknownPrincipalError(
            f'module fixture seeds no principal for the role: fixture "{self.name}" has no "{role}" principal '
            f'(seeded roles: {", ".join(seeded)})')


class FixtureSelection(str):
    """The fixture the Codefly runtime selected for this process."""

    def principal(self, role: str) -> FixturePrincipal:
        """Return the identity the selected fixture seeds for role.

        Resolving by role means a renamed or dropped principal fails here,
        against the package version the solution composed, rather than at login.
        """
        name = self.strip()
        if not name:
            raise FixtureError("resolve fixture principal: no fixture is selected")
        manifests, unresolved = _composed_packages()
        return _resolve_fixture(name, manifests, unresolved).principal(role)


def fixture() -> FixtureSelection:
    """Return the fixture selected by the Codefly runtime.

    Product code must not depend on the runtime's environment-variable
    representation.
    """
    return FixtureSelection(os.getenv(FIXTURE, ""))


class _PackageManifest(BaseModel):
    id: str
    fixtures: List[ProvidedFixture] = []


def _resolve_fixture(name: str, manifests: List[_PackageManifest],
                     unresolved: List[str]) -> ProvidedFixture:
    fixtures = _fixtures(manifests)
    available = []
    for provided in fixtures:
        if provided.name == name:
            return provided
        available.append(provided.name)
    if available:
        message = (f'module fixture is not declared by any composed package: "{name}" '
                   f'(available: {", ".join(available)})')
    else:
        message = (f'module fixture is not declared by any composed package: "{name}", '
                   f'and the composed packages declare no fixtures')
    # A module that resolves to a pinned artifact or to a checkout the Codefly
    # CLI materializes is absent from what we could read. Saying only that the
    # name is unknown would point at the fixture rather than at that package.
    if unresolved:
        message += (f'; modules ({", ".join(unresolved)}) do not resolve to a local package directory here '
                    f'and were not read')
    raise UnknownFixtureError(message)


def _fixtures(manifests: List[_PackageManifest]) -> List[ProvidedFixture]:
    """Return the fixtures the composed packages declare, sorted by name.

    Two packages declaring the same name collide: a fixture selection would no
    longer name one seed.
    """
    fixtures = []
    owners: Dict[str, str] = {}
    for manifest in manifests:
        for provided in manifest.fixtures:
            if provided.name in owners:
                raise FixtureCollisionError(
                    f'module composition collision: fixture "{provided.name}" is declared by both '
                    f'"{owners[provided.name]}" and "{manifest.id}"')
            owners[provided.name] = manifest.id
            fixtures.append(provided)
    return sorted(fixtures, key=lambda provided: provided.name)


def _composed_packages() -> Tuple[List[_PackageManifest], List[str]]:
    """Load the package manifest of every module the enclosing workspace composes.

    A module that ships no package manifest is not packageable and declares no
    fixtures. Modules that do not resolve to a local directory are named back to
    the caller rather than skipped silently.
    """
    workspace_path = _find_up(Path.cwd(), WORKSPACE_CONFIGURATION_NAME)
    if not workspace_path:
        raise FixtureError("resolve Codefly workspace: no enclosing workspace")
    root = workspace_path.parent
    workspace = yaml.safe_load(workspace_path.read_text()) or {}
    overlay_dir, overlay = _load_overlay(root)
    manifests = []
    unresolved = []
    loaded = set()
    for module in workspace.get("modules") or []:
        directory = _module_directory(root, workspace.get("layout"), module, overlay_dir, overlay)
        if not directory:
            unresolved.append(module["name"])
            continue
        # Two references can name one directory: a module listed twice, or an
        # alias carrying a path override. Loading it once per reference would
        # present a single package as two, which comes back as a collision with
        # itself.
        directory = directory.resolve()
        if directory in loaded:
            continue
        loaded.add(directory)
        manifest_path = directory / PACKAGE_MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        manifests.append(_PackageManifest(**(yaml.safe_load(manifest_path.read_text()) or {})))
    return manifests, unresolved


def _module_directory(root: Path, layout: Optional[str], module: dict, overlay_dir: Optional[Path],
                      overlay: Dict[str, dict]) -> Optional[Path]:
    """Return where a composed module lives, or None when it has no local directory."""
    name = module["name"]
    directive = overlay.get(name)
    if directive is not None:
        if directive.get("path"):
            return _absolute(overlay_dir, directive["path"])
        if not any(directive.get(key) for key in ("worktree", "pinned", "git")):
            raise FixtureError(
                f'overlay entry for module "{name}" selects none of path/worktree/pinned/git '
                f'(check for a typo\'d or empty directive)')
        return None
    if module.get("path"):
        return _absolute(root, module["path"])
    if module.get("source"):
        return None
    if layout == "flat":
        return root
    return root / "modules" / name


def _absolute(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def _load_overlay(directory: Path) -> Tuple[Optional[Path], Dict[str, dict]]:
    """Load the nearest machine-local overlay mapping modules to where they live."""
    overlay_path = _find_up(directory, LOCAL_OVERLAY_CONFIGURATION_NAME)
    if not overlay_path:
        return None, {}
    overlay = yaml.safe_load(overlay_path.read_text()) or {}
    return overlay_path.parent, overlay.get("resolve") or {}


def _find_up(directory: Path, name: str) -> Optional[Path]:
    for candidate in [directory, *directory.parents]:
        path = candidate / name
        if path.is_file():
            return path
    return None
