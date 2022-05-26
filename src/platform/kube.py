import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Optional

from kubernetes.client import CoreV1Api, CustomObjectsApi  # type: ignore
from kubernetes.client.exceptions import ApiException  # type: ignore
from kubernetes.config import new_client_from_config  # type: ignore
from pydantic import BaseModel, Field

logger = logging.getLogger()


class NotFoundError(Exception):
    pass


def handle_error(func: Callable) -> Callable:  # type: ignore
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        try:
            return func(*args, **kwargs)
        except ApiException as error:
            logger.debug(
                "Kube Client Call Error: %s\nArgs: %s\nKwargs: %s",
                error.reason,
                args,
                kwargs,
            )
            if error.status == 404:
                raise NotFoundError("Kubernetes resource not found.") from error
            raise

    return wrapper


@dataclass
class CustomObjectRequest:
    group: str
    plural: str
    label_selector: Optional[str] = None
    name: Optional[str] = None
    namespace: str = "openshift-storage"
    version: str = "v1"


class KubeResponseMetadata(BaseModel):
    name: str


class KubeResponseStatusCondition(BaseModel):
    status: bool = False
    type: str = ""


class KubeResponseStatus(BaseModel):
    conditions: list[KubeResponseStatusCondition] = []
    phase: str
    storage_provider_endpoint: str = Field(alias="storageProviderEndpoint", default="")


class KubeResponse(BaseModel):
    metadata: KubeResponseMetadata
    status: KubeResponseStatus


class KubeResponseList(BaseModel):
    items: list[KubeResponse] = []


class KubeClient:
    _core_v1_api: CoreV1Api
    _custom_objects_api: CustomObjectsApi

    def __init__(self, config_file: str) -> None:
        api_client = new_client_from_config(config_file=config_file)
        self._core_v1_api = CoreV1Api(api_client=api_client)
        self._custom_objects_api = CustomObjectsApi(api_client=api_client)

    @handle_error
    def get_object(self, request: CustomObjectRequest) -> KubeResponse:
        return KubeResponse(
            **self._custom_objects_api.get_namespaced_custom_object(
                group=request.group,
                version=request.version,
                name=request.name,
                plural=request.plural,
                namespace=request.namespace,
            )
        )

    @handle_error
    def list_nodes_statuses(self) -> list[bool]:
        statuses = []
        response: KubeResponseList = self._core_v1_api.list_node()
        for node in response.items:
            for condition in node.status.conditions:
                if condition.type == "Ready":
                    logger.debug(
                        "Ready status of node %s: %s",
                        node.metadata.name,
                        condition.status,
                    )
                    statuses.append(condition.status)
        return statuses

    @handle_error
    def list_objects(self, request: CustomObjectRequest) -> KubeResponseList:
        return KubeResponseList(
            **self._custom_objects_api.list_namespaced_custom_object(
                group=request.group,
                version=request.version,
                plural=request.plural,
                namespace=request.namespace,
                label_selector=request.label_selector,
            )
        )
