from pydantic import BaseModel
import os
import yaml
from typing import Optional, Dict


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


def service() -> Optional[Service]:
    global current_service
    if current_service is None:
        init(".")
    return current_service


def init(d: Optional[str] = "."):
    """Load the service configuration from the service.codefly.yaml file"""
    path = f"{d}/service.codefly.yaml"
    with open(path, 'r') as f:
        global current_service
        current_service = Service(**yaml.safe_load(f))


def is_local() -> bool:
    return os.getenv("CODEFLY_ENVIRONMENT") == "local"


class Endpoint(BaseModel):
    host: Optional[str] = None
    port_address: Optional[str] = None
    port: Optional[int] = None


def get_endpoint(unique: str) -> Optional[Endpoint]:
    """Get the endpoint from the environment variable"""
    if unique.startswith("self"):
        unique = unique.replace("self", f"{service().application}/{service().name}", 1)

    unique = unique.upper().replace('/', '__', 1)
    unique = unique.replace('/', '___')
    env = f"CODEFLY_ENDPOINT__{unique}"
    if env in os.environ:
        host, port = os.environ[env].split(":")
        return Endpoint(host=host, port_address=f":{port}", port=int(port))
    return None


def get_service_provider_info(unique: str, name: str, key: str) -> Optional[str]:
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
