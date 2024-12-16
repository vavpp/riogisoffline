
import json
import riogisoffline.plugin.utils as utils
from azure.storage.blob import BlobServiceClient, BlobBlock
import os
from pathlib import Path
import uuid
import pandas as pd

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

    def upload_projects(self, parent_dir_path, selected_projects, worker):
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

        projects_to_upload_full_path = [os.path.join(parent_dir_path, project) for project in selected_projects]

        for dir_path in projects_to_upload_full_path:

            dir_name = os.path.split(dir_path)[-1]
            new_azure_dir = os.path.join(self.env, "new", dir_name)

            worker.info.emit(f"Mappe: {dir_name}")
            
            
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
            

        worker.finished.emit(False)

    def upload_status_changes(self, settings):

        status_change_files = {
            "changed_status_filename": ["lsid", "new_status", "comment", "project_area_id"],
            "changed_project_status_filename": ["GlobalID", "new_status", "comments_inspector"]
        }

        user_settings = utils.get_user_settings_path()
        # read user settings
        user_settings = utils.load_json(user_settings)
        file_folder_path = user_settings["file_folder"]

        for file, fields in status_change_files.items():
        
            changed_status_filename = os.path.join(file_folder_path, settings[file])

            if not os.path.exists(changed_status_filename):
                return

            changed_status_df = pd.read_csv(changed_status_filename)
            changed_status_df.apply(lambda x: self._upload_status_file(x, fields), axis=1)

            os.remove(changed_status_filename)

    def _upload_status_file(self, row, fields):

        row_id = fields[0]

        if row[row_id] == row_id:
            return

        status_change_dict = {}

        for field in fields:
            if field not in row:
                utils.printWarningMessage(f"FEIL: Kolonne '{field}' finnes ikke i " + str(row))
                return
            
            status_change_dict[field] = row[field]

        json_object = json.dumps(status_change_dict, indent=4)

        if row_id == "lsid":
            new_azure_path = os.path.join(self.env, "changed_status", f"{status_change_dict[row_id]}_status_change.json")
        else:
            new_azure_path = os.path.join(self.env, "changed_project_status", f"{status_change_dict[row_id]}_status_change.json")

        container_client = self.blob_service_client.get_container_client(container="wincan-files")
        blob_client = container_client.get_blob_client(new_azure_path)

        blob_client.upload_blob(json_object, overwrite=True)