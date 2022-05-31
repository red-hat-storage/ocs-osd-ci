import json
import logging
import os
import random
import string
from enum import Enum
from shutil import copy
from typing import Any, Optional, Union

from src.platform.kube import CustomObjectRequest, KubeClient, NotFoundError
from src.util.util import (
    download_file,
    env,
    get_file_content,
    run_cmd,
    save_to_file,
    save_to_json_file,
    wait_for,
)

logger = logging.getLogger()


class AddonId(Enum):
    CONSUMER = "ocs-consumer-dev"
    PROVIDER = "ocs-provider-dev"


class ClusterService:
    _addon_install_data: dict[str, Any] = {
        "addon": {"id": ""},
        "parameters": {"items": []},
    }
    _api_base_url = "/api/clusters_mgmt/v1/clusters"
    _bin_dir: str = os.path.abspath(os.path.expanduser("~/bin"))
    _data_dir: str
    _cluster_install_data: dict[str, Any] = {
        "aws": {
            "access_key_id": env("AWS_ACCESS_KEY_ID"),
            "account_id": env("AWS_ACCOUNT_ID"),
            "secret_access_key": env("AWS_SECRET_ACCESS_KEY"),
            "subnet_ids": [],
        },
        "ccs": {"enabled": True},
        "cloud_provider": {"id": "aws"},
        "name": "",
        "nodes": {
            "compute": 3,
            "compute_machine_type": {"id": "m5.4xlarge"},
        },
        "region": {"id": env("AWS_REGION")},
    }
    _kube_client_instances: dict[str, KubeClient] = {}
    _ocm_config_file: str
    _ocm_config_template: dict[str, Union[str, list[str]]] = {
        "client_id": "cloud-services",
        "refresh_token": env("OCM_REFRESH_TOKEN"),
        "scopes": ["openid"],
        "token_url": "https://sso.redhat.com/auth/realms/"
        "redhat-external/protocol/openid-connect/token",
        "url": "https://api.stage.openshift.com",
    }
    _onboarding_ticket_generator_file: str
    _onboarding_private_key: str

    def __init__(self, data_dir: str = ".cluster") -> None:
        os.makedirs(self._bin_dir, exist_ok=True)

        self._install_ocm()

        self._data_dir = data_dir
        os.makedirs(os.path.abspath(self._data_dir), exist_ok=True)

        self._set_ocm_config()
        self._save_onboarding_ticket_required_files()

    def get_addon_ocs_provider_storage_endpoint(self, cluster_id: str) -> str:
        kube_client = self._get_kube_client(cluster_id)
        request = CustomObjectRequest(
            group="ocs.openshift.io",
            name="ocs-storagecluster",
            plural="storageclusters",
        )
        try:
            storage_provider_endpoint = kube_client.get_object(
                request
            ).status.storage_provider_endpoint
        except NotFoundError:
            logger.exception(
                "Storage Cluster info not found "
                "while retrieving the Storage Provider Endpoint."
            )
            raise
        logger.info("Storage Provider Endpoint: %s", storage_provider_endpoint)
        return storage_provider_endpoint

    def get_consumer_onboarding_ticket(self) -> str:
        response = run_cmd(
            [self._onboarding_ticket_generator_file, self._onboarding_private_key]
        )
        logger.info("Consumer Onboarding Ticket:\n%s", response.stdout)
        return response.stdout

    def install(
        self,
        cluster_name: str,
        subnets_ids: Optional[list[str]] = None,
        availability_zones: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        request_body = self._cluster_install_data.copy()
        request_body["name"] = cluster_name
        if subnets_ids:
            request_body["aws"]["subnet_ids"] = subnets_ids
        elif env.list("AWS_SUBNET_IDS", default=[]):
            request_body["aws"]["subnet_ids"] = env.list("AWS_SUBNET_IDS")
        if availability_zones:
            request_body["nodes"]["availability_zones"] = availability_zones
        elif env.list("AWS_AVAILABILITY_ZONES", default=[]):
            request_body["nodes"]["availability_zones"] = env.list(
                "AWS_AVAILABILITY_ZONES"
            )
        # Save request body to a file in order to avoid passing secrets as CLI args.
        body_file = save_to_json_file(
            f"{self._data_dir}/install-cluster-{cluster_name}.json", request_body
        )

        result = run_cmd(["ocm", "post", self._api_base_url, "--body", body_file])
        if not result.stdout:
            raise ValueError("No cluster info received.")
        return json.loads(result.stdout)

    def install_addon(
        self, cluster_id: str, addon_id: str, addon_params: dict[str, Any]
    ) -> None:
        body_file = self._get_addon_install_request_file_path(addon_id, addon_params)
        addon_info = run_cmd(
            # fmt: off
            ["ocm", "post", f"{self._api_base_url}/{cluster_id}/addons",
             "--body", body_file]
            # fmt: on
        )
        if not addon_info.stdout:
            raise ValueError("No addon info received.")

    @staticmethod
    def random_cluster_name(prefix: str = "ci") -> str:
        prefix = f"{prefix}-"
        cluster_name_max_length = 15
        if len(prefix) >= cluster_name_max_length:
            raise ValueError(
                "Cluster name cannot exceed max. length: " f"{cluster_name_max_length}"
            )
        random_suffix_length = len(prefix)
        return "".join(
            [prefix]
            + [
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(cluster_name_max_length - random_suffix_length)
            ]
        )

    def share_kubeconfig_file(self, cluster_id: str, target_file: str) -> None:
        config_file = self._save_cluster_config_file(cluster_id)
        copy(src=config_file, dst=f"./{self._data_dir}/{target_file}")

    @wait_for()
    def wait_for_addon_ready(self, cluster_id: str, addon_id: AddonId) -> bool:
        addon_status = self._get_addon_ocs_status(cluster_id)
        if addon_status == "Succeeded":
            logger.info("Addon %s is ready.", addon_id.value)
            return True
        if addon_status == "Failed":
            raise ValueError(f"Addon {addon_id.value} is in Failed state.")
        logger.info("Addon %s is not ready yet...", addon_id.value)
        return False

    @wait_for()
    def wait_for_cluster_ready(self, cluster_id: str) -> bool:
        cluster_info = self._get_cluster_info(cluster_id)
        cluster_name = cluster_info["name"]
        cluster_status = cluster_info["status"]["state"]
        if cluster_status == "ready" and False not in self._get_cluster_nodes_statuses(
            cluster_id
        ):
            logger.info("Cluster %s is ready.", cluster_name)
            return True
        if cluster_status == "error":
            raise ValueError(f"Cluster {cluster_name} is in error state.")
        logger.info("Cluster %s is not ready yet...", cluster_name)
        return False

    def _get_addon_install_request_file_path(
        self, addon_id: str, params: dict[str, Any]
    ) -> str:
        body = self._addon_install_data.copy()
        body["addon"]["id"] = addon_id
        for param_id, param_value in params.items():
            body["parameters"]["items"].append({"id": param_id, "value": param_value})
        return save_to_json_file(
            f"{self._data_dir}/install-addon-{addon_id}.json", body
        )

    def _get_addon_ocs_status(self, cluster_id: str) -> str:
        kube_client = self._get_kube_client(cluster_id)
        request = CustomObjectRequest(
            group="operators.coreos.com",
            version="v1alpha1",
            plural="clusterserviceversions",
            label_selector="operators.coreos.com/ocs-osd-deployer.openshift-storage",
        )
        status = "Not Found"
        try:
            response = kube_client.list_objects(request)
        except NotFoundError:
            return status
        if len(response.items) > 0:
            status = response.items[0].status.phase
        logger.debug("Addon status: %s", status)
        return status

    def _get_cluster_info(self, cluster_id: str) -> dict[str, Any]:
        completed_process = run_cmd(
            ["ocm", "get", f"{self._api_base_url}/{cluster_id}"]
        )
        return json.loads(completed_process.stdout)

    def _get_cluster_nodes_statuses(self, cluster_id: str) -> list[bool]:
        return self._get_kube_client(cluster_id).list_nodes_statuses()

    def _get_kube_client(self, cluster_id: str) -> KubeClient:
        if cluster_id in self._kube_client_instances:
            return self._kube_client_instances[cluster_id]
        cluster_config_path = self._save_cluster_config_file(cluster_id)
        self._kube_client_instances[cluster_id] = KubeClient(cluster_config_path)
        return self._kube_client_instances[cluster_id]

    def _install_ocm(self) -> None:
        ocm_binary = f"{self._bin_dir}/ocm"
        if not os.path.exists(ocm_binary):
            ocm_url = (
                "https://github.com/openshift-online/ocm-cli/releases/"
                f"download/{env('OCM_VERSION')}/ocm-linux-amd64"
            )
            download_file(ocm_url, ocm_binary)
        # Give execution permissions.
        os.chmod(ocm_binary, 0o700)

    def _save_cluster_config_file(self, cluster_id: str) -> str:
        config_file = f"{self._data_dir}/{cluster_id}-config.yaml"
        if not os.path.exists(config_file):
            response = run_cmd(
                ["ocm", "get", f"{self._api_base_url}/{cluster_id}/credentials"]
            )
            cluster_config: str = json.loads(response.stdout)["kubeconfig"]
            save_to_file(config_file, cluster_config)
            os.chmod(config_file, 0o600)
        return config_file

    def _save_onboarding_ticket_required_files(self) -> None:
        self._onboarding_ticket_generator_file = f"{self._data_dir}/ticketgen.sh"
        if not os.path.exists(self._onboarding_ticket_generator_file):
            download_file(
                url="https://raw.githubusercontent.com/red-hat-storage/"
                "ocs-operator/main/hack/ticketgen/ticketgen.sh",
                file_path=self._onboarding_ticket_generator_file,
            )
            # Extend the ticket expiration date.
            file_content = get_file_content(self._onboarding_ticket_generator_file)
            file_content = file_content.replace("172800", "999999999")
            save_to_file(self._onboarding_ticket_generator_file, file_content)
            # Give execution permissions.
            os.chmod(self._onboarding_ticket_generator_file, 0o700)
        # Create the onboarding private key.
        self._onboarding_private_key = f"{self._data_dir}/onboarding-private-key"
        if not os.path.exists(self._onboarding_private_key):
            save_to_file(self._onboarding_private_key, env("ONBOARDING_PRIVATE_KEY"))

    def _set_ocm_config(self) -> None:
        self._ocm_config_file = f"{self._data_dir}/ocm.json"
        if not os.path.exists(self._ocm_config_file):
            save_to_json_file(self._ocm_config_file, self._ocm_config_template)
        os.environ["OCM_CONFIG"] = self._ocm_config_file
