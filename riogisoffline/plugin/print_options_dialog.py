"""Dialog for choosing template and scale before printing a map."""

import math
import os

from qgis.PyQt.QtCore import QSettings, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from .print_layout import PRINT_SCALES

SCALE_SETTING = "riogisoffline/print_scale"
TEMPLATE_SETTING = "riogisoffline/print_template"


def nearest_print_scale(scale):
    """Fixed print scale closest to the given scale (compared on a log scale)."""
    scale = max(1.0, float(scale))
    return min(PRINT_SCALES, key=lambda s: abs(math.log(s) - math.log(scale)))


class PrintOptionsDialog(QDialog):
    """
    Non-modal dialog. While it is open, the print area is shown on the map and
    the user can pan the map to move it. Emits optionsChanged when the template
    or scale changes.
    """

    optionsChanged = pyqtSignal()

    def __init__(self, template_folder, current_scale, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Skriv ut kart")
        self.setModal(False)

        description = QLabel(
            "Det blå feltet i kartet viser hva som skrives ut. "
            "Panorer kartet for å flytte utsnittet."
        )
        description.setWordWrap(True)

        self.template_combo = QComboBox()
        self.template_combo.addItem("RioGIS standard (A4 liggende)", None)
        for path in self._template_paths(template_folder):
            self.template_combo.addItem(os.path.splitext(os.path.basename(path))[0], path)

        self.scale_combo = QComboBox()
        for denominator in PRINT_SCALES:
            self.scale_combo.addItem("1:{}".format(denominator), denominator)

        self.area_label = QLabel()
        self.area_label.setObjectName("printAreaLabel")

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b3261e;")
        self.error_label.hide()

        form = QFormLayout()
        form.addRow("Layoutmal", self.template_combo)
        form.addRow("Målestokk", self.scale_combo)
        form.addRow("Utskriftsområde", self.area_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Åpne forhåndsvisning")
        self.ok_button.setDefault(True)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Avbryt")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(description)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)
        self.setMinimumWidth(380)

        self._restore_choices(current_scale)
        self.template_combo.currentIndexChanged.connect(self._on_changed)
        self.scale_combo.currentIndexChanged.connect(self._on_changed)

    @staticmethod
    def _template_paths(template_folder):
        if not template_folder or not os.path.isdir(template_folder):
            return []
        return sorted(
            os.path.join(template_folder, filename)
            for filename in os.listdir(template_folder)
            if filename.lower().endswith(".qpt")
            and os.path.isfile(os.path.join(template_folder, filename))
        )

    def _restore_choices(self, current_scale):
        settings = QSettings()
        saved_template = settings.value(TEMPLATE_SETTING, "")
        index = self.template_combo.findData(saved_template) if saved_template else -1
        self.template_combo.setCurrentIndex(max(0, index))

        saved_scale = settings.value(SCALE_SETTING, 0, type=int)
        scale = saved_scale if saved_scale in PRINT_SCALES else nearest_print_scale(current_scale)
        self.scale_combo.setCurrentIndex(self.scale_combo.findData(scale))

    def _on_changed(self, *_args):
        self.optionsChanged.emit()

    def accept(self):
        settings = QSettings()
        settings.setValue(SCALE_SETTING, self.selected_scale())
        settings.setValue(TEMPLATE_SETTING, self.selected_template_path() or "")
        super().accept()

    def selected_template_path(self):
        return self.template_combo.currentData()

    def selected_scale(self):
        return int(self.scale_combo.currentData())

    def set_area(self, width_m, height_m):
        self.area_label.setText("{:,.0f} × {:,.0f} m".format(width_m, height_m).replace(",", " "))

    def set_error(self, message):
        """Show an error and block printing, or clear it with None."""
        self.error_label.setText(message or "")
        self.error_label.setVisible(bool(message))
        self.ok_button.setEnabled(not message)
