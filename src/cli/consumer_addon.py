#!/usr/bin/env python3

import logging
import sys

from src.service.aws import AWSService
from src.service.cluster import AddonId, ClusterService
from src.util.util import env

logger = logging.getLogger()


def main() -> int:
    logger.info("Starting consumer addon installation...")
    cluster_service = ClusterService()

    # Create provider cluster.
    provider_cluster_name = env(
        "PROVIDER_CLUSTER_NAME",
        default=ClusterService.random_cluster_name(prefix="chaos-p"),
    )
    logger.info("PROVIDER CLUSTER NAME: %s", provider_cluster_name)
    provider_cluster_id = cluster_service.install(provider_cluster_name)
    logger.info("PROVIDER CLUSTER ID: %s", provider_cluster_id)

    # Add inbound rules required for provider addon installation.
    cluster_service.wait_for_cluster_ready(provider_cluster_id)
    aws_service = AWSService()
    aws_service.add_provider_addon_inbound_rules(provider_cluster_name)

    # Create consumer cluster.
    provider_cluster_subnet_info = aws_service.get_subnets_info(provider_cluster_name)
    consumer_cluster_name = env(
        "CONSUMER_CLUSTER_NAME",
        default=ClusterService.random_cluster_name(prefix="chaos-c"),
    )
    logger.info("CONSUMER CLUSTER NAME: %s", consumer_cluster_name)
    consumer_cluster_id = cluster_service.install(
        cluster_name=consumer_cluster_name,
        subnets_ids=provider_cluster_subnet_info.subnet_ids,
        availability_zones=provider_cluster_subnet_info.availability_zones,
    )
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

    # Share the provider kubeconfig so ocs-monkey can identify the provider cluster.
    cluster_service.share_kubeconfig_file(
        provider_cluster_id, "provider-kubeconfig.yaml"
    )

    # Install consumer addon.
    cluster_service.wait_for_cluster_ready(consumer_cluster_id)
    consumer_addon_params = {
        "storage-provider-endpoint": cluster_service.get_addon_ocs_provider_storage_endpoint(
            provider_cluster_id
        ),
        "onboarding-ticket": cluster_service.get_consumer_onboarding_ticket(),
    }
    cluster_service.install_addon(
        consumer_cluster_id, AddonId.CONSUMER.value, consumer_addon_params
    )
    cluster_service.wait_for_addon_ready(consumer_cluster_id, AddonId.CONSUMER)

    # Share the consumer kubeconfig so ocs-monkey can identify the consumer cluster.
    cluster_service.share_kubeconfig_file(
        consumer_cluster_id, "consumer-kubeconfig.yaml"
    )

    logger.info("Consumer addon installation completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
