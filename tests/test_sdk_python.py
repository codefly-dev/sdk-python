from codefly import codefly
from codefly.codefly import load_service_configuration
import os


def test_load_configurations():
    conf = load_service_configuration("tests/testdata")
    assert conf.name == "server"
    assert conf.application == "backend"
    assert conf.version == "0.0.1"


def test_environment_variable_endpoints():
    os.environ["CODEFLY_ENDPOINT__BACKEND__SERVER___REST"] = "localhost:10123"
    endpoint = codefly.get_endpoint("backend/server/rest")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"

    load_service_configuration("tests/testdata")
    assert codefly.service.name == "server"

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
