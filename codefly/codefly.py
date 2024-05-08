from urllib.parse import urlparse

from pydantic import BaseModel
import os
import yaml
from typing import Optional, Dict
import base64


class Service(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    module: Optional[str] = None
    domain: Optional[str] = None
    namespace: Optional[str] = None
    agent: Optional[dict] = None
    dependencies: Optional[list] = None
    provider_dependencies: Optional[list] = None
    endpoints: Optional[list] = None
    spec: Optional[dict] = None


current_service = None


def get_service() -> Optional[Service]:
    global current_service
    if current_service is None:
        init()
    return current_service


def get_unique() -> str:
    return f"{get_service().module}/{get_service().name}"


def init(init_dir: Optional[str] = None):
    """Load the service configuration from the service.codefly.yaml file or up"""
    if not init_dir:
        init_dir = os.getcwd()
    configuration_path = find_service_path(init_dir)
    if configuration_path:
        load_service(configuration_path)


def load_service(configuration_path: str):
    """Load service."""
    with open(configuration_path, 'r') as f:
        global current_service
        current_service = Service(**yaml.safe_load(f))


def find_service_path(d: str) -> Optional[str]:
    """Find service in directory or up."""
    current_dir = d
    while current_dir:
        file_path = os.path.join(current_dir, 'service.codefly.yaml')
        if os.path.isfile(file_path):
            return file_path
        else:
            current_dir = os.path.dirname(current_dir)
    return None


def is_local() -> bool:
    return os.getenv("CODEFLY_ENVIRONMENT") == "local"


class Endpoint(BaseModel):
    address: str
    host: str
    port_address: str
    port: int


def endpoint(module: Optional[str] = None, service: Optional[str] = None, name: Optional[str] = None, api: Optional[str] = None) -> Optional[Endpoint]:
    """Get the endpoint from the environment variable"""
    if not service:
        service = get_service().name
    if not module:
        module = get_service().module

    key = f"CODEFLY__ENDPOINT__{module}__{service}"
    if not name and api:
        name = api
    if not api and name:
        api = name
    key = f"{key}__{name}__{api}".upper()
    if key not in os.environ:
        return None
    address = os.environ[key]
    tokens = address.split(":")
    if len(tokens) == 2:
        host, port = tokens
    else:
        parsed_url = urlparse(address)
        host, port = parsed_url.hostname, parsed_url.port
    return Endpoint(host=host, address=address, port_address=f":{port}", port=int(port))


def is_running() -> bool:
    """Returns true if we are in running mode."""
    key = "CODEFLY__RUNNING"
    return os.getenv(key) is not None


def configuration(name: str = None, key: str = None, service: Optional[str] = None,
                  module: Optional[str] = None) -> Optional[str]:
    if not name:
        raise KeyError("name is required")
    if not key:
        raise KeyError("key is required")
    if service:
        return _get_service_configuration(service, name, key, module=module)
    return _get_project_configuration(name, key)


def secret(name: str = None, key: str = None, service: Optional[str] = None, module: Optional[str] = None) -> \
        Optional[str]:
    if not name:
        raise KeyError("name is required")
    if not key:
        raise KeyError("key is required")
    if service:
        return _get_service_configuration(service, name, key, module=module, is_secret=True)
    return _get_project_configuration(name, key, is_secret=True)


def _get_service_configuration(service: str, name: str, key: str, module: Optional[str] = None,
                               is_secret: bool = False) -> Optional[str]:
    if not module:
        module = get_service().module
    env_key = f"{module}__{service}"
    # Replace - by _ as they are not great for env
    env_key = env_key.replace("-", "_")
    env_key = f"{env_key}__{name}__{key}"
    prefix = "CODEFLY__SERVICE_CONFIGURATION"
    if is_secret:
        prefix = "CODEFLY__SERVICE_SECRET_CONFIGURATION"
    key = f"{prefix}__{env_key}"
    key = key.upper()
    return os.getenv(key)


def _get_project_configuration(name: str, key: str,
                               is_secret: bool = False) -> Optional[str]:
    env_key = f"{name}__{key}"
    prefix = "CODEFLY__PROJECT_CONFIGURATION"
    if is_secret:
        prefix = "CODEFLY__PROJECT_SECRET_CONFIGURATION"
    key = f"{prefix}__{env_key}"
    key = key.upper()
    return os.getenv(key)


def user_id_from_headers(headers: Dict[str, str]) -> Optional[str]:
    return headers.get("X-CODEFLY-USER-ID")


def user_email_from_headers(headers: Dict[str, str]) -> Optional[str]:
    return headers.get("X-CODEFLY-USER-EMAIL")


def user_name_from_headers(headers: Dict[str, str]) -> Optional[str]:
    return headers.get("X-CODEFLY-USER-NAME")


def user_given_name_from_headers(headers: Dict[str, str]) -> Optional[str]:
    return headers.get("X-CODEFLY-USER-GIVEN-NAME")


def user_family_name_from_headers(headers: Dict[str, str]) -> Optional[str]:
    return headers.get("X-CODEFLY-USER-FAMILY-NAME")
