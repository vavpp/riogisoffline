
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
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        user_settings_generator = UserSettingsGenerator(self)
        self.btnSubmitSettingsFile.clicked.connect(lambda: user_settings_generator.run())

        user_settings_path = utils.get_user_settings_path()
        
        if os.path.exists(user_settings_path):

            user_settings = utils.load_json(user_settings_path)

            self._set_line_edit_text(self.lineOperator, "operator", user_settings)
            self._set_line_edit_text(self.lineBGURL, "background_url", user_settings)
            self._set_line_edit_text(self.lineAzurekey, "azure_key", user_settings)

    
    def _set_line_edit_text(self, line_edit_obj, key, user_settings):
        if not key in user_settings:
            return
        
        line_edit_obj.setText(user_settings[key])