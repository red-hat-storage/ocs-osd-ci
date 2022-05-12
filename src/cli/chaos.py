#!/usr/bin/env python3

import logging
import sys

from src.service.aws import AWSService
from src.service.cluster import AddonId, ClusterService
from src.util.util import env

logger = logging.getLogger()


def main() -> int:
    logger.info("CHAOS testing: setting up...")
    cluster_service = ClusterService()

    # Create provider cluster.
    provider_cluster_name = env(
        "PROVIDER_CLUSTER_NAME",
        default=ClusterService.random_cluster_name(prefix="chaos-p"),
    )
    logger.info("PROVIDER CLUSTER NAME: %s", provider_cluster_name)
    provider_cluster_id = cluster_service.install(provider_cluster_name)["id"]
    logger.info("PROVIDER CLUSTER ID: %s", provider_cluster_id)

    # Add inbound rules required for provider addon installation.
    cluster_service.wait_for_cluster_ready(provider_cluster_id)
    aws_service = AWSService()
    aws_service.add_provider_addon_inbound_rules(provider_cluster_name)

    # Create consumer cluster.
    provider_cluster_subnet_ids = aws_service.get_subnets(provider_cluster_name)
    logger.info("PROVIDER CLUSTER SUBNET IDS: %s", provider_cluster_subnet_ids)
    consumer_cluster_name = env(
        "CONSUMER_CLUSTER_NAME",
        default=ClusterService.random_cluster_name(prefix="chaos-c"),
    )
    logger.info("CONSUMER CLUSTER NAME: %s", consumer_cluster_name)
    consumer_cluster_id = cluster_service.install(
        consumer_cluster_name, provider_cluster_subnet_ids
    )["id"]
    logger.info("CONSUMER CLUSTER ID: %s", consumer_cluster_id)

    # Install provider addon.
    provider_addon_params = {
        "size": "20",
        "onboarding-validation-key": env("ONBOARDING_PUBLIC_KEY"),
    }
    cluster_service.install_addon(
        provider_cluster_id, AddonId.PROVIDER.value, provider_addon_params
    )
    cluster_service.wait_for_addon_ready(provider_cluster_id, AddonId.PROVIDER)

    # Install consumer addon.
    consumer_addon_params = {
        "size": "1",
        "unit": "Ti",
        "storage-provider-endpoint": cluster_service.get_addon_ocs_provider_storage_endpoint(
            provider_cluster_id
        ),
        "onboarding-ticket": cluster_service.get_consumer_onboarding_ticket(),
    }
    cluster_service.install_addon(
        consumer_cluster_id, AddonId.CONSUMER.value, consumer_addon_params
    )
    cluster_service.wait_for_addon_ready(consumer_cluster_id, AddonId.CONSUMER)

    # @TODO: run ocs-monkey.

    logger.info("CHAOS testing completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
