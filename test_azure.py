import os
import sys
from dotenv import load_dotenv

# Load env vars
load_dotenv(".env")

from app.infrastructure.storage import AzureBlobStorageAdapter

adapter = AzureBlobStorageAdapter(
    connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
    container_name=os.getenv("AZURE_CONTAINER_NAME"),
    account_name=os.getenv("AZURE_ACCOUNT_NAME"),
    account_key=os.getenv("AZURE_ACCOUNT_KEY")
)

try:
    url = adapter.generate_upload_url("test_file.txt")
    print(f"Azure is working. Generated URL: {url}")
except Exception as e:
    print(f"Azure Error: {e}")
    sys.exit(1)
