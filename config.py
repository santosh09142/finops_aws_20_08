# config.py

AWS_REGION = ["us-east-1"]

CORE_SERVICES = [
    "s3",
    "ec2",
    "lambda"
]

SERVICE_MAP = {
    # Use module-qualified class references so they can be imported dynamically
    "s3": "core.s3_service:S3Service",
    "ec2": "core.ec2_service:EC2Service",
}

AWS_PROFILE = "master9account"
ASSUME_ROLE_NAME = "FinOpsReadWriteRole"
ENABLE_SERVICESNOW = False
LOG_LEVEL = "INFO"

#Free metric capture
METRIC_NAME = 'CPUUtilization'
DAYS_LIST = [30, 60]
# End-of-file (EOF)
