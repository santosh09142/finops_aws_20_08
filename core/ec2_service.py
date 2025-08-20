# /core/ec2_service.py
"""Module to interact with AWS EC2 instances."""

from utils.logger import logger
from core.service_base import ServiceBase
from datetime import datetime, timedelta, timezone
import re
import config

class EC2Service(ServiceBase):
    """Service to interact with AWS EC2 instances."""
    def __init__(self, session, region, account_id):
        self.client = session.client('ec2', region_name=region)
        self.cw_client = session.client('cloudwatch', region_name=region)
        self.region = region
        
        self.account_id = account_id
    
    def fetch_properties(self):
        """Fetches EC2 properties for the given account and region.

        Returns:
            list: A list of EC2 properties or an empty list if an error occurs.
        """
        try:
            # res = self.client.describe_instances()
            instances_data = []
            paginator = self.client.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        if len(instance['BlockDeviceMappings']) == 0:
                            volume_status = {
                                'VolumeType': 'N/A',
                                'VolumeIops': 'N/A',
                                'InstanceName': 'N/A',
                                'VolumeDevice': 'N/A',
                                'total_volume_size':  'N/A',
                                'VolumeId': 'N/A',
                            }
                        elif len(instance['BlockDeviceMappings'])  > 1:
                            volume_status = []
                            for vol in instance['BlockDeviceMappings']:
                                data = get_volume_attachment_status(ec2_client=self.client, volume_id=vol['Ebs']['VolumeId'])
                                volume_info = {
                                    'VolumeType': data['VolumeType'],
                                    'VolumeIops': data['VolumeIops'],
                                    'InstanceName': data['InstanceName'],
                                    'VolumeDevice': data['VolumeDevice'],
                                    'total_volume_size':  data['VolumeSize'],
                                    'VolumeId': data['InstanceId'],
                                }
                                volume_status.append(volume_info)
                        else:
                            data = get_volume_attachment_status(ec2_client=self.client, volume_id=instance['BlockDeviceMappings'][0]['Ebs']['VolumeId'])
                            volume_status = {
                                'VolumeType': data['VolumeType'],
                                'VolumeIops': data['VolumeIops'],
                                'InstanceName': data['InstanceName'],
                                'VolumeDevice': data['VolumeDevice'],
                                'total_volume_size':  data['VolumeSize'],
                                'VolumeId': data['InstanceId'],
                                
                            }
                                    
                        # volume_status = get_volume_attachment_status(ec2_client, instance['BlockDeviceMappings'][0]['Ebs']['VolumeId'])
                        # Extract the datetime from the 'StateTransitionReason' string
                        stop_date_str = instance.get('StateTransitionReason', 'N/A')
                        stop_date_match = re.search(r'\((.*?)\)', stop_date_str)
                        last_transition_date = datetime.strptime(stop_date_match.group(1), '%Y-%m-%d %H:%M:%S %Z') if stop_date_match else 'N/A'

                        instance_id = instance['InstanceId']
                        
                        # Retrieve the aggregated metrics for the specified metric (e.g., CPUUtilization).                       
                        aggregated_metrics = collect_metric_aggregates(cw_client=self.cw_client, instance_id=instance_id, metric_name=config.METRIC_NAME, days_list=config.DAYS_LIST, region=self.region)

                        # Determine if the event is manual or system
                        if "User initiated" in stop_date_str:
                            last_transition_reason = "Manual"
                        elif "Server.SpotInstanceTermination" in stop_date_str or "Instance retirement scheduled" in stop_date_str:
                            last_transition_reason = "System"
                        else:
                            last_transition_reason = "Unknown"      
                            
                        if isinstance(volume_status, list):
                            total_volume_size_sum = sum(vol['total_volume_size'] for vol in volume_status)
                            vol_type = volume_status[0]['VolumeType']
                            vol_status = volume_status[0]['VolumeIops']
                            vol_device = ', '.join([vol['VolumeDevice'] for vol in volume_status])
                            vol_instance = volume_status[0]['InstanceName']
                            vol_Id = ', '.join([vol['VolumeId'] for vol in volume_status])
                        else:
                            total_volume_size_sum = volume_status['total_volume_size']
                            vol_type = volume_status['VolumeType']
                            vol_status = volume_status['VolumeIops']
                            vol_device = volume_status['VolumeDevice']
                            vol_instance = volume_status['InstanceName']
                            vol_Id = volume_status['VolumeId']
                            
                        # Determine the older date between LaunchTime and NetworkInterfaces attachment date
                        launch_time = instance['LaunchTime']
                        network_attach_time = instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] if instance['NetworkInterfaces'] else launch_time
                        older_date = min(launch_time, network_attach_time)
                        
                        
                        
                        instance_info = {
                            'InstanceId': instance_id,
                            'CreationTime': instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] if instance['NetworkInterfaces'] and instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] < instance['LaunchTime'] else '',
                            'InstanceType': instance['InstanceType'],
                            'State': instance['State']['Name'],
                            'StateCode': instance['State']['Code'],
                            'LastTransitionDate': last_transition_date,
                            'Aging': (datetime.now(timezone.utc) - older_date).days,
                            'LastTransitionReason': last_transition_reason,
                            'Launch_update_Time': instance['LaunchTime'],
                            'AvailabilityZone': instance['Placement']['AvailabilityZone'],
                            'MacAddress': instance['NetworkInterfaces'][0]['MacAddress'] if instance['NetworkInterfaces'] else 'N/A',
                            'NetworkInterfaceId': instance['NetworkInterfaces'][0]['NetworkInterfaceId'] if instance['NetworkInterfaces'] else 'N/A',
                            'AccountID': instance['NetworkInterfaces'][0]['OwnerId'] if instance['NetworkInterfaces'] else instance.get('OwnerId', 'N/A'),
                            'PrivateIpAddress': instance.get('PrivateIpAddress', 'N/A'),
                            'PublicIpAddress': instance.get('PublicIpAddress', 'N/A'),
                            'NetworkInterfaceAttachmentId': instance['NetworkInterfaces'][0]['Attachment']['AttachmentId'] if instance['NetworkInterfaces'] else 'N/A',
                            # 'UsageOperationUpdateTime': instance.get('UsageOperationUpdateTime', 'N/A'),
                            'UsageOperation': instance.get('UsageOperation', 'N/A'),
                            'Platform': instance.get('PlatformDetails', 'N/A'),
                            'Architecture': instance['Architecture'],
                            'SubnetId': instance.get('SubnetId', 'N/A'),
                            'VpcId': instance.get('VpcId','N/A'),
                            'ImageId': instance.get('ImageId','N/A'),
                            'SecurityGroups': [group['GroupName'] for group in instance['SecurityGroups']],
                            # 'Tags': [{tag['Key']: tag['Value']} for tag in instance.get('Tags', [])],
                            'Tags' : {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                            'InstanceName': next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'N/A'),
                            'region': self.region,
                            # 'DeviceName': instance['BlockDeviceMappings'][0]['DeviceName'] if instance['BlockDeviceMappings'] else 'N/A',
                            'RootDeviceType': instance['RootDeviceType'],
                            # 'VolumeId': instance['BlockDeviceMappings'][0]['Ebs']['VolumeId'] if instance['BlockDeviceMappings'] else 'N/A',
                            'VolumeId': vol_Id,
                            'VolumeType': vol_type,
                            'VolumeSize': total_volume_size_sum,
                            'Volume_IOPs': vol_status,
                            'Volume_InstanceName': vol_instance,
                            'VolumeDevice': vol_device,
                            'VolumeStatus': instance['BlockDeviceMappings'][0]['Ebs'].get('Status', 'N/A') if instance['BlockDeviceMappings'] else 'N/A',
                            'VolumeEncrypted': instance['BlockDeviceMappings'][0]['Ebs'].get('Encrypted', 'N/A') if instance['BlockDeviceMappings'] else 'N/A',
                            'VolumeAttachTime': instance['BlockDeviceMappings'][0]['Ebs']['AttachTime'] if instance['BlockDeviceMappings'] else 'N/A',
                            'VolumeDeleteOnTermination': instance['BlockDeviceMappings'][0]['Ebs']['DeleteOnTermination'] if instance['BlockDeviceMappings'] else 'N/A',
                            # 'VolumeTags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                            'NetworkAttachTime': instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] if instance['NetworkInterfaces'] else 'N/A',
                            'EbsOptimized': instance.get('EbsOptimized', 'N/A'),
                            'Monitoring': instance['Monitoring']['State'],
                            'PrivateDnsName': instance.get('PrivateDnsName', 'N/A'),
                            'PublicDnsName': instance.get('PublicDnsName', 'N/A'),
                            # '15_days_avg': aggregated_metrics[15]['Average'],
                            # '15_days_max': aggregated_metrics[15]['Maximum'],
                            # '15_days_min': aggregated_metrics[15]['Minimum'],
                            # '30_days_avg': aggregated_metrics[30]['Average'],
                            # '30_days_max': aggregated_metrics[30]['Maximum'],
                            # '30_days_min': aggregated_metrics[30]['Minimum'],
                            # '60_days_avg': aggregated_metrics[60]['Average'],
                            # '60_days_max': aggregated_metrics[60]['Maximum'],
                            # '60_days_min': aggregated_metrics[60]['Minimum'],
                            # '15_days_avg': round(float(aggregated_metrics[15]['Average']), 2) if aggregated_metrics[15]['Average'] != 'N/A' else 'N/A',
                            # '15_days_max': round(float(aggregated_metrics[15]['Maximum']), 2) if aggregated_metrics[15]['Maximum'] != 'N/A' else 'N/A',
                            # '15_days_min': round(float(aggregated_metrics[15]['Minimum']), 2) if aggregated_metrics[15]['Minimum'] != 'N/A' else 'N/A',
                            '30_days_avg': round(float(aggregated_metrics[30]['Average']), 2) if aggregated_metrics[30]['Average'] != 'N/A' else 'N/A',
                            '30_days_max': round(float(aggregated_metrics[30]['Maximum']), 2) if aggregated_metrics[30]['Maximum'] != 'N/A' else 'N/A',
                            '30_days_min': round(float(aggregated_metrics[30]['Minimum']), 2) if aggregated_metrics[30]['Minimum'] != 'N/A' else 'N/A',
                            '60_days_avg': round(float(aggregated_metrics[60]['Average']), 2) if aggregated_metrics[60]['Average'] != 'N/A' else 'N/A',
                            '60_days_max': round(float(aggregated_metrics[60]['Maximum']), 2) if aggregated_metrics[60]['Maximum'] != 'N/A' else 'N/A',
                            '60_days_min': round(float(aggregated_metrics[60]['Minimum']), 2) if aggregated_metrics[60]['Minimum'] != 'N/A' else 'N/A',
                        }
                        instances_data.append(instance_info)
            logger.info("Fetched EC2 properties for account %s in region %s", self.account_id, self.client.meta.region_name)
            return instances_data   #response('Reservations',[])""
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

