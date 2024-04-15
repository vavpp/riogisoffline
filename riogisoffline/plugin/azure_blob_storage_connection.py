
import riogisoffline.plugin.utils as utils
from azure.storage.blob import BlobServiceClient

class AzureBlobStorageConnection:

    connected = False

    def __init__(self, connect_str):
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
            self.connected = True
            utils.printInfoMessage("Connected to Azure Blob Storage")
        except Exception as e:
            utils.printCriticalMessage("Failed to connect to Azure Blob Storage! Make sure the connection string / azure key is correct!")
            utils.printCriticalMessage(e)


    def download_db(self, file_name, syncronizer):
        
        blob_client = self.blob_service_client.get_blob_client(container="offlinesecure", blob=f"latest/{utils.get_db_name()}")
        download_stream = blob_client.download_blob()
        download_chunks = download_stream.chunks()

        progress_percentage = 0
        
        with open(file=file_name, mode="wb") as blob:
            for chunk in download_chunks:
                progress_percentage += (len(chunk)/len(download_chunks))*100
                syncronizer.signal_progress(progress_percentage)

                blob.write(chunk)
            
        
        syncronizer.signal_progress(100)