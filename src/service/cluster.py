import json
import logging
import os
from typing import Any, Dict

from src.util.util import create_json_file, download_file, env, run_cmd

logger = logging.getLogger()


class ClusterService:
    _bin_dir: str = os.path.abspath(os.path.expanduser("~/bin"))
    _data_dir: str
    _install_cluster_template: Dict[str, Any] = {
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

    def install(self, name: str) -> str:
        body_file = self._gen_install_request_body(name)
        cluster_info = run_cmd(
            ["ocm", "post", "/api/clusters_mgmt/v1/clusters", "--body", body_file]
        )
        if not cluster_info.stdout:
            raise ValueError("No cluster info received.")
        cluster = json.loads(cluster_info.stdout)
        return cluster["id"]

    def _gen_install_request_body(self, name: str) -> str:
        body = self._install_cluster_template.copy()
        body["name"] = name
        return create_json_file(f"{self._data_dir}/install-{name}.json", body)

    def _install_ocm(self) -> None:
        ocm_file = f"{self._bin_dir}/ocm"
        if not os.path.exists(f"{self._bin_dir}/ocm"):
            ocm_url = (
                "https://github.com/openshift-online/ocm-cli/releases/"
                f"download/{env('OCM_VERSION')}/ocm-linux-amd64"
            )
            download_file(ocm_url, ocm_file)

        os.chmod(ocm_file, 0o755)
