from pydantic import BaseModel
import os
import yaml
from typing import Optional, Dict
from urllib.parse import urlparse


class Service(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    application: Optional[str] = None
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
    return f"{get_service().application}/{get_service().name}"


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
    host: Optional[str] = None
    port_address: Optional[str] = None
    port: Optional[int] = None


def get_endpoint(unique: str) -> Optional[Endpoint]:
    """Get the endpoint from the environment variable"""
    if unique.startswith("self"):
        unique = unique.replace("self", f"{get_unique()}", 1)

    unique = unique.replace("-", "_")
    unique = unique.upper().replace('/', '__', 1)
    unique = unique.replace('/', '___')
    env = f"CODEFLY_ENDPOINT__{unique}"
    if env in os.environ:
        address = os.environ[env]
        tokens = address.split(":")
        if len(tokens) == 2:
            host, port = tokens
        else:
            parsed_url = urlparse(address)
            host, port = parsed_url.hostname, parsed_url.port
        return Endpoint(host=host, port_address=f":{port}", port=int(port))
    return None


def get_service_provider_info(service: str, name: str, key: str, application: Optional[str] = None) -> Optional[str]:
    if not application:
        application = get_service().application
    unique = f"{application}/{service}"
    # Replace - by _ as they are not great for env
    unique = unique.replace("-", "_")
    unique = f"{unique}___{name}____{key}"
    unique = unique.upper().replace('/', '__', 1)
    env = f"CODEFLY_PROVIDER__{unique}"
    return os.environ.get(env)


def get_project_provider_info(name: str, key: str) -> Optional[str]:
    env = f"CODEFLY_PROVIDER___{name}____{key}".upper()
    return os.environ.get(env)


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
