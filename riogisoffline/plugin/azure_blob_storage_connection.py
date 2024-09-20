
import riogisoffline.plugin.utils as utils
from azure.storage.blob import BlobServiceClient
import os
from pathlib import Path
import uuid
from azure.storage.blob import BlobBlock
from datetime import date

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

    def upload_dir(self, dir_path, worker):

        azure_dir_with_date = f"test/{date.today().strftime("%Y_%m_%d")}"

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
                worker.warning.emit(f"ERROR: '{subdir_path}' does not exist in dir: '{dir_path}'")
                worker.warning.emit(f"Mappen du valgte har ikke riktig mappestruktur. Sjekk om du har valgt riktig mappe.")
                worker.finished.emit()
                return

        # upload to azure
        chunk_size=4*1024*1024
        container_client = self.blob_service_client.get_container_client(container="wincan-files")

        # TODO: show how many files will be uploaded and show how many are left
        
        for dir_name, subdir_path in subdirs_to_upload.items():
            for fullsubdirpath, _, filenames in os.walk(os.path.join(os.path.join(dir_path, subdir_path))):
                for filename in filenames:
                    worker.process_name.emit(filename)
                    worker.progress.emit(0)

                    block_list = []
                    blob_client = container_client.get_blob_client(os.path.join(azure_dir_with_date, dir_name, filename))
                    chunk_num = 0

                    with  open(file=os.path.join(fullsubdirpath, filename), mode="rb") as  f:
                        while  True:

                            chunk_num += 1
                            read_data = f.read(chunk_size)
                            if  not  read_data:
                                break  # done
                            blk_id = str(uuid.uuid4())
                            blob_client.stage_block(block_id=blk_id,data=read_data)
                            block_list.append(BlobBlock(block_id=blk_id))
                            blob_client.commit_block_list(block_list)
                            
                            progress = int((chunk_size*chunk_num)/os.path.getsize(os.path.join(fullsubdirpath, filename))*100)
                            worker.progress.emit(min(progress, 100))

                    worker.info.emit(f"Lastet opp {dir_name}/{filename}")
        
        worker.finished.emit()