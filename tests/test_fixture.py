from codefly_sdk import codefly
import pytest

DEV_ADMIN_PACKAGE = """kind: module-package
schema: codefly/module-package/v2
id: codefly/saas-starter
version: 0.1.0
minimum-codefly-version: ">=0.3.32"
artifact-roots:
  - services
contracts:
  composition: ">=2.0 <3.0"
  fixtures: ">=1.0 <2.0"
fixtures:
  - name: dev-admin
    description: Seeded tenant with an administrator
    principals:
      - id: dev-admin
        email: admin@dev.local
        role: super_admin
        token: dev-admin-provider-id
      - id: dev-member
        email: member@dev.local
        role: member
        token: dev-member-provider-id
"""


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def composing_workspace(tmp_path, monkeypatch):
    """A workspace composing a module that ships the dev-admin fixture alongside
    one that ships no package manifest."""
    write(tmp_path / "workspace.codefly.yaml",
          "name: solution\nlayout: modules\nmodules:\n  - name: saas-starter\n  - name: plain\n")
    write(tmp_path / "modules" / "saas-starter" / "module.package.codefly.yaml", DEV_ADMIN_PACKAGE)
    write(tmp_path / "modules" / "plain" / "services" / ".keep", "")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_fixture_principal_resolves_by_role(composing_workspace, monkeypatch):
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    principal = codefly.fixture().principal("super_admin")

    assert principal.id == "dev-admin"
    assert principal.email == "admin@dev.local"
    assert principal.token == "dev-admin-provider-id"


def test_fixture_principal_unknown_role_names_seeded_roles(composing_workspace, monkeypatch):
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    with pytest.raises(codefly.UnknownPrincipalError) as raised:
        codefly.fixture().principal("owner")

    assert "super_admin, member" in str(raised.value)


def test_fixture_principal_unknown_fixture_names_available_fixtures(composing_workspace, monkeypatch):
    monkeypatch.setenv("CODEFLY__FIXTURE", "typo")

    with pytest.raises(codefly.UnknownFixtureError) as raised:
        codefly.fixture().principal("super_admin")

    assert "dev-admin" in str(raised.value)


def test_fixture_principal_without_selected_fixture(composing_workspace, monkeypatch):
    monkeypatch.delenv("CODEFLY__FIXTURE", raising=False)

    with pytest.raises(codefly.FixtureError) as raised:
        codefly.fixture().principal("super_admin")

    assert "no fixture is selected" in str(raised.value)


def test_fixture_principal_resolves_through_the_local_overlay(tmp_path, monkeypatch):
    write(tmp_path / "workspace" / "workspace.codefly.yaml",
          "name: solution\nlayout: modules\nmodules:\n  - name: saas-starter\n")
    write(tmp_path / "workspace" / "codefly.local.yaml",
          "resolve:\n  saas-starter:\n    path: ../checkout\n")
    write(tmp_path / "checkout" / "module.package.codefly.yaml", DEV_ADMIN_PACKAGE)
    monkeypatch.chdir(tmp_path / "workspace")
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    principal = codefly.fixture().principal("member")

    assert principal.id == "dev-member"


def test_fixture_principal_resolves_when_one_directory_is_referenced_twice(tmp_path, monkeypatch):
    write(tmp_path / "workspace.codefly.yaml",
          "name: solution\nlayout: modules\nmodules:\n  - name: saas-starter\n"
          "  - name: alias\n    path: modules/saas-starter\n")
    write(tmp_path / "modules" / "saas-starter" / "module.package.codefly.yaml", DEV_ADMIN_PACKAGE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    principal = codefly.fixture().principal("super_admin")

    assert principal.id == "dev-admin"


def test_fixture_principal_names_modules_it_cannot_read(tmp_path, monkeypatch):
    write(tmp_path / "workspace.codefly.yaml",
          "name: solution\nlayout: modules\nmodules:\n"
          "  - name: saas-starter\n    source: codefly-dev/module-saas-starter\n    version: 0.1.0\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    with pytest.raises(codefly.UnknownFixtureError) as raised:
        codefly.fixture().principal("super_admin")

    assert "saas-starter" in str(raised.value)


def test_fixture_principal_reports_a_fixture_declared_twice(tmp_path, monkeypatch):
    write(tmp_path / "workspace.codefly.yaml",
          "name: solution\nlayout: modules\nmodules:\n  - name: saas-starter\n  - name: other\n")
    write(tmp_path / "modules" / "saas-starter" / "module.package.codefly.yaml", DEV_ADMIN_PACKAGE)
    write(tmp_path / "modules" / "other" / "module.package.codefly.yaml",
          DEV_ADMIN_PACKAGE.replace("id: codefly/saas-starter", "id: codefly/other"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    with pytest.raises(codefly.FixtureCollisionError) as raised:
        codefly.fixture().principal("super_admin")

    assert "codefly/saas-starter" in str(raised.value)
    assert "codefly/other" in str(raised.value)


def test_fixture_principal_outside_a_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEFLY__FIXTURE", "dev-admin")

    with pytest.raises(codefly.FixtureError) as raised:
        codefly.fixture().principal("super_admin")

    assert "no enclosing workspace" in str(raised.value)
