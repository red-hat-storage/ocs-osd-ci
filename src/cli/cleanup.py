#!/usr/bin/env python3

import logging
import sys

from src.service.cluster import ClusterService

logger = logging.getLogger()


def main() -> int:
    logger.info("Cleaning up...")
    cluster_service = ClusterService()

    cluster_service.uninstall_all_clusters()

    logger.info("Cleanup completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
