import datetime
import hashlib
import os
import requests
import json

from qgis.core import QgsVectorLayer
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

        # TODO add timeout?
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
            # TODO copy if no main db, so you dont need to download twice
            self._download_blob(self._filename, self._up_filename)
        
        # background map file
        if not self._backgroundFileHasLatestUpdate() or not os.path.exists(self._bg_filename):
            self._download(self._background_url, self._bg_filename)

    def _backgroundFileHasLatestUpdate(self):
        """
        Checks if background map is not updated after last plugin update

        Returns:
            bool: True if BG-file needs update
        """
        installed_plugin_version = iface.pluginManagerInterface().pluginMetadata('riogisoffline')['version_installed']
        metadata_file = os.path.join(self._filepath, 'metadata.json')

        installed_background_version = ''
        data = {}

        if os.path.exists(metadata_file):
            
            # checks that file has content
            if os.stat(metadata_file).st_size > 0:

                with open(metadata_file, 'r') as file:
                    data = json.load(file)

                if 'installed_background_version' in data:
                    installed_background_version = data['installed_background_version']

        if installed_background_version == installed_plugin_version:
            return True

        # write current version to json
        with open(metadata_file, 'w') as outfile:
            new_data = data
            if new_data:
                new_data['installed_background_version'] = installed_plugin_version
            else:
                new_data = {
                    'installed_background_version': installed_plugin_version
                }

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
            f"{file2_path}|layername={active_layer_name}", active_layer_name, "ogr"
        )
        # Check if the second layer was loaded successfully
        if not second_layer.isValid():
            self.signal_warning_message(f"Failed to load the layer from {file2_path}")
            return
        
        
        # Get a set of lsid values in the active layer for faster lookup
        max_id = max([f.id() for f in active_layer.getFeatures()])
        active_layer_set = set([f[idstr] for f in active_layer.getFeatures()])

        active_layer.startEditing()

        new_features = []
     
        # Iterate through features in second_layer
        for feature in second_layer.getFeatures():
            # Check if the feature's lsid is not in the active layer
            if feature[idstr] not in active_layer_set:
                max_id +=1
                
                feature.setAttribute(0, max_id)
                feature.setId(max_id)

                new_features.append(feature)

        if new_features:
            self.signal_info_message(f"{active_layer_name}: {len([f.id() for f in new_features])} nye objekter")
        else:
            self.signal_info_message(f"{active_layer_name}: Ingen ny data")
        
        old_feature_list = [f.id() for f in active_layer.getFeatures()]

        # Add the feature to the active layer
        active_layer.addFeatures(new_features)

        # Commit the changes to the active layer immediately
        active_layer.commitChanges()

        new_feature_list = [f.id() for f in active_layer.getFeatures()]
        if new_features and len(old_feature_list) == len(new_feature_list):
            self.signal_warning_message(f"Feil i synkronisering: {len(new_feature_list)} burde være {len(old_feature_list) + len(new_features)}")

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
