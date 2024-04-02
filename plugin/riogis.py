# -*- coding: utf-8 -*-

from qgis.core import QgsGeometry, QgsPointXY
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the dialog
from .riogis_dockedwidget import RioGISDocked
from .settings_dialog import SettingsDialog
from .syncronizer import Syncronizer

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
        #self.dlg = RioGISDialog()
        self.dlg = RioGISDocked()
        self.sync = Syncronizer()
        self.populate_select_values()

        self.dlg.btnSelectMapClick.clicked.connect(self.handle_map_click)
        self.dlg.btnReset.clicked.connect(self.refresh_map)
        self.dlg.btnSync.clicked.connect(self.sync.sync_now)

        self.dlg.btnEksport.clicked.connect(self._handle_export)
        # disable export-button until a feature is selected
        self.dlg.btnEksport.setEnabled(False)

        selectFileDialog = SettingsDialog()

        def _handle_settings_button_click():
            selectFileDialog.exec_()
            self.dlg.refresh_dialog()
            self.setup_user_settings()
        
        self.dlg.btnSelectSettingsFile.clicked.connect(_handle_settings_button_click)

    def _handle_export(self):
        if self.map_has_been_clicked:
            self.iface.mapCanvas().unsetMapTool(self.mapTool)
        
        if self.map_has_been_clicked and self.data and self.data.get("PipeID"):
                self.write_output_file()
                self.update_feature_status()
                utils.printSuccessMessage("Lagret som: " + self.filename)

                self.dlg.textLedningValgt.setText("")


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

        # TODO only print when pressing new feature?
        utils.printInfoMessage(f'Ledning valgt: LSID {data["lsid"]} (fra PSID {data["from_psid"]} til {data["to_psid"]}), {data["streetname"]}, {data["fcodegroup"]}')

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
        # TODO unset when reclick this button?
        self.canvas.setMapTool(self.mapTool)

    def select_feature(self, point):
        """Select layer and get nearest feature

        Args:
            point (point): point
        """
        self.select_layer()
        point_click = QgsGeometry.fromPointXY(QgsPointXY(point.x(), point.y()))
        near_features = list(
            filter(
                lambda feat: point_click.distance(feat.geometry()) < 10,
                self.layer.getFeatures(),
            )
        )
        nearest_feature_distances = [
            point_click.distance(feat.geometry()) for feat in near_features
        ]
        
        if not nearest_feature_distances:
            return

        min_dist = min(nearest_feature_distances)
        idx = nearest_feature_distances.index(min_dist)
        self.feature = near_features[idx]

    def update_feature_status(self):
        # Side effect update status on export!!
        self.layer.startEditing()
        status = self.feature["status_internal"]
        if int(status) < 4:
            self.feature["status_internal"] = self.data.get("InternalStatus")
        self.layer.updateFeature(self.feature)
        self.layer.commitChanges()
        self.layer.triggerRepaint()

    def get_feature_data(self):
        """Get data dictionary

        Returns:
            dict: data
        """

        # convert field data to a dictionary
        fieldnames = [field.name() for field in self.layer.fields()]
        data = {atn: self.feature[atn] for atn in fieldnames}
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
        filename = self.settings["project_filename"]
        project_filename = os.path.join(userfolder, filename)

        source = utils.get_db_name()
        bg = self.settings["background_url"].split("/")[-1].strip()
        source_filepath = os.path.join(userfolder, source)
        bg_filepath = os.path.join(userfolder, bg)
        os.environ['BACKGROUND_MAP'] = bg_filepath
        os.environ['SOURCE_MAP'] = source_filepath
        
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

        # TODO ? write output to output-folder?

        # write out the wincan file its a python config file format
        with open(self.filename, "w") as f:
            config.write(f, space_around_delimiters=False)

    def export_feature(self, point, mouse_button):
        self.select_feature(point)

        if self.feature:
            self.dlg.btnEksport.setEnabled(True)

            data = self.get_feature_data()
            self.show_selected_feature(data)
            self.map_attributes(data)

    def show_selected_feature(self, data):
        text = f"<strong>LSID: {data['lsid']}, Gate: {data['streetname']}</strong>"
        self.dlg.textLedningValgt.setText(text)

    def populate_select_values(self):
        models = self.settings["ui_models"]
        for _, item in models.items():
            ui = item["ui"]
            dlg_obj = getattr(self.dlg, ui)
            dlg_obj.clear()
            items = item["keys"]
            dlg_obj.addItems(items)

    def select_layer(self):
        # Fetch currently loaded layers
        layers = self.iface.mapCanvas().layers()
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

        if self.first_start:
            self.first_start = False
        self.initiate_gui_elements()

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dlg) 

    