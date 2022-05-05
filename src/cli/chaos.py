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
    provider_cluster_name = env("PROVIDER_CLUSTER_NAME")
    provider_cluster_id = cluster_service.install(provider_cluster_name)
    logger.info("PROVIDER CLUSTER ID: %s", provider_cluster_id)

    # Create consumer cluster.
    consumer_cluster_name = env("CONSUMER_CLUSTER_NAME")
    consumer_cluster_id = cluster_service.install(consumer_cluster_name)
    logger.info("CONSUMER CLUSTER ID: %s", consumer_cluster_id)

    # Add inbound rules required for provider addon installation.
    cluster_service.wait_for_cluster_ready(provider_cluster_id)
    aws_service = AWSService()
    aws_service.add_provider_addon_inbound_rules(provider_cluster_name)

    # Install provider addon.
    provider_addon_params = {
        "size": "20",
        "onboarding-validation-key": env("ONBOARDING_PUBLIC_KEY"),
    }
    cluster_service.install_addon(
        provider_cluster_id, AddonId.PROVIDER.value, provider_addon_params
    )
    cluster_service.wait_for_addon_ready(provider_cluster_id, AddonId.PROVIDER.value)

    # Install consumer addon.
    # @TODO: obtain onboarding ticket.
    onboarding_ticket = ""
    consumer_addon_params = {
        "size": "1",
        "unit": "Ti",
        "storage-provider-endpoint": cluster_service.get_storage_provider_endpoint(
            provider_cluster_id
        ),
        "onboarding-ticket": onboarding_ticket,
    }
    cluster_service.install_addon(
        consumer_cluster_id, AddonId.CONSUMER.value, consumer_addon_params
    )
    cluster_service.wait_for_addon_ready(consumer_cluster_id, AddonId.CONSUMER.value)

    # @TODO: run ocs-monkey.

    logger.info("CHAOS testing completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
