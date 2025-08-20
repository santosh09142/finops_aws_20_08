# /core/org_manager.py
"""Get all AWS accounts in the organization."""
from utils.logger import logger


class AWSOrgManager:
    """Manager class to handle AWS Organization accounts."""
    def __init__(self, session):
        """Initialize the AWSOrgManager with a session."""
        self.client = session.client('organizations')
        logger.info("AWSOrgManager initialized with session")

    def get_all_accounts(self):
        """Retrieve all accounts in the AWS organization."""
        accounts = []
        try:
            paginator = self.client.get_paginator('list_accounts')
            for page in paginator.paginate():
                accounts.extend(page['Accounts'])
            logger.info("Retrieved %d accounts from AWS Organizations",
                        len(accounts))
        except Exception as e:
            logger.error("Error retrieving accounts: %s", e)
        return accounts

# end-of file
