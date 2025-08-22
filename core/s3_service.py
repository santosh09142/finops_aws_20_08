# /core/s3_service.py
"""Module to interact with AWS S3 buckets."""
from utils.logger import logger
from core.service_base import ServiceBase
from db.models import S3Buckets

class S3Service(ServiceBase):
    """Service to interact with AWS S3 buckets."""
    def __init__(self, session, account_id):
        self.client_s3 = session.client('s3')
        self.account_id = account_id
    
    def fetch_properties(self):
        """Fetches S3 bucket properties for the given account and region.

        Returns:
            list: A list of S3 bucket properties or an empty list if an error occurs.
        """
        try:
            response = self.client_s3.list_buckets()
            logger.info("Fetched S3 properties for account %s in region %s", self.account_id, self.client_s3.meta.region_name)
            for bucket in response.get('Buckets', []):
                bucket_versioning = self.client_s3.get_bucket_versioning(Bucket=bucket['Name'])
                print(bucket_versioning)
            #  I want to print buckets name
            print("Buckets:", [bucket['Name'] for bucket in response.get('Buckets', [])])
            return response.get('Buckets', [])
        except Exception as e:
            logger.error("Error fetching S3 properties: {str(%s)}", e)
            return []
# This code defines a service to interact with AWS S3 buckets, similar to the EC2Service.
            