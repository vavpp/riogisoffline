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
        
        status_text = utils.get_status_text(status, self.riogis.settings["ui_models"]["status"])

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
                
        self.riogis.data.update(self.get_data_from_select_elements())

        self.riogis.map_attributes()
        filename = self.riogis.write_output_file()
        self.riogis.update_feature_status()

        utils.printSuccessMessage("Lagret som: " + filename)

        self.riogis.dlg.textLedningValgt.setText("Eksportert " + os.path.split(filename)[-1])        
        self.riogis.dlg.btnEksport.setEnabled(False)

        if self.riogis.selectedFeatureHasInternalStatus():
            feature = self.riogis.feature
            
            lsid = feature["lsid"]
            project_area_id = feature["project_area_id"]
            comment = ""
            new_status = 2
            utils.write_changed_status_to_file(self.riogis.settings, lsid, new_status, comment, project_area_id)

        self.accept()

    def get_data_from_select_elements(self):
        """ Leser ui_models i settings.json og lager en mapping dictionary"""
        data = {}
        models = self.riogis.settings["ui_models"]
        for name, item in models.items():
            ui = item["ui"]

            if not hasattr(self, ui):
                continue

            dlg_obj = getattr(self, ui)
            index = dlg_obj.currentIndex()
            items = item["values"]
            data[name] = items[index]
        return data