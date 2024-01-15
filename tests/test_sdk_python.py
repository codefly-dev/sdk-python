from codefly import codefly
from codefly.codefly import init, service
import os


def test_load_configurations():
    init("tests/testdata")
    assert service().name == "server"
    assert service().application == "backend"


def test_environment_variable_endpoints():
    os.environ["CODEFLY_ENDPOINT__BACKEND__SERVER___REST"] = "localhost:10123"
    endpoint = codefly.get_endpoint("backend/server/rest")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"

    init("tests/testdata")

    endpoint = codefly.get_endpoint("self/rest")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"


def test_environment_variable_project_provider():
    os.environ["CODEFLY_PROVIDER___AUTH____CONNECTION"] = "myconnection"
    value = codefly.get_project_provider_info("auth", "connection")
    assert value == "myconnection"


def test_environment_variable_service_provider():
    os.environ["CODEFLY_PROVIDER__MANAGEMENT__STORE___POSTGRES____CONNECTION"] = "myconnection"
    value = codefly.get_service_provider_info("management/store", "postgres", "connection")
    assert value == "myconnection"
