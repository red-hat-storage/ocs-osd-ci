import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from kubernetes.client import CustomObjectsApi  # type: ignore
from kubernetes.client.exceptions import ApiException  # type: ignore
from kubernetes.config import load_kube_config  # type: ignore

logger = logging.getLogger()


class NotFoundError(Exception):
    pass


def handle_error(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
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
    label_selector: str | None = None
    name: str | None = None
    namespace: str = "openshift-storage"
    version: str = "v1"


class KubeClient:
    _custom_objects_api: CustomObjectsApi

    def __init__(self, config_file: str) -> None:
        load_kube_config(config_file=config_file)
        self._custom_objects_api = CustomObjectsApi()

    @handle_error
    def get_object(self, request: CustomObjectRequest) -> dict:
        response: dict[
            str, Any
        ] = self._custom_objects_api.get_namespaced_custom_object(
            group=request.group,
            version=request.version,
            name=request.name,
            plural=request.plural,
            namespace=request.namespace,
        )
        return response

    @handle_error
    def list_objects(self, request: CustomObjectRequest) -> dict:
        response: dict[
            str, Any
        ] = self._custom_objects_api.list_namespaced_custom_object(
            group=request.group,
            version=request.version,
            plural=request.plural,
            namespace=request.namespace,
            label_selector=request.label_selector,
        )
        return response
