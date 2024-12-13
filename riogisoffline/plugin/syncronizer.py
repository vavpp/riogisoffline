import datetime
import hashlib
import os
import requests
import json
import pandas as pd

from qgis.core import QgsVectorLayer, QgsFeatureRequest
from qgis.utils import iface
import riogisoffline.plugin.utils as utils

class Syncronizer:
    def __init__(self, worker, azure_connection):
        self.plugin_dir =utils.get_plugin_dir
        self._settings = utils.get_settings_path()
        self._user_settings = utils.get_user_settings_path()
        self.worker = worker
        self.azure_connection = azure_connection

    def _setup(self):
        # read builtin-settings
        settings = utils.load_json(self._settings)
        self._layer_definitions = settings["layer_definitions"]
        self.changed_status_filename = settings["changed_status_filename"]
        self.changed_project_status_filename = settings["changed_project_status_filename"]
        
        # read user settings
        user_settings = utils.load_json(self._user_settings)
        self._filepath = user_settings["file_folder"]
        if not os.path.exists(self._filepath):
            os.makedirs(self._filepath, exist_ok=True)
        y = datetime.datetime.now().strftime("%Y")
        self._background_url = user_settings["background_url"].format(year=y)
        self._filename = os.path.join(self._filepath, utils.get_db_name())
        bg_file = self._background_url.split("/")[-1]
        root, ext = os.path.splitext(self._filename)
        self._up_filename = root + "_update" + ext
        self._bg_filename = os.path.join(self._filepath, bg_file)
        self.azure_key = user_settings["azure_key"]

    def _download(self, url, filename):

        short_file_name = filename
        if os.sep in filename:
            short_file_name = filename.split(os.sep)[-1]

        self.signal_new_process_name(f"Laster ned {short_file_name}...")

        response = requests.get(url, stream=True)
        if response.status_code != 200:
            self.signal_warning_message(f"Failed to download the new file {filename} from {url}")
            return
            
        chunk_size = int(response.headers["Content-Length"])//100
        download_chunks = response.iter_content(chunk_size=chunk_size)
        
        progress_percentage = 0


        with open(filename, "wb") as file:
            for chunk in download_chunks:

                self.signal_progress(progress_percentage)
                progress_percentage += 1

                file.write(chunk)
        
        self.signal_progress(100)
        
    
    def _download_blob(self, *file_names):          
        for file_name in file_names:

            short_file_name = file_name
            if os.sep in file_name:
                short_file_name = file_name.split(os.sep)[-1]

            self.signal_new_process_name(f"Laster ned {short_file_name}...")

            self.azure_connection.download_db(file_name, self)


    def _fetch(self):

        # database file
        if os.path.exists(self._filename):
            self._download_blob(self._up_filename)
        else:
            self._download_blob(self._filename, self._up_filename)
        
        # background map file
        if not self._backgroundFileHasLatestUpdate() or not os.path.exists(self._bg_filename):
            self._download(self._background_url, self._bg_filename)

    def _backgroundFileHasLatestUpdate(self):
        """
        Checks if background map is not updated after last plugin update

        Returns:
            bool: True if BG-file has latest update
        """
        
        metadata_file = utils.get_plugin_dir('riogis_metadata.json')

        has_latest_background_version = False
        data = {}

        # checks that file exists and has content
        if os.path.exists(metadata_file) and os.stat(metadata_file).st_size > 0:
            with open(metadata_file, 'r') as file:
                data = json.load(file)

            if 'has_latest_background_version' in data:
                has_latest_background_version = data['has_latest_background_version']

        if has_latest_background_version:
            return True

        with open(metadata_file, 'w') as outfile:
            new_data = data
            new_data['has_latest_background_version'] = True

            json.dump(new_data, outfile, indent=4)

        return False

    @staticmethod
    def _equal(file1, file2):
        with open(file1, "rb") as f1:
            with open(file2, "rb") as f2:
                h1 = hashlib.new("md5")
                h2 = hashlib.new("md5")
                h1.update(f1.read())
                h2.update(f2.read())
                return h1.hexdigest() == h2.hexdigest()

    def _update(self, active_layer_name, source_filepath, file2_path, idstr):

        # Get the active layer from the QGIS interface
        active_layer = QgsVectorLayer(
                        f"{source_filepath}|layername={active_layer_name}",
                        active_layer_name,
                        "ogr")
        # Check if the active layer is valid
        if active_layer is None:
            self.signal_warning_message("Active layer not found in the project.")
            return

        # Load the layer from file2.gpkg
        second_layer = QgsVectorLayer(
            f"{file2_path}|layername={active_layer_name}", 
            active_layer_name, 
            "ogr"
        )
        # Check if the second layer was loaded successfully
        if not second_layer.isValid():
            self.signal_warning_message(f"Failed to load the layer from {file2_path}")
            return
        
        active_layer.startEditing()

        feature_id = 0
        new_features = []
    
        listOfIds = [feat.id() for feat in active_layer.getFeatures()]
        active_layer.deleteFeatures( listOfIds )
     
        # Iterate through features in second_layer
        for feature in second_layer.getFeatures():
            feature.setAttribute(0, feature_id)
            feature.setId(feature_id)

            feature_id +=1
            
            new_features.append(feature)

        changed_status_filepath = os.path.join(self._filepath, self.changed_status_filename)
        changed_project_status_filepath = os.path.join(self._filepath, self.changed_project_status_filename)
        
        if idstr == "lsid" and os.path.exists(changed_status_filepath):
            changed_status_df = pd.read_csv(changed_status_filepath)
        
            for _, row in changed_status_df.iterrows():
                lsid = row["lsid"]
                project_area_id = row["project_area_id"]
                status = row["new_status"]

                feature_to_change = [feat for feat in new_features if feat["lsid"] == lsid and feat["project_area_id"] == project_area_id]

                if feature_to_change:
                    feature = feature_to_change[0]
                    
                    feature["status_internal"] = status
        elif idstr == "project_area_id" and os.path.exists(changed_project_status_filepath):
            changed_project_status_df = pd.read_csv(changed_project_status_filepath)
        
            for _, row in changed_project_status_df.iterrows():
                project_area_id = row["GlobalID"]
                status = row["new_status"]

                feature_to_change = [feat for feat in new_features if feat["project_area_id"] == project_area_id]

                if feature_to_change:
                    feature = feature_to_change[0]
                    
                    feature["status"] = status

        # Add the feature to the active layer
        active_layer.addFeatures(new_features)

        # Commit the changes to the active layer immediately
        active_layer.commitChanges()

        # Refresh the active layer to see the changes
        active_layer.triggerRepaint()

    def sync_now(self):

        # Load settings variables     
        self._setup()

        # Download new datafiles
        self._fetch()
        
        # Merge local db file if updated file is different
        if not self._equal(self._filename, self._up_filename):
            layer_definition = self._layer_definitions
            for layer_name, idstr in layer_definition.items():
                self.signal_new_process_name(f"Oppdaterer lag {layer_name}...")
                self.signal_progress(0)

                # Add new features to layer
                self._update(layer_name, self._filename, self._up_filename, idstr)
    
                self.signal_progress(100)
                
        self.worker.finished.emit(False)

    def signal_progress(self, progress):
        """Signal progress (0 to 100, inclusive) for current process to main thread

        Args:
            progress (number): number between 0 and 100 indicating progress for current process
        """
        if int(progress) > 100 or int(progress) < 0:
            self.signal_warning_message(f"Trying to set progress outside of legal range: {progress}")
            return

        self.worker.progress.emit(int(progress))

    def signal_new_process_name(self, process_name):
        self.worker.process_name.emit(process_name)

    def signal_info_message(self, message):
        self.worker.info.emit(message)

    def signal_warning_message(self, message):
        self.worker.warning.emit(message)

    def signal_error(self, exception, message):
        self.worker.error.emit(exception, message)
