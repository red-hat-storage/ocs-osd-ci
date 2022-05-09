import logging

import boto3
from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import (
    AuthorizeSecurityGroupIngressResultTypeDef,
    DescribeSecurityGroupsResultTypeDef,
    DescribeSubnetsResultTypeDef,
)

from src.util.util import env

logger = logging.getLogger()


class AWSService:
    _ec2_client: EC2Client

    def __init__(self) -> None:
        self._ec2_client = boto3.client(
            "ec2",
            aws_access_key_id=env("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=env("AWS_SECRET_ACCESS_KEY"),
            region_name=env("AWS_REGION"),
        )

    def add_provider_addon_inbound_rules(self, cluster_name: str) -> None:
        describe_result: DescribeSecurityGroupsResultTypeDef = (
            self._ec2_client.describe_security_groups(
                Filters=[
                    {
                        "Name": "tag:Name",
                        "Values": [
                            f"{cluster_name}-*-worker-sg",
                        ],
                    },
                ]
            )
        )
        sg_group_id = describe_result["SecurityGroups"][0]["GroupId"]

        authorize_result: AuthorizeSecurityGroupIngressResultTypeDef = (
            self._ec2_client.authorize_security_group_ingress(
                GroupId=sg_group_id,
                IpPermissions=[
                    {
                        "FromPort": 6800,
                        "ToPort": 7300,
                        "IpProtocol": "tcp",
                        "IpRanges": [
                            {"CidrIp": "10.0.0.0/16", "Description": "Ceph OSDs"},
                        ],
                    },
                    {
                        "FromPort": 3300,
                        "ToPort": 3300,
                        "IpProtocol": "tcp",
                        "IpRanges": [
                            {"CidrIp": "10.0.0.0/16", "Description": "Ceph MONs rule1"}
                        ],
                    },
                    {
                        "FromPort": 6789,
                        "ToPort": 6789,
                        "IpProtocol": "tcp",
                        "IpRanges": [
                            {"CidrIp": "10.0.0.0/16", "Description": "Ceph MONs rule2"},
                        ],
                    },
                    {
                        "FromPort": 9283,
                        "ToPort": 9283,
                        "IpProtocol": "tcp",
                        "IpRanges": [
                            {"CidrIp": "10.0.0.0/16", "Description": "Ceph Manager"},
                        ],
                    },
                    {
                        "FromPort": 31659,
                        "ToPort": 31659,
                        "IpProtocol": "tcp",
                        "IpRanges": [
                            {"CidrIp": "10.0.0.0/16", "Description": "API Server"},
                        ],
                    },
                ],
            )
        )
        if not authorize_result["Return"]:
            logger.error(authorize_result)
            raise RuntimeError("EC2: error while adding inbound rules.")

    def get_subnets(self, cluster_name: str) -> list[str]:
        result: DescribeSubnetsResultTypeDef = self._ec2_client.describe_subnets(
            Filters=[
                {"Name": "tag:Name", "Values": [f"{cluster_name}-*"]},
            ]
        )
        return [subnet["SubnetId"] for subnet in result["Subnets"]]
