
import riogisoffline.plugin.utils as utils
import os

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import QtCore

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dockwidget.ui")
)

class RioGISDocked(QtWidgets.QDockWidget, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(RioGISDocked, self).__init__("RioGIS", parent)
        self.setupUi(self)

        #dock_widget.setWidget(MainWindow)
        #self.setFixedWidth(356)
        #self.setFixedHeight(620)
        self.setAllowedAreas(QtCore.Qt.RightDockWidgetArea)

        # setting vertical title bar
        #self.setFeatures(QtWidgets.QDockWidget.DockWidgetVerticalTitleBar)



        self.settingsButtonText = "Oppdater bruker-innstillinger..."
        self.refresh_dialog()

    def refresh_dialog(self):

        # TODO ? legg til prompt med ja/nei om synkronisering siden kan ta lang tid

        if os.path.exists(utils.get_user_settings_path()):
            self.btnSelectSettingsFile.setText(self.settingsButtonText)

            user_settings = utils.load_json(utils.get_user_settings_path())
            self.textBrukerInfo.setText(self.format_user_settings(user_settings))


    def accept(self):
        if not os.path.exists(utils.get_user_settings_path()):
            utils.printWarningMessage("Legg til bruker-info!")
            return
        
        self.done(1)

    def format_user_settings(self, user_settings):
        user_settings_str = f"<p><strong>Operatør: {user_settings['operator']}</strong><br>"
        user_settings_str += f"For å endre operatør (eller andre bruker-innstillinger), <br>trykk på <strong>\"{self.settingsButtonText}\"</strong>.</p>"

        return user_settings_str