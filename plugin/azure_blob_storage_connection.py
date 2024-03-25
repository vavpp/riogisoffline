
import sys
from .utils import printInfoMessage, printCriticalMessage, get_db_name, get_plugin_dir
sys.path = [get_plugin_dir('dep')] + sys.path
from azure.storage.blob import BlobServiceClient





class AzureBlobStorageConnection:

    # container_name: offlinesecure
    # databasen ligger på latest/oslo_offline.db

    def __init__(self, connect_str):
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
            printInfoMessage("Connected to Azure Blob Storage")
        except Exception as e:
            printCriticalMessage("Failed to connect to Azure Blob Storage! Make sure the connection string / azure key is correct!")
            printCriticalMessage(e)


    def download_db(self, file_name):
        
        blob_client = self.blob_service_client.get_blob_client(container="offlinesecure", blob=f"latest/{get_db_name()}")
        
        with open(file=file_name, mode="wb") as blob:
            download_stream = blob_client.download_blob()
            blob.write(download_stream.readall())