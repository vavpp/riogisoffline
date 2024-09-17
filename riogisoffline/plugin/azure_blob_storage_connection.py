
import riogisoffline.plugin.utils as utils
from azure.storage.blob import BlobServiceClient
import os
from pathlib import Path

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

    def upload_dir(self, dir_path):

        subdirs_to_upload = {
            "DB": "DB",
            "Document": "Misc/Docu",
            "Image": "Picture/Sec",
            "Video": "Video/Sec",
        }

        # test that subdirs exist in given dir
        for _, subdir_path in subdirs_to_upload.items():
            p = Path(os.path.join(dir_path, subdir_path))

            if not p.is_dir():
                # TODO: Legg til feilmelding til brukeren her
                raise Exception(f"ERROR: '{subdir_path}' does not exist in dir: '{dir_path}'")

        # upload to azure
        container_client = self.blob_service_client.get_container_client(container="wincan-files")
        for dir_name, subdir_path in subdirs_to_upload.items():
            print("\n", dir_name)
            for fullsubdirpath, _, filenames in os.walk(os.path.join(os.path.join(dir_path, subdir_path))):
                for filename in filenames:
                    print(filename)
                    with open(file=os.path.join(fullsubdirpath, filename), mode="rb") as data:
                        container_client.upload_blob(name=os.path.join("test", dir_name, filename), data=data, overwrite=True)