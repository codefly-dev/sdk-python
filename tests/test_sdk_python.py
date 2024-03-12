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


def test_environment_variable_endpoints():
    os.environ["CODEFLY_ENDPOINT__BACKEND__SERVER___REST"] = "http://localhost:10123"
    endpoint = codefly.get_endpoint("backend/server/rest")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"

    init("tests/testdata/src")

    endpoint = codefly.get_endpoint("self/rest")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"

    os.environ["CODEFLY_ENDPOINT__BACKEND__SERVER___GRPC"] = "localhost:10123"
    endpoint = codefly.get_endpoint("backend/server/grpc")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"

    init("tests/testdata/src")

    endpoint = codefly.get_endpoint("self/grpc")
    assert endpoint.host == "localhost"
    assert endpoint.port == 10123
    assert endpoint.port_address == ":10123"


def test_environment_variable_project_provider():
    os.environ["CODEFLY_PROVIDER___AUTH____CONNECTION"] = "myconnection"
    value = codefly.get_project_provider_info("auth", "connection")
    assert value == "myconnection"


def test_environment_variable_service_provider():
    connection = "postgresql://user:password@localhost:30140/counter-python-nextjs-postgres?sslmode=disable"
    os.environ["CODEFLY_PROVIDER__COUNTER_PYTHON_NEXTJS_POSTGRES__STORE___POSTGRES____CONNECTION"] = connection
    value = codefly.get_service_provider_info(application="counter-python-nextjs-postgres", service="store",
                                              name="postgres", key="connection")
    assert value == connection


def test_environment_variable_service_provider_without_application():
    init("tests/testdata/src")
    connection = "postgresql://user:password@localhost:30140/counter-python-nextjs-postgres?sslmode=disable"
    os.environ["CODEFLY_PROVIDER__BACKEND__STORE___POSTGRES____CONNECTION"] = connection
    value = codefly.get_service_provider_info(service="store",
                                              name="postgres", key="connection")
    assert value == connection

