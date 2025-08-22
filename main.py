# main.py

from core.aws_connector import AWSConnector
from core.org_manager import AWSOrgManager
from core.core_service_runner import AWSServiceRunner
from db.init_db import Session, Base, engine
from db.models import Account, EC2Instance
# from integrations.db_handler import DBHandler
import config
def sync_account_to_db(db_session, account):
    acct_obj = db_session.query(Account).filter_by(account_id=account["Id"]).first()
    if not acct_obj:
        acct_obj = Account(account_id=account["Id"], account_name=account.get("Name", None), email=account.get("Email", None), org_unit=account.get("OrgUnit", None))
        db_session.add(acct_obj)
        db_session.commit()
    return acct_obj

def main():
    """Main function to run AWS services across accounts and regions."""
    # Initialize AWS connector
    connector = AWSConnector(region_name=config.AWS_REGION[0])
    base_session = connector.get_session(profile_name=config.AWS_PROFILE)
    
    org_mgr = AWSOrgManager(base_session)
    accounts = org_mgr.get_all_accounts()
    # Create tables if not exits
    # Base.metadata.create_all(engine)
    
    db_session = Session()
        
    for account in accounts:
        sync_account_to_db(db_session, account)
        
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

if __name__ == "__main__":
    main()
    
            
# end of file
