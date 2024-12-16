# -*- coding: utf-8 -*-

from qgis.core import QgsGeometry, QgsPointXY, QgsFeature, QgsFeatureRequest
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QToolBar, QListWidgetItem

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the dialog
from .riogis_dockedwidget import RioGISDocked
from .settings_dialog import SettingsDialog
from .azure_blob_storage_connection import AzureBlobStorageConnection
from .change_status_dialog import ChangeStatusDialog
from .change_project_status_dialog import ChangeProjectStatusDialog
from .export_dialog import ExportDialog
from .upload_dialog import UploadDialog
from .search_box import SearchBox
from .multi_thread_job import MultiThreadJob

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
        self.selected_project = None

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
            text=self.tr("RioGIS offline"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

        # will be set False in run()
        self.first_start = True

    def initiate_gui_elements(self):
        """ Initiates GUI elements the first time the plugin runs """

        self.dlg = RioGISDocked()

        # Select feature
        self.dlg.btnSelectMapClick.clicked.connect(lambda: self.handle_map_click(self.handle_select_feature))

        # Select project
        self.dlg.btnSelectProject.clicked.connect(lambda: self.handle_map_click(self.select_project))

        # Refresh map
        self.dlg.btnReset.clicked.connect(self.refresh_map)

        # Syncronize
        self.dlg.btnSync.clicked.connect(self.run_syncronize_in_background)

        self.show_last_sync_time_date()

        # Export
        self.dlg.btnEksport.clicked.connect(self._handle_export)
        # disable export-button until a feature is selected
        self.dlg.btnEksport.setEnabled(False)

        # Upload
        def _handle_upload_button_click():
            uploadDialog = UploadDialog(self)
            upload_dir_is_valid = uploadDialog.setup_file_view(self.dlg.selectUploadDir.filePath())
            if upload_dir_is_valid:
                uploadDialog.exec_()

        self.dlg.btnUpload.clicked.connect(_handle_upload_button_click)
        self.dlg.btnUpload.setEnabled(False)

        self.dlg.selectUploadDir.fileChanged.connect(lambda: 
                self.dlg.btnUpload.setEnabled(True) if self.dlg.selectUploadDir.filePath() else self.dlg.btnUpload.setEnabled(False)
            )

        self.dlg.selectUploadDir.filePath()

        # User settings
        selectFileDialog = SettingsDialog()

        def _handle_settings_button_click():
            selectFileDialog.exec_()
            self.dlg.refresh_dialog()
            self.setup_user_settings()
        
        self.dlg.btnSelectSettingsFile.clicked.connect(_handle_settings_button_click)

        # Change status
        changeStatusDialog = ChangeStatusDialog(self)
        changeStatusDialog.populate_select_values()

        def _handle_change_status_button_click():            
            changeStatusDialog.update_label()
            changeStatusDialog.exec_()

        self.dlg.btnMarker.clicked.connect(_handle_change_status_button_click)
        
        self.setButtonsEnabled(False)
        self.show_necessary_panels()

        # Change project status
        self.dlg.btnChangeProjectStatus.setEnabled(False)
        
        changeProjectStatusDialog = ChangeProjectStatusDialog(self)
        changeProjectStatusDialog.populate_select_values()
  
        def _handle_change_project_status_button_click():
            changeProjectStatusDialog.update_label()
            changeProjectStatusDialog.exec_()

        self.dlg.btnChangeProjectStatus.clicked.connect(_handle_change_project_status_button_click)

        # List with orders in project
        self.dlg.listOrdersInProject.hide()
        self.dlg.listOrdersInProject.itemClicked.connect(self._list_item_clicked)
        self.all_orders_in_selected_project = None

        # Search
        search_box = SearchBox(self.dlg, self.iface)
        search_box.setup()

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
        
        export_dialog = ExportDialog(self)
        export_dialog.update_label()
        export_dialog.exec()

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

    def map_attributes(self):
        """Map to new keys and values"""

        data = self.data
        
        data["datenow"] = datetime.datetime.now().strftime("%Y.%m.%d")

        if "status_internal" in data:
            data["InternalStatus"] = data["status_internal"]

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

    def handle_map_click(self, click_map_action):
        self.map_has_been_clicked = True
        self.canvas = self.iface.mapCanvas()
        self.mapTool = QgsMapToolEmitPoint(self.canvas)
        self.mapTool.canvasClicked.connect(click_map_action)
        self.canvas.setMapTool(self.mapTool)

    def handle_select_feature(self, point, mouse_button, layers=None):
        
        feature_layers = layers if layers else self.iface.mapCanvas().layers()
        self.selected_layer = None

        self.select_layer(feature_layers, self.settings["feature_name"])
        self.select_nearest_feature(point, layers=feature_layers)

        self.select_feature()

    def select_feature(self):

        if self.feature:
            if self.selectedFeatureHasInternalStatus():
                self.setButtonsEnabled(True)
            else:
                self.dlg.btnEksport.setEnabled(True)

            data = self.get_feature_data()
            self.show_selected_feature(data)
            self.data = data
        else:
            self.show_selected_feature(None)
            self.setButtonsEnabled(False)

    def select_project(self, point, mouse_button, layers=None):

        self.dlg.listOrdersInProject.clear()
        
        feature_layer = "Prosjekt"
        feature_layers = layers if layers else self.iface.mapCanvas().layers()
        self.select_layer(feature_layers, feature_layer)
        point_click = QgsGeometry.fromPointXY(QgsPointXY(point.x(), point.y()))

        all_features = self.get_all_features_from_all_feature_layers(feature_layers, [feature_layer])

        near_projects = list(
            filter(
                lambda feat: point_click.distance(feat.geometry()) == 0,
                all_features,
            )
        )

        if not near_projects:
            self.dlg.btnChangeProjectStatus.setEnabled(False)
            self.dlg.textSelectedProject.setText("Ingen prosjekter er valgt")
            self.dlg.listOrdersInProject.hide()
            return
        
        features_with_meters_in_order = {
            feat: feat.geometry().area() for feat in near_projects
        }
        
        nearest_feature_distances_list = list(features_with_meters_in_order.values())
        min_dist = min(nearest_feature_distances_list)
        idx = nearest_feature_distances_list.index(min_dist)
        self.selected_project = near_projects[idx]

        self.dlg.btnChangeProjectStatus.setEnabled(True)

        
        # flash geometry
        self.iface.mapCanvas().flashGeometries([self.selected_project.geometry()], flashes=1, duration=500, startColor=QColor(100, 0, 100, 150), endColor=QColor(255, 255, 255, 0))

        self.show_project_information(self.selected_project)

    def show_project_information(self, project):
        """
        Show project information in widget

        Args:
            project (QgsFeature): selected project
        """

        print(project.geometry().area())

        # get all orders in project
        all_order_features = self.get_layer_by_name("Bestillinger").getFeatures()

        orders_in_project = list(
            filter(
                lambda feat: project.geometry().distance(feat.geometry()) == 0 and feat["project_area_id"] == project["project_area_id"],
                all_order_features,
            )
        )

        completed_total_length = 0
        cant_inspect_total_length = 0
        interrupted_total_length = 0
        spyling_total_length = 0
        remaining_total_length = 0


        for order in orders_in_project:
            length = order["length"]
            status = order["status_internal"]

            if not length:
                length = 0

            if status == 3:
                cant_inspect_total_length += length
            elif status == 4:
                completed_total_length += length
            elif status == 5:
                interrupted_total_length += length
            elif status == 8:
                spyling_total_length += length

        meters_in_order = project["meters_in_order"] if project["meters_in_order"] else 0
        remaining_total_length = meters_in_order-completed_total_length

        # show project information
        text = f'Prosjekt valgt:<br>'

        project_info_dict = {
            "Navn": project["project_name"],
            "Status": utils.get_status_text(project["status"], self.settings['ui_models']['project_status']),
            "Kommentar": project["comments"],
            "Bestilt": project["ordered_date"],
            "Bestilt av": project["ordered_email"],
            "Inspeksjonsformål": project["purpose"],
            "ISY prosjektnummer": project["isy_project_reference"],
            "Totalt antall meter i bestilling": meters_in_order,
            "Antall meter fullført": completed_total_length,
            "Antall meter som ikke kunne inspiseres": cant_inspect_total_length,
            "Antall meter avbrutt": interrupted_total_length,
            "Antall meter spyling": spyling_total_length,
            "Gjenstående meter": remaining_total_length,
        }

        for k,v in project_info_dict.items():
            if isinstance(v, float):
                v = "{:.2f}".format(v)
            project_info_dict[k] = v if v or str(v) == "0" else ""

        text += "<br>".join([f"<strong>{k}</strong>: {v}" for k,v in project_info_dict.items()])

        self.dlg.textSelectedProject.setText(text)


        orders_in_project.sort(key=lambda x: x["status_internal"])
        for order_feature in orders_in_project:
            fcode = order_feature['fcode']
            lsid = order_feature['lsid'] 
            status_internal = utils.get_status_text(order_feature['status_internal'], self.settings['ui_models']['status'])
            material = order_feature['material'] 
            dim = order_feature['dim']
            construction_year = order_feature['construction_year'] 
            owner = order_feature['owner'] 
            pipe_status = order_feature['pipe_status']

            list_item_text = f"{fcode}{lsid} ({status_internal}) - {material} {dim} - {construction_year} - {owner} {pipe_status}"
            order_item = QListWidgetItem(list_item_text)
            order_item.setData(Qt.UserRole, order_feature)
            self.dlg.listOrdersInProject.addItem(order_item)

        self.dlg.listOrdersInProject.show()

    def _list_item_clicked(self, item):
        clicked_order_feature = item.data(Qt.UserRole)
        self.feature = clicked_order_feature
        self.select_feature()        

        canvas = self.iface.mapCanvas()
        canvas.setExtent(clicked_order_feature.geometry().boundingBox())
        canvas.refresh()

    def setButtonsEnabled(self, enabled):
        self.dlg.btnEksport.setEnabled(enabled)
        self.dlg.btnMarker.setEnabled(enabled)

    def selectedFeatureHasInternalStatus(self):
        if not self.feature:
            return False
        
        return "status_internal" in getFieldNames(self.feature)

    def show_selected_feature(self, data):
        if not data:
            text = "Ingen ledning er valgt"
            self.dlg.textLedningValgt.setText(text) 
            return
            
        # flash geometry
        self.iface.mapCanvas().flashGeometries([self.feature.geometry()], flashes=1, duration=500, startColor=QColor(100, 0, 100, 255), endColor=QColor(255, 255, 255, 255))

        streetname = data["streetname"] if "streetname" in data else "-"
        fcode = utils.fcode_to_text(data["fcode"]) if str(data["fcodegroup"]).isnumeric() else data["fcodegroup"]

        text = f'Ledning valgt: LSID: <strong>{data["lsid"]}</strong> (fra PSID {data["from_psid"]} til {data["to_psid"]}), Gate: <strong>{streetname}</strong>, Type: <strong>{fcode}</strong>, Dim: <strong>{data["dim"]} mm</strong>, Materiale: <strong>{data["material"]}</strong>'
        
        # show in message
        utils.printInfoMessage(text, message_duration=5)
        
        # show in dialog
        dlgText = text.replace(",", "<br>").replace("Ledning valgt: ", "Ledning valgt: <br>")
        dlgText += "<br>"
        if not "orderd_ident" in data:
            dlgText += "<p style='color:#d60;'><strong style='color:#f40;'>Advarsel:</strong> Ledningen er ikke bestilt, og vil opprette en ny bestilling! Hvis du prøver å velge en eksisterende bestilling kan du prøve å skru av laget \"VA-data\", og velge ledningen på nytt.</p>"
        self.dlg.textLedningValgt.setText(dlgText)

    def select_nearest_feature(self, point, layers=None):
        """
        Get nearest feature

        Args:
            point (point): point
        """
        point_click = QgsGeometry.fromPointXY(QgsPointXY(point.x(), point.y()))

        feature_names = [self.settings["feature_name"]] + self.settings["other_feature_names"]
        all_features = self.get_all_features_from_all_feature_layers(layers, feature_names)

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

    def get_all_features_from_all_feature_layers(self, layers, feature_names):
        
        # layers with selectable features
        layer_names = [l.name() for l in layers]

        all_features = []

        for name in feature_names:
            if name in layer_names:
                index = layer_names.index(name)
                all_features += layers[index].getFeatures()
        
        return all_features


    def update_feature_status(self):
        # Side effect update status on export
        self.layer.startEditing()

        update_project_status = False

        # create new feature in "Bestilling" if feature is not in that layer
        if not self.selectedFeatureHasInternalStatus():
            self.create_new_order_feature()
        else:
            status = self.feature["status_internal"]
            if int(status) < 4:
                self.feature["status_internal"] = 2
            self.layer.updateFeature(self.feature)

            update_project_status = True

        self.layer.commitChanges()
        self.layer.triggerRepaint()

        if update_project_status:
            self.update_project_to_in_progress(self.feature)

    def update_project_to_in_progress(self, feature_in_project):

        # get project that belongs to feature
        project_area_id = feature_in_project["project_area_id"]
        
        feature_layer = "Prosjekt"
        feature_layers = self.iface.mapCanvas().layers()
        self.select_layer(feature_layers, feature_layer)

        all_features = self.get_all_features_from_all_feature_layers(feature_layers, [feature_layer])

        near_features = list(
            filter(
                lambda feat: feature_in_project.geometry().distance(feat.geometry()) < 10,
                all_features,
            )
        )

        project = None

        for nf in near_features:
            if nf["project_area_id"] == project_area_id:
                project = nf
                break

        if not project:
            utils.printWarningMessage("Fant ikke tilhørende prosjekt til bestilling")
            return

        if project["status"] == 1:
            new_status = 2
            comment = ""
            utils.change_project_status(self.settings, self.layer, project, new_status, comment)

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

        filename = os.path.join(folder, f"{fcode}-{lsid}.txt")
        config = configparser.ConfigParser()
        config.optionxform = str
        config[f"Inspection1"] = self.data

        # write out the wincan file its a python config file format
        with open(filename, "w") as f:
            config.write(f, space_around_delimiters=False)

        return filename

    def select_layer(self, layers, name):
        # Fetch currently loaded layers
        names = [l.name() for l in layers]
        if name in names:
            index = names.index(name)
            self.layer = layers[index]
            self.iface.setActiveLayer(self.layer)
        else:
            self.layer = self.iface.activeLayer()

    def get_layer_by_name(self, name):

        layers = self.iface.mapCanvas().layers()

        # Fetch currently loaded layers
        names = [l.name() for l in layers]
        if name in names:
            index = names.index(name)
            return layers[index]

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
        mtj = MultiThreadJob(self)
        mtj.startSyncWorker()

    def show_last_sync_time_date(self):

        if not "file_folder" in self.settings:
            return

        default_text = "Last ned kartdata"

        filepath = self.settings["file_folder"]
        filename = os.path.join(filepath, utils.get_db_name())
        root, ext = os.path.splitext(filename)
        up_filename = root + "_update" + ext

        if not os.path.exists(up_filename):
            self.dlg.textSync.setText(default_text)
            return

        sync_time = os.path.getmtime(up_filename)
        datetime_last_sync = datetime.datetime.fromtimestamp(sync_time).strftime("%d. %b. %Y, %H:%M")
        self.dlg.textSync.setText(f"{default_text}\n(Synket sist: {datetime_last_sync})")
        

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
