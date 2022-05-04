import json
import logging
import os
from enum import Enum
from typing import Any, Dict

from src.util.util import create_json_file, download_file, env, run_cmd, wait_for

logger = logging.getLogger()


class AddonId(Enum):
    CONSUMER = "ocs-consumer"
    PROVIDER = "ocs-provider"


class ClusterService:
    _addon_install_data: Dict[str, Any] = {
        "addon": {"id": ""},
        "parameters": {"items": []},
    }
    _bin_dir: str = os.path.abspath(os.path.expanduser("~/bin"))
    _data_dir: str
    _cluster_install_data: Dict[str, Any] = {
        "aws": {
            "access_key_id": env("AWS_ACCESS_KEY_ID"),
            "account_id": env("AWS_ACCOUNT_ID"),
            "secret_access_key": env("AWS_SECRET_ACCESS_KEY"),
            "subnet_ids": env.list("AWS_SUBNET_IDS"),
        },
        "ccs": {"enabled": True},
        "cloud_provider": {"id": "aws"},
        "name": "",
        "nodes": {
            "availability_zones": env.list("AWS_AVAILABILITY_ZONES"),
            "compute": 3,
            "compute_machine_type": {"id": "m5.4xlarge"},
        },
        "region": {"id": env("AWS_REGION")},
    }
    _ocm_config_file: str
    _ocm_config_template: Dict[str, str | list[str]] = {
        "client_id": "cloud-services",
        "refresh_token": env("OCM_REFRESH_TOKEN"),
        "scopes": ["openid"],
        "token_url": "https://sso.redhat.com/auth/realms/"
        "redhat-external/protocol/openid-connect/token",
        "url": "https://api.stage.openshift.com",
    }

    def __init__(self, data_dir: str = ".cluster"):
        self._data_dir = data_dir
        self._ocm_config_file = f"{data_dir}/ocm.json"
        # Create data dir and ocm config file.
        os.makedirs(os.path.abspath(data_dir), exist_ok=True)
        create_json_file(self._ocm_config_file, self._ocm_config_template)
        # Set ocm config.
        os.environ["OCM_CONFIG"] = self._ocm_config_file
        # Create bin dir.
        os.makedirs(self._bin_dir, exist_ok=True)
        # Install ocm.
        self._install_ocm()

    def install(self, cluster_name: str) -> str:
        body_file = self._get_cluster_install_request_file_path(cluster_name)
        cluster_info = run_cmd(
            ["ocm", "post", "/api/clusters_mgmt/v1/clusters", "--body", body_file]
        )
        if not cluster_info.stdout:
            raise ValueError("No cluster info received.")
        cluster = json.loads(cluster_info.stdout)
        return cluster["id"]

    def install_addon(
        self, cluster_id: str, addon_id: str, addon_params: Dict[str, Any]
    ) -> None:
        body_file = self._get_addon_install_request_file_path(addon_id, addon_params)
        addon_info = run_cmd(
            # fmt: off
            ["ocm", "post", f"/api/clusters_mgmt/v1/clusters/{cluster_id}/addons",
             "--body", body_file]
            # fmt: on
        )
        if not addon_info.stdout:
            raise ValueError("No addon info received.")

    @staticmethod
    def get_addon_status(cluster_id: str, addon_id: str) -> str:
        # fmt: off
        completed_process = run_cmd(
            ["ocm", "get",
             f"/api/clusters_mgmt/v1/clusters/{cluster_id}/addons/{addon_id}"]
        )
        # fmt: on
        return json.loads(completed_process.stdout)["state"]

    @staticmethod
    def get_cluster_status(cluster_id: str) -> str:
        # fmt: off
        completed_process = run_cmd(
            ["ocm", "get", f"/api/clusters_mgmt/v1/clusters/{cluster_id}"]
        )
        # fmt: on
        return json.loads(completed_process.stdout)["status"]["state"]

    @wait_for()
    def wait_for_addon_ready(self, cluster_id: str, addon_id: str) -> bool:
        addon_status = self.get_addon_status(cluster_id, addon_id)
        if addon_status == "ready":
            logger.info("Addon %s is ready.", addon_id)
            return True
        if addon_status == "error":
            raise ValueError(f"Addon {addon_id} is in error state.")
        logger.info("Addon %s is not ready yet...", addon_id)
        return False

    @wait_for()
    def wait_for_cluster_ready(self, cluster_id: str) -> bool:
        cluster_status = self.get_cluster_status(cluster_id)
        if cluster_status == "ready":
            logger.info("Cluster %s is ready.", cluster_id)
            return True
        if cluster_status == "error":
            raise ValueError(f"Cluster {cluster_id} is in error state.")
        logger.info("Cluster %s is not ready yet...", cluster_id)
        return False

    def _get_addon_install_request_file_path(
        self, addon_id: str, params: Dict[str, Any]
    ) -> str:
        body = self._addon_install_data.copy()
        body["addon"]["id"] = addon_id
        for param_id, param_value in params.items():
            body["parameters"]["items"].append({"id": param_id, "value": param_value})
        return create_json_file(f"{self._data_dir}/install-{addon_id}.json", body)

    def _get_cluster_install_request_file_path(self, cluster_name: str) -> str:
        body = self._cluster_install_data.copy()
        body["name"] = cluster_name
        return create_json_file(f"{self._data_dir}/install-{cluster_name}.json", body)

    def _install_ocm(self) -> None:
        ocm_file = f"{self._bin_dir}/ocm"
        if not os.path.exists(f"{self._bin_dir}/ocm"):
            ocm_url = (
                "https://github.com/openshift-online/ocm-cli/releases/"
                f"download/{env('OCM_VERSION')}/ocm-linux-amd64"
            )
            download_file(ocm_url, ocm_file)

        os.chmod(ocm_file, 0o755)
