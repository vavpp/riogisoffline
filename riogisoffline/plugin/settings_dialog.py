
import os

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt

from .user_settings_generator import UserSettingsGenerator
import riogisoffline.plugin.utils as utils

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dialog_settings.ui")
)

class SettingsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        user_settings_generator = UserSettingsGenerator(self)
        self.btnSubmitSettingsFile.clicked.connect(lambda: user_settings_generator.run())

        user_settings_path = utils.get_user_settings_path()
        
        if os.path.exists(user_settings_path):

            user_settings = utils.load_json(user_settings_path)

            self._set_line_edit_text(self.lineOperator, "operator", user_settings)
            self._set_line_edit_text(self.lineBGURL, "background_url", user_settings)
            self._set_line_edit_text(self.lineAzurekey, "azure_key", user_settings)

        self._add_crash_report_option()

    def _add_crash_report_option(self):
        """Opt-out for sending crash reports (saved immediately, not with the user settings file)."""
        from qgis.PyQt.QtCore import QSettings
        from .crash_reporter import SEND_SETTING

        self.checkSendCrashReports = QtWidgets.QCheckBox("Send feilrapporter til GIS-teamet")
        self.checkSendCrashReports.setChecked(QSettings().value(SEND_SETTING, True, type=bool))
        self.checkSendCrashReports.setToolTip(
            "Når RioGIS får en feil eller QGIS krasjer, lagres en rapport med feilmelding, "
            "versjoner, de siste handlingene i RioGIS og operatørnavnet ditt, slik at "
            "GIS-teamet kan kontakte deg om feilen. Den sendes til Vann- og avløpsetatens "
            "GIS-team ved neste synkronisering eller opplasting.\n"
            "Nøkler, brukernavn i filstier og e-postadresser fjernes før rapporten lagres. "
            "Rapporter slettes etter 90 dager."
        )
        self.checkSendCrashReports.toggled.connect(
            lambda checked: QSettings().setValue(SEND_SETTING, bool(checked))
        )
        # just above the save button
        self.formLayout.insertRow(self.formLayout.rowCount() - 1, "", self.checkSendCrashReports)


    def _set_line_edit_text(self, line_edit_obj, key, user_settings):
        if not key in user_settings:
            return
        
        line_edit_obj.setText(user_settings[key])