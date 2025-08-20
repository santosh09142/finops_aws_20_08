# /core/core_service_runner.py

from utils.logger import logger
import config
import importlib

class AWSServiceRunner:
    """Runner class to manage AWS services."""
    
    def __init__(self, base_session, connector, region, services, accounts, role_name):
        self.base_session = base_session
        self.connector = connector
        self.region = region
        self.services = services
        self.accounts = accounts
        self.role_name = role_name
        # Ensure SERVICE_MAP entries are actual callables (classes), not strings.
        # config.SERVICE_MAP may contain class names as strings; replace them
        # with the module-level imported classes (S3Service, EC2Service, ...)
        self.SERVICE_MAP = {}
        for name, val in config.SERVICE_MAP.items():
            resolved = None
            if isinstance(val, str):
                # support module-qualified string like 'core.s3_service:S3Service'
                if ':' in val:
                    module_path, cls_name = val.split(':', 1)
                    try:
                        module = importlib.import_module(module_path)
                        resolved = getattr(module, cls_name, None)
                        if resolved is None:
                            logger.warning("Class %s not found in module %s for service %s", cls_name, module_path, name)
                    except (ImportError, AttributeError) as e:
                        logger.exception("Failed importing %s for service %s: %s", val, name, e)
                else:
                    # fallback: try resolving simple class name from globals
                    resolved = globals().get(val)
                    if resolved is None:
                        logger.warning("Service class '%s' for key '%s' not found in globals", val, name)
            else:
                resolved = val
            self.SERVICE_MAP[name] = resolved
    
    def run(self):
        """Runs the specified AWS services."""
        results = {}
        for account in self.accounts:
            account_id = account["Id"]
            logger.info("Running services for account: %s in region %s", account_id, self.region)
            account_session = self.connector.assume_role(
                    account_id, self.role_name, self.base_session
                )
            if not account_session:
                logger.error("Failed to assume role for account %s", account_id)
                continue
            account_results = {}
            for service in self.services:
                svc_cls = self.SERVICE_MAP.get(service)
                if not svc_cls:
                    logger.warning("Service %s is not supported", service)
                    continue
                svc_instance = (
                    svc_cls(account_session, self.region, account_id)
                    if service != "s3"
                    else svc_cls(account_session, account_id)
                )
                account_results[service] = svc_instance.fetch_properties()
                results[account_id] = account_results
        return results    