import datetime
import hashlib
import os

import requests

from qgis.core import QgsVectorLayer
from .utils import printInfoMessage, get_plugin_dir, load_json, printWarningMessage, get_user_settings_path, get_settings_path, get_db_name, printCriticalMessage
from .azure_blob_storage_connection import AzureBlobStorageConnection


class Syncronizer:
    def __init__(self):
        #printInfoMessage('init sync')
        self.plugin_dir =get_plugin_dir
        self._settings = get_settings_path()
        self._user_settings = get_user_settings_path()

    def _setup(self):
        # read builtin-settings
        settings = load_json(self._settings)
        self._layer_definitions = settings["layer_definitions"]
        
        # read user settings
        user_settings = load_json(self._user_settings)
        self._filepath = user_settings["userfolder"]
        if not os.path.exists(self._filepath):
            os.makedirs(self._filepath, exist_ok=True)
        y = datetime.datetime.now().strftime("%Y")
        self._background_url = user_settings["background_url"].format(year=y)
        self._filename = os.path.join(self._filepath, get_db_name())
        bg_file = self._background_url.split("/")[-1]
        root, ext = os.path.splitext(self._filename)
        self._up_filename = root + "_update" + ext
        self._bg_filename = os.path.join(self._filepath, bg_file)
        self.azure_key = user_settings["azure_key"]

    @staticmethod
    def _download(url, filename):
        response = requests.get(url)
        if response.status_code == 200:
            printInfoMessage('download ok')
            with open(filename, "wb") as file:
                file.write(response.content)
        else:
            printInfoMessage(f"Failed to download the new file {filename} from {url}")
    
    def _download_blob(self, file_name):
        azure_connection = AzureBlobStorageConnection(self.azure_key)
        azure_connection.download_db(file_name)

    def _fetch(self):
        # database file
        if os.path.exists(self._filename):
            self._download_blob(self._up_filename)
        else:
            self._download_blob(self._filename)
            self._download_blob(self._up_filename)
        
        # background map file
        if not os.path.exists(self._bg_filename):
            self._download(self._background_url, self._bg_filename)

    @staticmethod
    def _equal(file1, file2):
        with open(file1, "rb") as f1:
            with open(file2, "rb") as f2:
                h1 = hashlib.new("md5")
                h2 = hashlib.new("md5")
                h1.update(f1.read())
                h2.update(f2.read())
                return h1.hexdigest() == h2.hexdigest()

    @staticmethod
    def _update(active_layer_name, source_filepath, file2_path, idstr):
        # Get the active layer from the QGIS interface
        #printInfoMessage(f'Update {active_layer_name} from {file2_path} using {idstr}')
        active_layer = QgsVectorLayer(
                        f"{source_filepath}|layername={active_layer_name}",
                        active_layer_name,
                        "ogr")
        # Check if the active layer is valid
        if active_layer is None:
            printWarningMessage("Active layer not found in the project.")
            return

        # Load the layer from file2.gpkg
        second_layer = QgsVectorLayer(
            f"{file2_path}|layername={active_layer_name}", active_layer_name, "ogr"
        )
        # Check if the second layer was loaded successfully
        if not second_layer.isValid():
             printWarningMessage(f"Failed to load the layer from {file2_path}")
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
            printInfoMessage(f"{active_layer_name}: {len([f.id() for f in new_features])} nye features")
        else:
            printInfoMessage(f"{active_layer_name}: Ingen ny data")
        
        old_feature_list = [f.id() for f in active_layer.getFeatures()]

        # Add the feature to the active layer
        active_layer.addFeatures(new_features)

        # Commit the changes to the active layer immediately
        active_layer.commitChanges()

        new_feature_list = [f.id() for f in active_layer.getFeatures()]
        if new_features and len(old_feature_list) == len(new_feature_list):
            printCriticalMessage(f"Feil i synkronisering: {len(new_feature_list)} burde være {len(old_feature_list) + len(new_features)}")

        # Refresh the active layer to see the changes
        active_layer.triggerRepaint()

        printInfoMessage(f"{active_layer_name}: Features copied successfully.")

    def sync_now(self):
        
        if not os.path.exists(self._user_settings): 
            printWarningMessage("Legg til bruker-innstillinger (bruker_settings.json)!")
            return
        
        self._setup()

        # Download new datafiles
        printInfoMessage('Laster ned data...')
        self._fetch()
        
        # If the updated file is different proceed
        if not self._equal(self._filename, self._up_filename):
            layer_definition = self._layer_definitions
            for layer_name, idstr in layer_definition.items():
                self._update(layer_name, self._filename, self._up_filename, idstr)

        printInfoMessage("Synkronisering gjennomført")