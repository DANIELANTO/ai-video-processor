from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from app.application.interfaces import IFileStorage

class AzureBlobStorageAdapter(IFileStorage):
    def __init__(self, connection_string: str, container_name: str, account_name: str, account_key: str):
        self.connection_string = connection_string
        self.container_name = container_name
        self.account_name = account_name
        self.account_key = account_key
        # Verify connection
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    def generate_upload_url(self, filename: str) -> str:
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=filename,
            account_key=self.account_key,
            permission=BlobSasPermissions(write=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Build the final URL with the embedded token
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{filename}?{sas_token}"

    def download_file(self, blob_name: str, local_path: str) -> None:
        """Downloads a blob from Azure to the container's local storage using chunks to optimize memory RAM."""
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
        
        with open(local_path, "wb") as download_file:
            # Start the download as a data stream
            download_stream = blob_client.download_blob()
            
            # Iterate over the chunks and write them directly to disk
            for chunk in download_stream.chunks():
                download_file.write(chunk)

    def upload_file(self, local_path: str, blob_name: str) -> str:
        """
        Uploads a local file to Azure Blob Storage and returns a read-only 
        signed URL (SAS Token) valid for 7 days.
        """
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
        
        # Upload the rendered file
        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
            
        # Generate a secure read token
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=7)
        )
        
        # Return the URL with the injected signature
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"

    def generate_read_url(self, blob_name: str) -> str:
        """Generates a temporary read-only SAS URL for a blob."""
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=7)
        )
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"