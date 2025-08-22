# /core/ec2_service.py
"""Module to interact with AWS EC2 instances."""

from utils.logger import logger
from core.service_base import ServiceBase
from datetime import datetime, timedelta, timezone
from db.init_db import Session
from db.models import EC2Instance
import inflection
import re
import config

db_session = Session()

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
                            'instance_id': instance_id,
                            'creation_time': instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] if instance['NetworkInterfaces'] and instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] < instance['LaunchTime'] else 'N/A',
                            'instance_type': instance['InstanceType'],
                            'state': instance['State']['Name'],
                            'state_code': instance['State']['Code'],
                            'last_transition_date': last_transition_date,
                            'aging': (datetime.now(timezone.utc) - older_date).days,
                            'last_transition_reason': last_transition_reason,
                            'launch_update_time': instance['LaunchTime'],
                            'availability_zone': instance['Placement']['AvailabilityZone'],
                            'mac_address': instance['NetworkInterfaces'][0]['MacAddress'] if instance['NetworkInterfaces'] else 'N/A',
                            'network_interface_id': instance['NetworkInterfaces'][0]['NetworkInterfaceId'] if instance['NetworkInterfaces'] else 'N/A',
                            'account_id': instance['NetworkInterfaces'][0]['OwnerId'] if instance['NetworkInterfaces'] else instance.get('OwnerId', 'N/A'),
                            'private_ip_address': instance.get('PrivateIpAddress', 'N/A'),
                            'public_ip_address': instance.get('PublicIpAddress', 'N/A'),
                            'network_interface_attachment_id': instance['NetworkInterfaces'][0]['Attachment']['AttachmentId'] if instance['NetworkInterfaces'] else 'N/A',
                            # 'UsageOperationUpdateTime': instance.get('UsageOperationUpdateTime', 'N/A'),
                            'usage_operation': instance.get('UsageOperation', 'N/A'),
                            'platform': instance.get('PlatformDetails', 'N/A'),
                            'architecture': instance['Architecture'],
                            'subnet_id': instance.get('SubnetId', 'N/A'),
                            'vpc_id': instance.get('VpcId','N/A'),
                            'image_id': instance.get('ImageId','N/A'),
                            'security_groups': [group['GroupName'] for group in instance['SecurityGroups']],
                            # 'Tags': [{tag['Key']: tag['Value']} for tag in instance.get('Tags', [])],
                            'tag_properties' :  {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                            'instance_name': next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'N/A'),
                            'region': self.region,
                            # 'DeviceName': instance['BlockDeviceMappings'][0]['DeviceName'] if instance['BlockDeviceMappings'] else 'N/A',
                            'root_device_type': instance['RootDeviceType'],
                            # 'VolumeId': instance['BlockDeviceMappings'][0]['Ebs']['VolumeId'] if instance['BlockDeviceMappings'] else 'N/A',
                            'volume_id': vol_Id,
                            'volume_type': vol_type,
                            'volume_size': total_volume_size_sum,
                            'volume_iops': vol_status,
                            'volume_instance_name': vol_instance,
                            'volume_device': vol_device,
                            'volume_status': instance['BlockDeviceMappings'][0]['Ebs'].get('Status', 'N/A') if instance['BlockDeviceMappings'] else 'N/A',
                            'volume_encrypted': instance['BlockDeviceMappings'][0]['Ebs'].get('Encrypted', 'False') if instance['BlockDeviceMappings'] else 'False',
                            'volume_attach_time': instance['BlockDeviceMappings'][0]['Ebs']['AttachTime'] if instance['BlockDeviceMappings'] else 'N/A',
                            'volume_delete_on_termination': instance['BlockDeviceMappings'][0]['Ebs']['DeleteOnTermination'] if instance['BlockDeviceMappings'] else 'N/A',
                            # 'VolumeTags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                            'network_attach_time': instance['NetworkInterfaces'][0]['Attachment']['AttachTime'] if instance['NetworkInterfaces'] else 'N/A',
                            'ebs_optimized': instance.get('EbsOptimized', 'N/A'),
                            'monitoring_state': instance['Monitoring']['State'],
                            'private_dns_name': instance.get('PrivateDnsName', 'N/A'),
                            'public_dns_name': instance.get('PublicDnsName', 'N/A'),
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
                            'thirty_days_avg': round(float(aggregated_metrics[30]['Average']), 2) if aggregated_metrics[30]['Average'] != 'N/A' else 'N/A',
                            'thirty_days_max': round(float(aggregated_metrics[30]['Maximum']), 2) if aggregated_metrics[30]['Maximum'] != 'N/A' else 'N/A',
                            'thirty_days_min': round(float(aggregated_metrics[30]['Minimum']), 2) if aggregated_metrics[30]['Minimum'] != 'N/A' else 'N/A',
                            'sixty_days_avg': round(float(aggregated_metrics[60]['Average']), 2) if aggregated_metrics[60]['Average'] != 'N/A' else 'N/A',
                            'sixty_days_max': round(float(aggregated_metrics[60]['Maximum']), 2) if aggregated_metrics[60]['Maximum'] != 'N/A' else 'N/A',
                            'sixty_days_min': round(float(aggregated_metrics[60]['Minimum']), 2) if aggregated_metrics[60]['Minimum'] != 'N/A' else 'N/A',
                        }
                        sync_ec2instance_to_db(instance_props=instance_info)
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

