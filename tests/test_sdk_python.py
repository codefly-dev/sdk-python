from codefly import codefly
from codefly.codefly import init, get_service
import os


def test_load_configurations():
    init("tests/testdata/src")
    assert get_service().name == "server"
    assert get_service().application == "backend"


def test_environment():
    os.environ["CODEFLY_ENVIRONMENT"] = "local"
    assert codefly.is_local()
    os.environ["CODEFLY_ENVIRONMENT"] = "staging"
    assert not codefly.is_local()


def test_service_not_found():
    init("tests")


# def test_environment_variable_endpoints():
#     os.environ["CODEFLY_ENDPOINT__BACKEND__SERVER___REST"] = "http://localhost:10123"
#     endpoint = codefly.get_endpoint("backend/server/rest")
#     assert endpoint.host == "localhost"
#     assert endpoint.port == 10123
#     assert endpoint.port_address == ":10123"
#
#     init("tests/testdata/src")
#
#     endpoint = codefly.get_endpoint("self/rest")
#     assert endpoint.host == "localhost"
#     assert endpoint.port == 10123
#     assert endpoint.port_address == ":10123"
#
#     os.environ["CODEFLY_ENDPOINT__BACKEND__SERVER___GRPC"] = "localhost:10123"
#     endpoint = codefly.get_endpoint("backend/server/grpc")
#     assert endpoint.host == "localhost"
#     assert endpoint.port == 10123
#     assert endpoint.port_address == ":10123"
#
#     init("tests/testdata/src")
#
#     endpoint = codefly.get_endpoint("self/grpc")
#     assert endpoint.host == "localhost"
#     assert endpoint.port == 10123
#     assert endpoint.port_address == ":10123"
#

value = "Hello world!"
encoded_value = "SGVsbG8gd29ybGQh"


def test_configuration_project():
    os.environ["CODEFLY__PROJECT_CONFIGURATION__AUTH__CONNECTION"] = encoded_value
    v = codefly.configuration(name="auth", key="connection")
    assert v == value


def test_secret_configuration_project():
    os.environ["CODEFLY__PROJECT_SECRET_CONFIGURATION__AUTH__CONNECTION"] = encoded_value
    v = codefly.secret(name="auth", key="connection")
    assert v == value


def test_configuration_service():
    os.environ["CODEFLY__SERVICE_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] = encoded_value
    v = codefly.configuration(service="server", application="backend", name="auth", key="connection")
    assert v == value


def test_secret_configuration_service():
    os.environ["CODEFLY__SERVICE_SECRET_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] = encoded_value
    v = codefly.secret(service="server", application="backend", name="auth", key="connection")
    assert v == value


def test_configuration_service_no_application():
    os.environ["CODEFLY__SERVICE_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] = encoded_value
    v = codefly.configuration(service="server", name="auth", key="connection")
    assert v == value


def test_secret_configuration_service_no_application():
    os.environ["CODEFLY__SERVICE_SECRET_CONFIGURATION__BACKEND__SERVER__AUTH__CONNECTION"] = encoded_value
    v = codefly.secret(service="server", name="auth", key="connection")
    assert v == value
