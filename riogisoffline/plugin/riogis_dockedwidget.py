import os

from qgis.PyQt import uic, QtWidgets, QtCore, QtGui
from pathlib import Path

import riogisoffline.plugin.utils as utils

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dockwidget.ui")
)

class RioGISDocked(QtWidgets.QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(RioGISDocked, self).__init__("RioGIS", parent)
        self.setupUi(self)
        
        self.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)

        self.settingsButtonText = "Oppdater bruker-innstillinger..."
        self.refresh_dialog()

        # TODO set title?
        self.setWindowTitle("")

        self.selectUploadDir.fileChanged.connect(self.handleSelectUploadDir)


    def refresh_dialog(self):

        if os.path.exists(utils.get_user_settings_path()):
            self.btnSelectSettingsFile.setText(self.settingsButtonText)

            user_settings = utils.load_json(utils.get_user_settings_path())
            self.textBrukerInfo.setText(self.format_user_settings(user_settings))


    def format_user_settings(self, user_settings):
        user_settings_str = f"<p><strong>Operatør: {user_settings['operator']}</strong><br>"
        user_settings_str += f"For å endre operatør (eller andre bruker-innstillinger), trykk på <strong>\"{self.settingsButtonText}\"</strong>.</p>"

        return user_settings_str
    
    def handleSelectUploadDir(self):
        selected_path = self.selectUploadDir.filePath()

        if selected_path and Path(selected_path).is_dir():
            self.btnUpload.setEnabled(True)