def sync_ec2instance_to_db_test(instance_props):
    """Syncs EC2 instance data to the database."""
    instance_obj = db_session.query(EC2Instance).filter_by(instance_id=instance_props['instanceid']).first()
    print(instance_props["tags"])
    print(type(instance_props["tags"]))
    if not instance_obj:
        instance_obj = EC2Instance(
            instance_id=instance_props['instanceid'],
            creation_time=instance_props['creationtime'],
            instance_type=instance_props['instancetype'],
            state=instance_props['state'],
            state_code=instance_props['statecode'],
            last_transition_date=instance_props['lasttransitiondate'],
            aging=instance_props['aging'],
            last_transition_reason=instance_props['lasttransitionreason'],
            launch_update_time=instance_props['launchupdatetime'],
            availability_zone=instance_props['availabilityzone'],
            mac_address=instance_props['macaddress'],
            network_interface_id=instance_props['networkinterfaceid'],
            account_id=instance_props['accountid'],
            private_ip_address=instance_props['privateipaddress'],
            public_ip_address=instance_props['publicipaddress'],
            network_interface_attachment_id=instance_props['networkinterfaceattachmentid'],
            usage_operation=instance_props['usageoperation'],
            platform=instance_props['platform'],
            architecture=instance_props['architecture'],
            subnet_id=instance_props['subnetid'],
            vpc_id=instance_props['vpcid'],
            image_id=instance_props['imageid'],
            security_groups=str(instance_props['securitygroups']),
            tag_properties=str(instance_props.get('tags', {})),
            instance_name=instance_props.get('instancename', 'N/A'),
            region=instance_props.get('region', 'N/A'),
            root_device_type=instance_props.get('rootdevicetype', 'N/A'),
            volume_id=instance_props.get('volumeid', 'N/A'),
            volume_type=instance_props.get('volumetype', 'N/A'),
            volume_size=instance_props.get('volumesize', 0),
            volume_iops=instance_props.get('volumeiops', 0),
            volume_instance_name=instance_props.get('volumeinstancename', 'N/A'),
            volume_device=instance_props.get('volumedevice', 'N/A'),
            volume_status=instance_props.get('volumestatus', 'N/A'),
            volume_encrypted=instance_props.get('volumeencrypted', False),
            volume_attach_time=instance_props.get('volumeattachtime', None),
            volume_delete_on_termination=instance_props.get('volumedeleteontermination', False),
            network_attach_time=instance_props.get('networkattachtime', None),
            ebs_optimized=instance_props.get('ebsoptimized', False),
            monitoring_state=instance_props.get('monitoring', 'N/A'),
        )
        db_session.add(instance_obj)
        db_session.commit()
    else:
        model_columns = set(c.name for c in instance_obj.__table__.columns)
        for key, value in instance_props.items():
            normalized_key = inflection.underscore(key)
            if normalized_key in model_columns:
                setattr(instance_obj, normalized_key, value)
        db_session.commit()
                
    return instance_obj

def sync_ec2instance_to_db(instance_props):
    """Syncs EC2 instance data to the database."""
    instance_obj = db_session.query(EC2Instance).filter_by(instance_id=instance_props['instance_id']).first()
    model_columns = set(c.name for c in EC2Instance.__table__.columns)
    updated = False

    if not instance_obj:
        # Create new record
        instance_obj = EC2Instance(**{k: v for k, v in instance_props.items() if k in model_columns})
        db_session.add(instance_obj)
        db_session.commit()
    else:
        # Update only changed fields
        for key, value in instance_props.items():
            if key in model_columns:
                current_value = getattr(instance_obj, key)
                if current_value != value:
                    setattr(instance_obj, key, value)
                    updated = True
        if updated:
            db_session.commit()
    return instance_obj


# end of file
