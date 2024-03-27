from pydantic import BaseModel
import os
import yaml
from typing import Optional, Dict
import base64


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


# class Endpoint(BaseModel):
#     host: Optional[str] = None
#     port_address: Optional[str] = None
#     port: Optional[int] = None
#
#
# def get_endpoint(unique: str) -> Optional[Endpoint]:
#     """Get the endpoint from the environment variable"""
#     if unique.startswith("self"):
#         unique = unique.replace("self", f"{get_unique()}", 1)
#
#     unique = unique.replace("-", "_")
#     unique = unique.upper().replace('/', '__', 1)
#     unique = unique.replace('/', '___')
#     env = f"CODEFLY_ENDPOINT__{unique}"
#     if env in os.environ:
#         address = os.environ[env]
#         tokens = address.split(":")
#         if len(tokens) == 2:
#             host, port = tokens
#         else:
#             parsed_url = urlparse(address)
#             host, port = parsed_url.hostname, parsed_url.port
#         return Endpoint(host=host, port_address=f":{port}", port=int(port))
#     return None


def decode_base64(data: str) -> str:
    decoded_bytes = base64.b64decode(data)
    return decoded_bytes.decode('utf-8')


def configuration(name: str = None, key: str = None, service: Optional[str] = None, application: Optional[str] = None) -> Optional[str]:
    if not name:
        raise KeyError("name is required")
    if not key:
        raise KeyError("key is required")
    if service:
        return _get_service_configuration(service, name, key, application=application)
    return _get_project_configuration(name, key)

def secret(name: str = None, key: str = None, service: Optional[str] = None, application: Optional[str] = None) -> Optional[str]:
    if not name:
        raise KeyError("name is required")
    if not key:
        raise KeyError("key is required")
    if service:
        return _get_service_configuration(service, name, key, application=application, is_secret=True)
    return _get_project_configuration(name, key, is_secret=True)


def _get_service_configuration(service: str, name: str, key: str, application: Optional[str] = None,
                               is_secret: bool = False) -> Optional[str]:
    if not application:
        application = get_service().application
    env_key = f"{application}__{service}"
    # Replace - by _ as they are not great for env
    env_key = env_key.replace("-", "_")
    env_key = f"{env_key}__{name}__{key}"
    prefix = "CODEFLY__SERVICE_CONFIGURATION"
    if is_secret:
        prefix = "CODEFLY__SERVICE_SECRET_CONFIGURATION"
    key = f"{prefix}__{env_key}"
    key = key.upper()
    value = os.getenv(key)
    if not value:
        return None
    return decode_base64(value)


def _get_project_configuration(name: str, key: str,
                               is_secret: bool = False) -> Optional[str]:
    env_key = f"{name}__{key}"
    prefix = "CODEFLY__PROJECT_CONFIGURATION"
    if is_secret:
        prefix = "CODEFLY__PROJECT_SECRET_CONFIGURATION"
    key = f"{prefix}__{env_key}"
    key = key.upper()
    print(key)
    value = os.getenv(key)
    if not value:
        return None
    return decode_base64(value)




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
