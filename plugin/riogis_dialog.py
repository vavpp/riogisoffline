
import riogisoffline.plugin.utils as utils
import os
import textwrap

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dialog_base.ui")
)

class RioGISDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(RioGISDialog, self).__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

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

        user_info_mapper = {
            "operator": "Operatør",
            "output_folder": "Output-mappe",
            "userfolder": "Bruker-mappe",
            "background_url": "URL til bakgrunnskart",
            "azure_key": "Azure connection string",
        }

        max_str_width = 80
        
        user_settings_str = "<strong>Bruker-innstillinger</strong><p>"

        for k in user_settings:
            user_settings_str += f"<strong>{user_info_mapper[k]}</strong> :  "
            user_settings_str += '<br>'.join(textwrap.wrap(user_settings[k], max_str_width))
            user_settings_str += "<br>"

        user_settings_str += f"<br>Hvis informasjon over ikke stemmer, trykk på <strong>\"{self.settingsButtonText}\"</strong>."
        user_settings_str += "</p>"

        return user_settings_str