
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
        #self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.listWidget.itemClicked.connect(self._item_clicked)
        self.listWidget.itemSelectionChanged.connect(self._update_selected_items_list_widget)
        self.btnSubmit.clicked.connect(self._submit_upload)

        self.riogis = riogis

        self.selected_items = []

        self.has_changed_project_status = False
        self.has_changed_status = False

    
    def _submit_upload(self):

        if not self.riogis.establish_azure_connection():
            return

        mtj = MultiThreadJob(self.riogis)
        mtj.startUploadWorker(self.selected_items)

        self.accept()
        

    def setup_file_view(self, path):

        self._show_if_changed_statuses()

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

        subdirs_that_should_exist = [
            "DB", "Video/Sec",
        ]

        project_dirs = [f.path for f in os.scandir(path) if f.is_dir()]
        project_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        for dir_path in project_dirs:

            dir_name = os.path.split(dir_path)[-1]
            
            # test that subdirs exist in given dir
            for subdir_path in subdirs_that_should_exist:
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
    
    def _show_if_changed_statuses(self):
        # show status change uploads
        user_settings = utils.get_user_settings_path()
        user_settings = utils.load_json(user_settings)
        file_folder_path = user_settings["file_folder"]

        changed_status_filename = os.path.join(file_folder_path, self.riogis.settings["changed_status_filename"])
        self.has_changed_status = os.path.exists(changed_status_filename)

        changed_project_status_filename = os.path.join(file_folder_path, self.riogis.settings["changed_project_status_filename"])
        self.has_changed_project_status = os.path.exists(changed_project_status_filename)
        

    def _item_clicked(self, item):

        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)

        self._update_selected_items_list_widget()

    def _get_checked_list_items(self):
        list_widget = self.listWidget
        items = [list_widget.item(x) for x in range(list_widget.count())]

        return [x for x in items if x.checkState() == Qt.Checked]

    def _update_selected_items_list_widget(self):
        self.selectedItemsWidget.clear()

        self.selected_items = []

        for item in self._get_checked_list_items():
            item_text = item.text()

            self.selected_items.append(item_text)
            self.selectedItemsWidget.addItem(item_text)

        print(self.selected_items)

        if self.has_changed_project_status:
            self.selectedItemsWidget.addItem("Endret status på prosjekt(er)")

        if self.has_changed_status:
            self.selectedItemsWidget.addItem("Endret status på bestilt(e) ledning(er)")


        if self.selected_items or self.has_changed_project_status or self.has_changed_status:
            self.btnSubmit.setEnabled(True)
        else:
            self.btnSubmit.setEnabled(False)