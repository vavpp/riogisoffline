# -*- coding: utf-8 -*-

from qgis.core import QgsGeometry, QgsPointXY, QgsFeature
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QToolBar

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the dialog
from .riogis_dockedwidget import RioGISDocked
from .settings_dialog import SettingsDialog
from .azure_blob_storage_connection import AzureBlobStorageConnection

import os.path
import configparser
import datetime

import riogisoffline.plugin.utils as utils


class RioGIS:
    """ Handles initialization and interaction with GUI-elements """

    def __init__(self, iface):

        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = utils.get_plugin_dir()

        self.setup()

        # initialize locale
        locale = QSettings().value("locale/userLocale")
        locale_path = os.path.join(self.plugin_dir, "i18n", "{}.ts".format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = "&RioGIS"

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.first_refresh = True
        self.map_has_been_clicked = False
        self.feature = None
        self.data = None
        self.azure_connection = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("RioGIS", message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """ Runs when QGIS starts """

        icon_path = ":/plugins/riogis/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("Export to wincan"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

        # will be set False in run()
        self.first_start = True

    def initiate_gui_elements(self):
        """ Initiates GUI elements the first time the plugin runs """
        self.dlg = RioGISDocked()
        self.populate_select_values()

        self.dlg.btnSelectMapClick.clicked.connect(self.handle_map_click)
        self.dlg.btnReset.clicked.connect(self.refresh_map)

        self.dlg.btnSync.clicked.connect(self.run_syncronize_in_background)

        self.dlg.btnEksport.clicked.connect(self._handle_export)
        # disable export-button until a feature is selected
        self.dlg.btnEksport.setEnabled(False)

        self.dlg.btnUpload.clicked.connect(self.run_upload_wincan_dir_in_background)
        # disable upload-button until user selects dir with selectUploadDir
        self.dlg.btnUpload.setEnabled(False)

        selectFileDialog = SettingsDialog()

        def _handle_settings_button_click():
            selectFileDialog.exec_()
            self.dlg.refresh_dialog()
            self.setup_user_settings()
        
        self.dlg.btnSelectSettingsFile.clicked.connect(_handle_settings_button_click)

        self.show_necessary_panels()

    def show_necessary_panels(self):
        
        needed_panels = ['Layers', 'mPluginToolBar', 'mAttributesToolBar', 'mMapNavToolBar', 'MessageLog']
        for x in self.iface.mainWindow().findChildren(QDockWidget) + self.iface.mainWindow().findChildren(QToolBar):
            if x.objectName() in ["RioGIS2"]:
                continue

            if x.objectName() in needed_panels:
                x.setVisible(True)
            else:
                x.setVisible(False)

    def _handle_export(self):
        if self.map_has_been_clicked:
            self.iface.mapCanvas().unsetMapTool(self.mapTool)
        
        if self.map_has_been_clicked and self.data and self.data.get("PipeID"):
                self.write_output_file()
                self.update_feature_status()
                utils.printSuccessMessage("Lagret som: " + self.filename)

                self.dlg.textLedningValgt.setText("Eksportert " + os.path.split(self.filename)[-1])        
                self.dlg.btnEksport.setEnabled(False)


    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu("&RioGIS", action)
            self.iface.removeToolBarIcon(action)

    def setup(self):
        settings = utils.get_settings_path()
        self.settings = utils.load_json(settings)
        self.mapper = self.settings["mapping"]

        self.setup_user_settings()

    def setup_user_settings(self):
        user_settings_path = utils.get_user_settings_path()
        if os.path.exists(user_settings_path): 
            self.settings.update(utils.load_json(user_settings_path))

    def load_select_elements(self):
        """ Leser ui_models i settings.json og lager en mapping dictionary"""
        data = {}
        models = self.settings["ui_models"]
        for name, item in models.items():
            ui = item["ui"]
            dlg_obj = getattr(self.dlg, ui)
            index = dlg_obj.currentIndex()
            items = item["values"]
            data[name] = items[index]
        return data

    def map_attributes(self, data):
        """Map to new keys and values"""

        data["datenow"] = datetime.datetime.now().strftime("%Y.%m.%d")
        data.update(self.load_select_elements())

        data["operator"] = self.settings["operator"]
        data["orderid"] = ""
        data["workorder"] = ""
        if not data.get('form'):
            data['form'] = ""

        old_keys = set(data.keys())
        map_keys = set(self.mapper.keys())
        auto_keys = old_keys.intersection(map_keys)

        new_data = {}
        for k in auto_keys:
            v = self.mapper[k]
            new_data[v] = data[k]
        self.data = new_data

    def handle_map_click(self):
        self.map_has_been_clicked = True
        self.canvas = self.iface.mapCanvas()
        self.mapTool = QgsMapToolEmitPoint(self.canvas)
        self.mapTool.canvasClicked.connect(self.export_feature)
        self.canvas.setMapTool(self.mapTool)

    def export_feature(self, point, mouse_button, layers=None):
        
        feature_layers = layers if layers else self.iface.mapCanvas().layers()
        self.selected_layer = None

        self.select_layer(feature_layers)
        self.select_feature(point, layers=feature_layers)

        if self.feature:
            self.dlg.btnEksport.setEnabled(True)

            data = self.get_feature_data()
            self.show_selected_feature(data)
            self.map_attributes(data)
        else:
            self.show_selected_feature(None)
            self.dlg.btnEksport.setEnabled(False)

    def show_selected_feature(self, data):
        if not data:
            text = "Ingen ledning er valgt"
            self.dlg.textLedningValgt.setText(text) 
            return
            
        streetname = data["streetname"] if "streetname" in data else "-"
        fcode = utils.fcode_to_text(data["fcode"]) if str(data["fcodegroup"]).isnumeric() else data["fcodegroup"]

        text = f'Ledning valgt: LSID: <strong>{data["lsid"]}</strong> (fra PSID {data["from_psid"]} til {data["to_psid"]}), Gate: <strong>{streetname}</strong>, Type: <strong>{fcode}</strong>, Dim: <strong>{data["dim"]}</strong>, Materiale: <strong>{data["material"]}</strong>'
        
        # show in message
        utils.printInfoMessage(text, message_duration=5)
        
        # show in dialog
        dlgText = text.replace(",", "<br>").replace("Ledning valgt: ", "Ledning valgt: <br>")
        dlgText += "<br>"
        if not "orderd_ident" in data:
            dlgText += "<p style='color:#d60;'><strong style='color:#f40;'>Advarsel:</strong> Ledningen er ikke bestilt, og vil opprette en ny bestilling! Hvis du prøver å velge en eksisterende bestilling kan du prøve å skru av laget \"VA-data\", og velge ledningen på nytt.</p>"
        self.dlg.textLedningValgt.setText(dlgText)

    def select_feature(self, point, layers=None):
        """
        Get nearest feature

        Args:
            point (point): point
        """
        point_click = QgsGeometry.fromPointXY(QgsPointXY(point.x(), point.y()))

        all_features = self.get_all_features_from_all_feature_layers(layers)

        near_features = list(
            filter(
                lambda feat: point_click.distance(feat.geometry()) < 10 and point_click.distance(feat.geometry()) >= 0,
                all_features,
            )
        )
        
        nearest_feature_distances = {
            feat: point_click.distance(feat.geometry()) for feat in near_features
        }
        
        # remove duplicates that is not in layer "Bestilling" so that "Bestilling"-layer is prioritized
        nearest_feature_distances_without_duplicates = nearest_feature_distances.copy()
        feature_lsids = [feat["lsid"] for feat in nearest_feature_distances]
        for feat in nearest_feature_distances:
            if feature_lsids.count(feat["lsid"]) > 1 and not "orderd_ident" in getFieldNames(feat):
                del nearest_feature_distances_without_duplicates[feat]
        
        if not nearest_feature_distances_without_duplicates:
            self.feature = None
            return

        nearest_feature_distances_list = list(nearest_feature_distances_without_duplicates.values())
        min_dist = min(nearest_feature_distances_list)
        idx = nearest_feature_distances_list.index(min_dist)
        self.feature = near_features[idx]

    def get_all_features_from_all_feature_layers(self, layers):
        
        # layers with selectable features
        feature_names = [self.settings["feature_name"]] + self.settings["other_feature_names"]
        layer_names = [l.name() for l in layers]

        all_features = []

        for name in feature_names:
            if name in layer_names:
                index = layer_names.index(name)
                all_features += layers[index].getFeatures()
        
        return all_features


    def update_feature_status(self):
        # Side effect update status on export!!
        self.layer.startEditing()

        # create new feature in "Bestilling" if feature is not in that layer
        if not "status_internal" in getFieldNames(self.feature):
            self.create_new_order_feature()
        else:
            order_feature = self.feature
            status = order_feature["status_internal"]
            if int(status) < 4:
                order_feature["status_internal"] = self.data.get("InternalStatus")
            self.layer.updateFeature(order_feature)

        self.layer.commitChanges()
        self.layer.triggerRepaint()

    def create_new_order_feature(self):
        """
        Create new feature and adds it to "Bestilling"-layer. Copies attributes and geometry from self.feature

        Returns:
            QgsFeature: new order feature
        """

        # create new feature
        new_feature = QgsFeature()

        selected_feature_fields = self.feature.attributeMap()

        new_feature.setFields(self.layer.fields())
        
        for attr, val in selected_feature_fields.items():
            if attr in getFieldNames(new_feature):
                new_feature.setAttribute(attr, val)
        
        new_feature.setAttribute("status_internal", 2)
        new_feature.setAttribute("objectid", 1000000)

        # set geometry
        new_feature.setGeometry(self.feature.geometry())

        # TODO: fails when adding feature. returns false
        res = self.layer.dataProvider().addFeature(new_feature)
        print("RESULTAT:", res)
        
        self.layer.updateFeature(new_feature)
        
        return new_feature 

    def get_feature_data(self):
        """Get data dictionary

        Returns:
            dict: data
        """

        # convert field data to a dictionary
        data = {atn: self.feature[atn] for atn in getFieldNames(self.feature)}
        
        # if anything is a datetime object, convert it to a string
        for key in data.keys():
            val = data[key]
            if hasattr(val, "strftime"):
                val = val.strftime("%Y-%m-%dT%H:%M:%S")
                data[key] = val
        return data

    def refresh_map(self):
        
        if not os.path.exists(utils.get_user_settings_path()): 
            utils.printWarningMessage("Legg til bruker-innstillinger (bruker_settings.json)!")
            return
        
        userfolder = self.settings["userfolder"]
        filefolder = self.settings["file_folder"]
        filename = self.settings["project_filename"]
        project_filename = os.path.join(userfolder, filename)

        source = utils.get_db_name()
        bg = self.settings["background_url"].split("/")[-1].strip()
        source_filepath = os.path.join(filefolder, source)
        bg_filepath = os.path.join(filefolder, bg)
        os.environ['BACKGROUND_MAP'] = bg_filepath
        os.environ['SOURCE_MAP'] = source_filepath
       
        # check that .db files and background exists in file_folder
        if not utils.synced_files_exist():
            utils.printWarningMessage("Mangler data for å laste kart. Trykk \"Synkroniser\" først!")
            return
        
        from .refresh_map import MapRefresher 
        map_refresher = MapRefresher()
        map_refresher.refresh_map(project_filename)

        if self.first_refresh:
            map_refresher.zoom_to_extent()
            self.first_refresh = False


    def write_output_file(self):
        lsid = self.data.get("PipeID")
        fcode = self.data.get("PipeFeature")
        folder = self.settings["output_folder"]
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        self.filename = os.path.join(folder, f"{fcode}-{lsid}.txt")
        config = configparser.ConfigParser()
        config.optionxform = str
        config[f"Inspection1"] = self.data

        # write out the wincan file its a python config file format
        with open(self.filename, "w") as f:
            config.write(f, space_around_delimiters=False)

    def uploadFiles(self):

        if not self.establish_azure_connection():
            return

        dir_path_to_upload = self.dlg.selectUploadDir.filePath()
        self.azure_connection.upload_dir(dir_path_to_upload)

        

    def populate_select_values(self):
        models = self.settings["ui_models"]
        for _, item in models.items():
            ui = item["ui"]
            dlg_obj = getattr(self.dlg, ui)
            dlg_obj.clear()
            items = item["keys"]
            dlg_obj.addItems(items)

    def select_layer(self, layers):
        # Fetch currently loaded layers
        name = self.settings["feature_name"]
        names = [l.name() for l in layers]
        if name in names:
            index = names.index(name)
            self.layer = layers[index]
            self.iface.setActiveLayer(self.layer)
        else:
            self.layer = self.iface.activeLayer()

    def run(self):
        """ Run when user clicks plugin icon """         
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        
        # TODO Split some gui-things into riogis_dockedwidget

        if self.first_start:
            self.first_start = False
        self.initiate_gui_elements()

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dlg) 

    def establish_azure_connection(self):
        if not os.path.exists(utils.get_user_settings_path()): 
            utils.printWarningMessage("Legg til bruker-innstillinger (bruker_settings.json)!")
            return False
        
        if not self.azure_connection:
            self.azure_connection = AzureBlobStorageConnection(self.settings["azure_key"])

        if not self.azure_connection.connected:
            self.azure_connection = None
            return False

        return True
    
    def run_syncronize_in_background(self):
        from .multi_thread_job import MultiThreadJob
        mtj = MultiThreadJob(self)
        mtj.startSyncWorker()

    def run_upload_wincan_dir_in_background(self):
        from .multi_thread_job import MultiThreadJob
        mtj = MultiThreadJob(self)
        mtj.startUploadWorker()
        

def getFieldNames(obj):
    """
    Get field names from layer or feature

    Args:
        feature (QgsFeature or layer): feature or layer

    Returns:
        [str]: list of field names of given object 
    """

    fieldnames = [field.name() for field in obj.fields()]
    return fieldnames
