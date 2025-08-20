# /core/service_base.py
"""service_base.py"""

class ServiceBase:
    """Base class for AWS services."""
    def fetch_properties(self):
        """
        Fetches a property from the service.
        """
        raise NotImplementedError("Subclasses must implement fetch+properties() method.")
