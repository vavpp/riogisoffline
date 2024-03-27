
from .utils import get_plugin_dir, load_json, printWarningMessage, get_user_settings_path
import os
import textwrap

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import QtCore

FORM_CLASS, _ = uic.loadUiType(
    get_plugin_dir("dialog/riogis_dockwidget.ui")
)

class RioGISDocked(QtWidgets.QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(RioGISDocked, self).__init__("RioGIS", parent)
        self.setupUi(self)

        #dock_widget.setWidget(MainWindow)
        #self.setFixedWidth(356)
        #self.setFixedHeight(620)
        self.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)# | QtCore.Qt.TopDockWidgetArea)

        self.settingsButtonText = "Oppdater bruker-innstillinger..."
        self.refresh_dialog()

    def refresh_dialog(self):

        # TODO ? legg til prompt med ja/nei om synkronisering siden kan ta lang tid

        if os.path.exists(get_user_settings_path()):
            self.btnSelectSettingsFile.setText(self.settingsButtonText)

            user_settings = load_json(get_user_settings_path())
            self.textBrukerInfo.setText(self.format_user_settings(user_settings))


    def accept(self):
        if not os.path.exists(get_user_settings_path()):
            printWarningMessage("Legg til bruker-info!")
            return
        
        self.done(1)

    def format_user_settings(self, user_settings):

        user_info_mapper = {
            "operator": "Operatør",
            #"output_folder": "Output-mappe",
            #"userfolder": "Bruker-mappe",
            #"background_url": "URL til bakgrunnskart",
            #"azure_key": "Azure connection string",
        }

        max_str_width = 80
        
        user_settings_str = "<strong>Bruker-innstillinger</strong><p>"

        for k in user_settings:
            if k not in user_info_mapper:
                continue
            
            user_settings_str += f"<strong>{user_info_mapper[k]}</strong> :  "
            user_settings_str += '<br>'.join(textwrap.wrap(user_settings[k], max_str_width))
            user_settings_str += "<br>"

        user_settings_str += f"<br>Hvis informasjon over ikke stemmer, trykk på <strong>\"{self.settingsButtonText}\"</strong>."
        user_settings_str += "</p>"

        return user_settings_str