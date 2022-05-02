#!/usr/bin/env python3

import logging
import sys

from src.service.cluster import ClusterService
from src.util.util import env

logger = logging.getLogger()


def main() -> int:
    logger.info("CHAOS testing: setting up...")
    cluster_service = ClusterService()

    provider_cluster_id = cluster_service.install(env("PROVIDER_CLUSTER_NAME"))
    logger.info("PROVIDER CLUSTER ID: %s", provider_cluster_id)

    cluster_service.wait_for_cluster_ready(provider_cluster_id)

    logger.info("CHAOS testing completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
