# /core/ec2_service.py
"""Module to interact with AWS EC2 instances."""

from utils.logger import logger
from core.service_base import ServiceBase
from datetime import datetime, timedelta, timezone

class EC2Service(ServiceBase):
    """Service to interact with AWS EC2 instances."""
    def __init__(self, session, region, account_id):
        self.client = session.client('ec2', region_name=region)
        self.cw_client = session.client('cloudwatch', region_name=region)
        
        self.account_id = account_id
    
    def fetch_properties(self):
        """Fetches EC2 properties for the given account and region.

        Returns:
            list: A list of EC2 properties or an empty list if an error occurs.
        """
        try:
            # res = self.client.describe_instances()
            res = self.client.get_paginator('describe_instances')
            logger.info("Fetched EC2 properties for account %s in region %s", self.account_id, self.client.meta.region_name)
            return "respnse"   #response('Reservations',[])""
        except Exception as e:
            logger.error("Error fetching EC2 properties: {str(%s)}", e)
            return []
    
    def get_aggregated_metric(cw_client, instance_id, metric_name, statistic, days, region):
        """
        Retrieve an aggregated CloudWatch metric for a given EC2 instance over a specified number of days.
        
        Args:
        instance_id (str): The ID of the EC2 instance.
        metric_name (str): The name of the metric (e.g., 'CPUUtilization').
        statistic (str): The statistic to retrieve ('Average', 'Maximum', 'Minimum').
        days (int): The time window in days over which to aggregate the data.
        region (str): AWS region.
        
        Returns:
        The aggregated value (float) for the requested statistic or None if no data is found.
        """
        # cloudwatch = cw_client('cloudwatch', region_name=region)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        period = int((end_time - start_time).total_seconds())  # Total seconds for the entire window

        try:
            response = cw_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'InstanceId',
                        'Value': instance_id
                    },
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=[statistic]
            )
        except Exception as e:
            print(f"Error retrieving metric {metric_name} for {instance_id} over {days} days: {e}")
            return None

        datapoints = response.get('Datapoints', [])
        if datapoints:
            # We expect a single data point since the period equals the full interval.
            return datapoints[0].get(statistic)
        else:
            # print(f"No datapoints returned for metric {metric_name} over {days} days.")
            return None
    
    
    