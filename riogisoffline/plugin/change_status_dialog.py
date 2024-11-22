
import os

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt

import riogisoffline.plugin.utils as utils
from .azure_blob_storage_connection import AzureBlobStorageConnection

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dialog_change_status.ui")
)

class ChangeStatusDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, riogis, parent=None):
        """Constructor."""
        super(ChangeStatusDialog, self).__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.riogis = riogis
        
        self.btnSubmit.clicked.connect(self.run)

    def update_label(self):

        selected_feature = self.riogis.feature

        if not selected_feature:
            self.done(0)
            return

        lsid = selected_feature["lsid"]
        fcode = selected_feature["fcode"]
        status = selected_feature["status_internal"]

        status_items = self.riogis.settings["ui_models"]["status"]
        status_values = status_items["values"]
        status_keys = status_items["keys"]
        status_text = status_keys[status_values.index(status)]

        text = f"Valgt: {fcode} {lsid} - {status_text}"

        self.labelLSID.setText(text)
        self.textComment.clear()
        self.cmbSelectStatus.setCurrentText(status_text)

    def populate_select_values(self):
        select_status_obj = self.cmbSelectStatus
        select_status_obj.clear()
        
        status_items = self.riogis.settings["ui_models"]["status"]
        status_text = status_items["keys"]

        select_status_obj.addItems(status_text)

    def run(self):
        comment = self.textComment.toPlainText()
        selected_status_index = self.cmbSelectStatus.currentIndex()

        layer = self.riogis.layer
        selected_feature = self.riogis.feature

        status_items = self.riogis.settings["ui_models"]["status"]
        status_values = status_items["values"]
        new_status = status_values[selected_status_index]

        if selected_feature["status_internal"] == new_status:
            utils.printInfoMessage("Endret status må være annen en nåværende status")
            return
        
        if  not comment and self.cmbSelectStatus.currentText() in ["Avbrutt", "Ikke inspisert"]:
            utils.printInfoMessage("Kommentar er påkrevd hvis status settes til \"Avbrutt\" eller \"Ikke inspisert\"")
            return

        lsid = selected_feature["lsid"]
        project_area_id = selected_feature["project_area_id"]

        # upload to azure

        utils.write_changed_status_to_file(self.riogis.settings, lsid, new_status, comment, project_area_id)

        layer.startEditing()

        selected_feature["status_internal"] = new_status
        layer.updateFeature(selected_feature)

        layer.commitChanges()
        layer.triggerRepaint()

        self.done(1)