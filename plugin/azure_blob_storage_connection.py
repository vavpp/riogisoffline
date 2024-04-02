
import sys
import riogisoffline.plugin.utils as utils
sys.path = [utils.get_plugin_dir('dep')] + sys.path
from azure.storage.blob import BlobServiceClient

class AzureBlobStorageConnection:

    def __init__(self, connect_str):
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
            utils.printInfoMessage("Connected to Azure Blob Storage")
        except Exception as e:
            utils.printCriticalMessage("Failed to connect to Azure Blob Storage! Make sure the connection string / azure key is correct!")
            utils.printCriticalMessage(e)


    def download_db(self, file_name):
        
        blob_client = self.blob_service_client.get_blob_client(container="offlinesecure", blob=f"latest/{utils.utils.get_db_name()}")
        
        with open(file=file_name, mode="wb") as blob:
            download_stream = blob_client.download_blob()
            blob.write(download_stream.readall())