
import os
from pathlib import Path

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import Qt

from .multi_thread_job import MultiThreadJob

import riogisoffline.plugin.utils as utils

FORM_CLASS, _ = uic.loadUiType(
    utils.get_plugin_dir("dialog/riogis_dialog_upload.ui")
)

class UploadDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, riogis, parent=None):
        """Constructor."""
        super(UploadDialog, self).__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.listWidget.itemClicked.connect(self._item_clicked)
        self.btnSubmit.clicked.connect(self._submit_upload)

        self.riogis = riogis

        self.selected_items = []

    
    def _submit_upload(self):

        if not self.riogis.establish_azure_connection():
            return

        mtj = MultiThreadJob(self.riogis)
        mtj.startUploadWorker(self.selected_items)

        self.accept()
        

    def setup_file_view(self, path):

        self.listWidget.clear()
        self.selected_items = []
        self._update_selected_items_list_widget()

        if not path:
            utils.printWarningMessage("Du må velge mappe før opplasting")
            return False

        if not os.path.exists(path):
            utils.printWarningMessage(f"{path} eksisterer ikke")
            return False

        # get all projects from path

        subdirs_to_upload = {
            "DB": "DB",
            "Document": "Misc/Docu",
            "Image": "Picture/Sec",
            "Video": "Video/Sec",
        }

        project_dirs = [f.path for f in os.scandir(path) if f.is_dir()]
        project_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        for dir_path in project_dirs:

            dir_name = os.path.split(dir_path)[-1]
            
            # test that subdirs exist in given dir
            for _, subdir_path in subdirs_to_upload.items():
                p = Path(os.path.join(dir_path, subdir_path))

                if not p.is_dir() or dir_name == "Trash":
                    break
            else:
                # display projects in list
                list_item = QtWidgets.QListWidgetItem(dir_name)
                list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)  
                list_item.setCheckState(Qt.Unchecked)  
                self.listWidget.addItem(list_item)

        return True
        

    def _item_clicked(self, item):
        
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        
            self.selected_items.remove(item.text())
            self._update_selected_items_list_widget()
        
            return
        
        item.setCheckState(Qt.Checked)
        self.selected_items.append(item.text())

        self._update_selected_items_list_widget()

    def _update_selected_items_list_widget(self):
        self.selectedItemsWidget.clear()

        for item_text in self.selected_items:
            self.selectedItemsWidget.addItem(item_text)

        if self.selected_items:
            self.btnSubmit.setEnabled(True)
        else:
            self.btnSubmit.setEnabled(False)