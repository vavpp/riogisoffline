from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt

import os

import riogisoffline.plugin.utils as utils

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dialog_export.ui")
)

class ExportDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, riogis, parent=None):
        """Constructor."""
        super(ExportDialog, self).__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.riogis = riogis

        self.populate_select_values()
        
        self.btnSubmit.clicked.connect(self.export)

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

    def populate_select_values(self):
        models = self.riogis.settings["ui_models"]
        for _, item in models.items():
            ui = item["ui"]

            if not hasattr(self, ui):
                continue
             
            dlg_obj = getattr(self, ui)
            dlg_obj.clear()
            items = item["keys"]
            dlg_obj.addItems(items)

    def export(self):

        feature = self.riogis.feature
                
        self.write_output_file()
        self.update_feature_status()
        utils.printSuccessMessage("Lagret som: " + self.riogis.filename)

        self.riogis.dlg.textLedningValgt.setText("Eksportert " + os.path.split(self.filename)[-1])        
        self.rioigs.dlg.btnEksport.setEnabled(False)

        if self.selectedFeatureHasInternalStatus():
            
            lsid = feature["lsid"]
            project_area_id = feature["project_area_id"]
            comment = ""
            new_status = 2
            utils.write_changed_status_to_file(self.riogis.settings, lsid, new_status, comment, project_area_id)

        self.done(1)