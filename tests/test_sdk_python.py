from codefly import codefly
from codefly.codefly import init, get_service
import os


def test_load_configurations():
    init("tests/testdata/src")
    assert get_service().name == "server"
    assert get_service().module == "backend"


def test_environment():
    os.environ["CODEFLY_ENVIRONMENT"] = "local"
    assert codefly.is_local()
    os.environ["CODEFLY_ENVIRONMENT"] = "staging"
    assert not codefly.is_local()


def test_service_not_found():
    init("tests")


def test_environment_variable_endpoints():
    init("tests/testdata/src")
    def test(ep, address):
        assert ep.address == address
        assert ep.host == "localhost"
        assert ep.port == 10123
        assert ep.port_address == ":10123"

    address =  "http://localhost:10123"
    os.environ["CODEFLY__ENDPOINT__BACKEND__SERVER__REST__REST"] = address
    endpoint = codefly.endpoint(module="backend", service="server", name="rest", api="rest")
    test(endpoint, address)
    endpoint = codefly.endpoint(service="server", name="rest")
    test(endpoint, address)
    endpoint = codefly.endpoint(name="rest")
    test(endpoint, address)
    endpoint = codefly.endpoint(api="rest")
    test(endpoint, address)

    address = "localhost:10123"
    os.environ["CODEFLY__ENDPOINT__BACKEND__SERVER__GRPC__GRPC"] = address
    endpoint = codefly.endpoint(module="backend", service="server", name="grpc", api="grpc")
    test(endpoint, address)
    endpoint = codefly.endpoint(service="server", name="grpc")
    test(endpoint, address)
    endpoint = codefly.endpoint(name="grpc")
    test(endpoint, address)
    endpoint = codefly.endpoint(api="grpc")
    test(endpoint, address)

    os.environ["CODEFLY__ENDPOINT__BACKEND__SERVER__NAME__GRPC"] = address
    endpoint = codefly.endpoint(module="backend", service="server", name="name", api="grpc")
    test(endpoint, address)
    endpoint = codefly.endpoint(name="name", api="grpc")
    test(endpoint, address)


value = "Hello world!"

def test_configuration_project():
    os.environ["CODEFLY__PROJECT_CONFIGURATION__AUTH__CONNECTION"] =value
    v = codefly.configuration(name="auth", key="connection")
    assert v == value


def test_secret_configuration_project():
    os.environ["CODEFLY__PROJECT_SECRET_CONFIGURATION__AUTH__CONNECTION"] =value
    v = codefly.secret(name="auth", key="connection")
    assert v == value


def test_configuration_service():
    os.environ["CODEFLY__SERVICE_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] =value
    v = codefly.configuration(service="server", module="backend", name="auth", key="connection")
    assert v == value


def test_secret_configuration_service():
    os.environ["CODEFLY__SERVICE_SECRET_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] =value
    v = codefly.secret(service="server", module="backend", name="auth", key="connection")
    assert v == value


def test_configuration_service_no_module():
    os.environ["CODEFLY__SERVICE_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] =value
    v = codefly.configuration(service="server", name="auth", key="connection")
    assert v == value


def test_secret_configuration_service_no_module():
    os.environ["CODEFLY__SERVICE_SECRET_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] =value
    v = codefly.secret(service="server", name="auth", key="connection")
    assert v == value
