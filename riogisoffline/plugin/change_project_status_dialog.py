
from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt

import riogisoffline.plugin.utils as utils

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dialog_change_project_status.ui")
)

class ChangeProjectStatusDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, riogis, parent=None):
        """Constructor."""
        super(ChangeProjectStatusDialog, self).__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.riogis = riogis
        
        self.btnSubmit.clicked.connect(self.run)

        self.status_items = self.riogis.settings["ui_models"]["project_status"]

    def update_label(self):
    
        selected_feature = self.riogis.selected_project

        if not selected_feature:
            self.reject()
            return

        project_name = selected_feature["project_name"]
        status = selected_feature["status"]
        comments = selected_feature["comments"]

        status_text = utils.get_status_text(status, self.status_items)

        text = f"Valgt: <strong>{project_name}</strong> - <strong>{status_text}</strong><br>{comments}"

        self.labelProject.setText(text)
        self.textComment.clear()
        self.cmbSelectStatus.setCurrentText(status_text)

    def populate_select_values(self):
        select_status_obj = self.cmbSelectStatus
        select_status_obj.clear()
        
        status_text = self.status_items["keys"]

        select_status_obj.addItems(status_text)

    def run(self):
        comment = self.textComment.toPlainText()
        selected_status_index = self.cmbSelectStatus.currentIndex()

        layer = self.riogis.layer
        selected_feature = self.riogis.selected_project

        status_values = self.status_items["values"]
        new_status = status_values[selected_status_index]

        if selected_feature["status"] == new_status:
            utils.printInfoMessage("Endret status må være annen en nåværende status")
            return
        
        #if  not comment and self.cmbSelectStatus.currentText() in ["Avbrutt", "Kunne ikke inspiseres"]:
        #    utils.printInfoMessage("Kommentar er påkrevd hvis status settes til \"Avbrutt\" eller \"Kunne ikke inspiseres\"")
        #    return
        
        utils.change_project_status(self.riogis.settings, layer, selected_feature, new_status, comment)

        self.accept()