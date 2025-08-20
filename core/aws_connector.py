# /core/aws_connector.py
"""Module to handle AWS connections and role assumptions."""

from typing import Optional
import boto3
from utils.logger import logger


class AWSConnector:
    """A class to handle AWS connections and role assumptions."""

    def __init__(self, region_name: Optional[str] = None) -> None:
        """Initialize the AWS Connector with a specific region."""
        self.region_name = region_name

    def get_session(self, profile_name: Optional[str] = None):
        """Create a boto3 session with the specified profile and region."""
        return boto3.Session(
            profile_name=profile_name,
            region_name=self.region_name
        )

    def assume_role(self, account_id: str, role_name: str, session=None):
        """Assumes a role in the specified AWS account."""
        if not session:
            session = boto3.Session(region_name=self.region_name)
        sts_client = session.client('sts')
        try:
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
            logger.info("Assuming role %s in account %s", role_name,
                        account_id)
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="FinOpsSession"
            )
            credentials = response['Credentials']
            logger.info("Assumed role %s successfully", role_name)
            return boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region_name
            )
        except Exception as e:
            logger.error("Failed to assume role %s in account %s: %s",
                         role_name, account_id, e)
            return None
