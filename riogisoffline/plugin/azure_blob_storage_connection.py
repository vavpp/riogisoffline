
import riogisoffline.plugin.utils as utils
from azure.storage.blob import BlobServiceClient, BlobBlock
from azure.data.tables import TableClient
import os
from pathlib import Path
import uuid
from datetime import datetime

class AzureBlobStorageConnection:
    """
    Class that connects to Azure Blob Storage. Can upload and download
    """

    connected = False

    def __init__(self, connect_str):
        """
        Establishes connection to Azure Storage Blob

        Args:
            connect_str (str): Connection string to Azure
        """
        self.connect_str = connect_str
        self.env = "prod"

        if not utils.has_internet_connection():
            utils.printCriticalMessage("Finner ikke internett-tilkobling! Du må ha nett-tilgang for å synkronisere filer!")
            return

        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connect_str)
            self.connected = True
            self.table_client = TableClient.from_connection_string(conn_str=self.connect_str, table_name="UploadedDirectories")
            utils.printInfoMessage("Connected to Azure Blob Storage")
        except Exception as e:
            utils.printCriticalMessage("Failed to connect to Azure Blob Storage! Make sure the connection string / azure key is correct!")
            utils.printCriticalMessage(e)


    def download_db(self, file_name, syncronizer):
        """
        Download database-file

        Args:
            file_name (str): file name to save file as
            syncronizer (Syncronizer): Syncronizer-object used for signalling
        """
        
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

    def upload_dir(self, all_insp_dir_path, worker):
        """
        Upload content of directory containing WinCan-output directories

        Args:
            all_insp_dir_path (str): path to dir
            worker (Worker): worker running function
        """


        subdirs_to_upload = {
            "DB": "DB",
            "Document": "Misc/Docu",
            "Image": "Picture/Sec",
            "Video": "Video/Sec",
        }


        for dir_path in [f.path for f in os.scandir(all_insp_dir_path) if f.is_dir()]:

            dir_name = os.path.split(dir_path)[-1]
            new_azure_dir = os.path.join(self.env, "new", dir_name)

            worker.info.emit(f"Mappe: {dir_name}")

            if self.dir_has_been_uploaded_before(dir_name):
                worker.info.emit(f" - Hopper over. Allerede lastet opp mappe med navn: {dir_name}")
                continue
            
            
            # test that subdirs exist in given dir
            for _, subdir_path in subdirs_to_upload.items():
                p = Path(os.path.join(dir_path, subdir_path))

                if not p.is_dir():
                    worker.warning.emit(f"ERROR: '{subdir_path}' does not exist in dir: '{dir_path}'")
                    worker.warning.emit(f"Mappen du valgte har ikke riktig mappestruktur. Sjekk om du har valgt riktig mappe.")
                    worker.finished.emit(True)
                    return

            # upload to azure
            chunk_size=4*1024*1024
            container_client = self.blob_service_client.get_container_client(container="wincan-files")

            # TODO: show how many files will be uploaded and show how many are left
            
            for subdir_to_upload_name, subdir_path in subdirs_to_upload.items():
                for fullsubdirpath, _, filenames in os.walk(os.path.join(os.path.join(dir_path, subdir_path))):
                    for filename in filenames:
                        worker.process_name.emit(f"{dir_name}/{subdir_to_upload_name}/{filename}")
                        worker.progress.emit(0)

                        block_list = []
                        blob_client = container_client.get_blob_client(os.path.join(new_azure_dir, subdir_to_upload_name, filename))
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

                        worker.info.emit(f" - Lastet opp {dir_name}/{subdir_to_upload_name}/{filename}")
            

            self.add_dir_name_to_table(dir_name)


        worker.finished.emit(False)


    def dir_has_been_uploaded_before(self, dir_name):
        """
        Return true if dir has been uploaded before

        Args:
            dir_name (str): inspection directory name

        Returns:
            bool: True if dir has been uploaded before, False otherwise
        """
        query_filter = f"PartitionKey eq '{self.env}'"
        entities = self.table_client.query_entities(query_filter)
        return dir_name in [e["dir_name"] for e in entities if "dir_name" in e.keys()]
    
    def add_dir_name_to_table(self, dir_name):
        """
        Insert dir name into table that lists what directories have been uploaded before

        Args:
            dir_name (str): inspection directory name
        """
        rowKey = str(uuid.uuid4())
        new_row = {
            u'PartitionKey': self.env,
            u'RowKey': rowKey,
            u'dir_name': dir_name,
            u"upload_time": str(datetime.now())
        }
        self.table_client.create_entity(entity=new_row)