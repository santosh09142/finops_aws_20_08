# main.py

from core.aws_connector import AWSConnector
from core.org_manager import AWSOrgManager
from core.core_service_runner import AWSServiceRunner
# from integrations.db_handler import DBHandler
import config


if __name__ == "__main__":
    # Initialize AWS connector
    connector = AWSConnector(region_name=config.AWS_REGION[0])
    base_session = connector.get_session(profile_name=config.AWS_PROFILE)
    
    org_mgr = AWSOrgManager(base_session)
    accounts = org_mgr.get_all_accounts()
    
    for region in config.AWS_REGION:
        runner = AWSServiceRunner(
            base_session,
            connector,
            region,
            config.CORE_SERVICES,
            accounts,
            config.ASSUME_ROLE_NAME
        )
    result = runner.run()
    print(f"Result for region: {region}")
    for acc_id, svc_data in result.items():
        print(f"  Account ID: {acc_id}")
        for svc, items in svc_data.items():
            print(f"    Service: {svc}: {len(items)}")
            
# end of file
