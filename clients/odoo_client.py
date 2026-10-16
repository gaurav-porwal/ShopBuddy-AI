import os
from urllib.parse import urlparse
 
import odoorpc
from dotenv import load_dotenv
 
 
class OdooClient:
    """Handles Odoo RPC connection and authentication."""
 
    def __init__(self):
        """Load environment variables and connect to Odoo."""
 
        # Load .env and override old environment values
        load_dotenv(override=True)
 
        # Read environment variables
        self.url = os.getenv("ODOO_ENDPOINT")
        self.db = os.getenv("ODOO_DB_NAME")
        self.username = os.getenv("ODOO_ADMIN_USERNAME")
        self.password = os.getenv("ODOO_ADMIN_PASSWORD")
 
        # Debug prints
        print("Loaded Configuration")
        print("URL:", self.url)
        print("DB:", self.db)
        print("USERNAME:", self.username)
 
        # Validate values
        missing = [
            name for name, value in {
                "ODOO_ENDPOINT": self.url,
                "ODOO_DB_NAME": self.db,
                "ODOO_ADMIN_USERNAME": self.username,
                "ODOO_ADMIN_PASSWORD": self.password,
            }.items()
            if not value
        ]
 
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
 
        # Connect
        self.connect()
 
    def connect(self):
        """Establish RPC connection and authenticate."""
 
        try:
            # Parse URL
            parsed = urlparse(self.url)
 
            self.host = parsed.hostname
 
            print("\nConnecting to Odoo...")
            print("Host:", self.host)
 
            # HTTPS Odoo connection
            self.odoo = odoorpc.ODOO(
                self.host,
                protocol="jsonrpc+ssl",
                port=443
            )
 
            # Login
            self.odoo.login(
                self.db,
                self.username,
                self.password
            )
 
            # Store UID
            self.uid = self.odoo.env.uid
 
            print("? Connected Successfully")
            print("UID:", self.uid)
 
        except Exception as e:
            print("? Connection/Login Failed")
            print("ERROR:", e)
            raise
 
 
# Create client instance
client = OdooClient()