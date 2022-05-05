from typing import Any

from kubernetes.client import CustomObjectsApi  # type: ignore
from kubernetes.config import load_kube_config  # type: ignore


class KubeClient:
    _custom_objects_api: CustomObjectsApi

    def __init__(self, config_file: str) -> None:
        load_kube_config(config_file=config_file)
        self._custom_objects_api = CustomObjectsApi()

    def get_storage_provider_endpoint(self):
        response: dict[
            str, Any
        ] = self._custom_objects_api.get_namespaced_custom_object(
            group="ocs.openshift.io",
            version="v1",
            name="ocs-storagecluster",
            plural="storageclusters",
            namespace="openshift-storage",
        )
        return response["status"]["storageProviderEndpoint"]