def collect_metric_aggregates(cw_client, instance_id, metric_name, days_list, region):
    """
    Collect aggregated metric data for multiple durations and return a data.

    Args:
    instance_id (str): The ID of the EC2 instance.
    metric_name (str): The metric to collect (e.g., 'CPUUtilization').
    days_list (list): A list of durations in days (e.g., [15, 30, 60]).
    region (str): AWS region.
    
    Returns:
    dict: A dictionary where each key is the duration in days and the value is another
            dictionary containing 'Average', 'Maximum', and 'Minimum' for that period.
    """
    aggregated_data = {}
    for days in days_list:
        period_data = {}
        for stat in ['Average', 'Maximum', 'Minimum']:
            value = get_aggregated_metric(cw_client, instance_id, metric_name, stat, days, region)
            period_data[stat] = value if value is not None else 'N/A'
        aggregated_data[days] = period_data
    return aggregated_data

def get_volume_attachment_status(ec2_client, volume_id):
        """Check if a volume is attached to any instance and retrieve additional volume details"""
        try:
            response = ec2_client.describe_volumes(VolumeIds=[volume_id])
            if response["Volumes"]:
                volume = response["Volumes"][0]
                volume_state = volume.get("State", "Unknown")
                volume_type = volume.get("VolumeType", "Unknown")
                volume_size = volume.get("Size", "Unknown")
                volume_device = volume.get("Attachments", [{}])[0].get("Device", "Unknown")
                volume_attachments_state = volume.get("Attachments", [{}])[0].get("State", "Unknown")
                volume_iops = volume.get("Iops", "Unknown")
                instance_id = volume.get("Attachments", [{}])[0].get("InstanceId", "Detached")
                
                if instance_id != "Detached":
                    instance_response = ec2_client.describe_instances(InstanceIds=[instance_id])
                    instance = instance_response["Reservations"][0]["Instances"][0]
                    instance_type = instance.get("InstanceType", "Unknown")
                    instance_name = next((tag["Value"] for tag in instance.get("Tags", []) if tag["Key"] == "Name"), "Unknown")
                    instance_state = instance.get("State", {}).get("Name", "Unknown")
                    private_ip = instance.get("PrivateIpAddress", "Unknown")
                    is_storage = instance.get("RootDeviceType", "Unknown") == "ebs"
                else:
                    instance_type = "Detached"
                    instance_name = "Detached"
                    instance_state = "Detached"
                    private_ip = "Detached"
                    is_storage = False
                
                return {
                    "InstanceId": instance_id,
                    "VolumeState": volume_state,
                    "VolumeType": volume_type,
                    "VolumeSize": volume_size,
                    "VolumeDevice": volume_device,
                    "VolumeAttachmentsState": volume_attachments_state,
                    "VolumeIops": volume_iops,
                    "InstanceType": instance_type,
                    "InstanceName": instance_name,
                    "InstanceState": instance_state,
                    "PrivateIp": private_ip,
                    "IsStorage": is_storage
                }
            return {
                "InstanceId": "Detached",
                "VolumeState": "Unknown",
                "VolumeType": "Unknown",
                "VolumeSize": "Unknown",
                "VolumeDevice": "Unknown",
                "VolumeAttachmentsState": "Unknown",
                "VolumeIops": "Unknown",
                "InstanceType": "Detached",
                "InstanceName": "Detached",
                "InstanceState": "Detached",
                "PrivateIp": "Detached",
                "IsStorage": False
            }
        except Exception as e:
            return {
                "InstanceId": f"Error: {e}",
                "VolumeState": "Error",
                "VolumeType": "Error",
                "VolumeSize": "Error",
                "VolumeDevice": "Error",
                "VolumeAttachmentsState": "Error",
                "VolumeIops": "Error",
                "InstanceType": "Error",
                "InstanceName": "Error",
                "InstanceState": "Error",
                "PrivateIp": "Error",
                "IsStorage": "Error"
            }


# end of file    
    