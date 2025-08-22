from sqlalchemy import Column, Integer, String, ForeignKey, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    account_id = Column(String(32), unique=True, nullable=False)
    account_name = Column(String(128))
    email = Column(String(128))
    org_unit = Column(String(256))
    created_at = Column(TIMESTAMP, server_default=func.now())
    
    instances = relationship("EC2Instance", back_populates="account")
    s3_buckets_relationship = relationship("S3Buckets", back_populates="account")

class EC2Instance(Base):
    __tablename__ = 'ec2_instances'
    id = Column(Integer, primary_key=True)
    instance_id = Column(String(32), unique=True, nullable=False)
    creation_time = Column(String(64))
    instance_type = Column(String(128))
    state = Column(String(128))
    state_code = Column(String(32))
    last_transition_date = Column(String(64))
    aging = Column(String(64))
    last_transition_reason = Column(String(128))
    launch_update_time = Column(String(64))
    availability_zone = Column(String(128))
    mac_address = Column(String(64))
    network_interface_id = Column(String(128))
    account_id = Column(String(32), ForeignKey('accounts.account_id'))
    private_ip_address = Column(String(64))
    public_ip_address = Column(String(64))
    network_interface_attachment_id = Column(String(64))
    usage_operation = Column(String(64))
    platform = Column(String(64))
    architecture = Column(String(20))
    subnet_id = Column(String(32))
    vpc_id = Column(String(32))
    image_id = Column(String(64))
    security_groups = Column(String(128))
    tag_properties = Column(JSON)
    instance_name = Column(String(128))
    region = Column(String(32))
    root_device_type = Column(String(64))
    volume_id = Column(String(64)) 
    instance_type = Column(String(64))
    # name_tag = Column(String(128))
    volume_type = Column(String(64))
    volume_size = Column(String(20))
    volume_iops = Column(String(20))
    volume_instance_name = Column(String(128))
    volume_device = Column(String(64))
    volume_status = Column(String(64))
    volume_encrypted = Column(String(64))
    volume_attach_time = Column(String(64))
    volume_delete_on_termination = Column(String(64))
    network_attach_time = Column(String(64))
    ebs_optimized = Column(String(64))
    private_dns_name = Column(String(128))
    public_dns_name = Column(String(128))
    monitoring_state = Column(String(64))
    created_at = Column(TIMESTAMP, server_default=func.now())
    thirty_days_avg = Column(String(10))
    thirty_days_max = Column(String(10))
    thirty_days_min = Column(String(10))
    sixty_days_avg = Column(String(10))
    sixty_days_max = Column(String(10))
    sixty_days_min = Column(String(10))
    provider = Column(String(32), default='aws')

    account = relationship("Account", back_populates="instances")
    
class S3Buckets(Base):
    """Model for S3 Buckets."""
    __tablename__ = 's3_buckets'
    id = Column(Integer, primary_key=True)
    bucket_name = Column(String(128), unique=True, nullable=False)
    creation_date = Column(String(64))
    region = Column(String(32))
    get_bucket_versioning = Column(JSON)
    tag_properties = Column(JSON)
    lifecycle_policy = Column(String(256))
    classifiable_object_count = Column(String(24))
    classifiable_size_bytes = Column(String(32))
    last_update = Column(String(64))
    
    account_id = Column(String(32), ForeignKey('accounts.account_id'))
    provider = Column(String(32), default='aws')
    created_at = Column(TIMESTAMP, server_default=func.now())

    account = relationship("Account", back_populates="s3_buckets_relationship")