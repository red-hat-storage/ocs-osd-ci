#!/usr/bin/env python3

import logging
import sys

from src.service.aws import AWSService
from src.service.cluster import ClusterService
from src.util.util import env

logger = logging.getLogger()


def main() -> int:
    logger.info("CHAOS testing: setting up...")
    cluster_service = ClusterService()

    # Create provider cluster.
    provider_cluster_name = env("PROVIDER_CLUSTER_NAME")
    provider_cluster_id = cluster_service.install(provider_cluster_name)
    logger.info("PROVIDER CLUSTER ID: %s", provider_cluster_id)

    # Create consumer cluster.
    consumer_cluster_name = env("CONSUMER_CLUSTER_NAME")
    consumer_cluster_id = cluster_service.install(consumer_cluster_name)
    logger.info("CONSUMER CLUSTER ID: %s", consumer_cluster_id)

    # Add inbound rules.
    cluster_service.wait_for_cluster_ready(provider_cluster_id)
    aws_service = AWSService()
    aws_service.add_provider_addon_inbound_rules(provider_cluster_name)

    logger.info("CHAOS testing completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
