"""
Print workflow: choose template and scale, see the print area on the map, then
open the finished layout in the QGIS layout designer.
"""

import os

from qgis.core import Qgis, QgsProject, QgsUnitTypes

import riogisoffline.plugin.utils as utils

from .print_layout import (
    PrintRequest,
    add_save_template_action,
    build_print_layout,
    load_layout,
    map_frame_size_mm,
    print_extent,
    register_layout,
)
from .print_options_dialog import PrintOptionsDialog
from .print_preview import PrintAreaPreview


class PrintController:
    """
    Owns the dialog and the map preview while printing is in progress, so
    that nothing is garbage collected while QGIS still uses it.
    """

    def __init__(self, iface, settings, dialog_class=PrintOptionsDialog):
        """
        Args:
            iface (QgisInterface): QGIS interface
            settings (dict): plugin settings (operator, output_folder, ...)
            dialog_class: dialog to use (replaceable in tests)
        """
        self.iface = iface
        self.settings = settings
        self._dialog_class = dialog_class
        self._dialog = None
        self._preview = None
        self._frame_sizes = {}
        self.last_layout = None

    # ---------------------------------------------------------------- public

    @property
    def is_active(self):
        return self._dialog is not None

    def start(self):
        """Open the print dialog and show the print area on the map."""
        if self._dialog is not None:
            self._dialog.raise_()
            self._dialog.activateWindow()
            return

        operator = str(self.settings.get("operator", "")).strip()
        if not operator:
            utils.printWarningMessage("Legg inn operatørnavn i brukerinnstillingene før utskrift.")
            return

        canvas = self.iface.mapCanvas()
        if not canvas.layers():
            utils.printWarningMessage("Kartet har ingen lag å skrive ut. Synkroniser og last kartet først.")
            return

        self._dialog = self._dialog_class(
            self.template_folder, canvas.scale(), self.iface.mainWindow()
        )
        self._preview = PrintAreaPreview(canvas)

        self._dialog.optionsChanged.connect(self._on_options_changed)
        # not "finished": Qt emits it before "accepted", which would clean up too early
        self._dialog.accepted.connect(self._on_accepted)
        self._dialog.rejected.connect(self._cleanup)
        canvas.extentsChanged.connect(self._update_preview)

        # pan tool, so dragging the map moves the print area
        pan_action = getattr(self.iface, "actionPan", None)
        if callable(pan_action):
            pan_action().trigger()

        self._update_preview(ensure_visible=True)
        self._dialog.show()

    def close(self):
        """Close the dialog (if open) and remove the preview."""
        if self._dialog is not None:
            self._dialog.reject()
        self._cleanup()

    @property
    def template_folder(self):
        output_folder = self.settings.get("output_folder") or os.path.expanduser("~")
        return os.path.join(output_folder, "print_templates")

    # --------------------------------------------------------------- private

    def _canvas_crs(self):
        return self.iface.mapCanvas().mapSettings().destinationCrs()

    def _frame_size(self, template_path):
        if template_path not in self._frame_sizes:
            layout = load_layout(QgsProject.instance(), template_path)
            self._frame_sizes[template_path] = map_frame_size_mm(layout)
        return self._frame_sizes[template_path]

    def _current_request(self):
        canvas = self.iface.mapCanvas()
        return PrintRequest(
            center=canvas.extent().center(),
            scale=self._dialog.selected_scale(),
            operator=str(self.settings.get("operator", "")).strip(),
            layers=canvas.layers(),
            crs=self._canvas_crs(),
            template_path=self._dialog.selected_template_path(),
        )

    def _current_extent(self):
        request = self._current_request()
        size = self._frame_size(request.template_path)
        return print_extent(request.center, request.scale, size, request.crs)

    def _on_options_changed(self):
        self._update_preview(ensure_visible=True)

    def _update_preview(self, *_args, ensure_visible=False):
        if self._dialog is None:
            return
        try:
            extent = self._current_extent()
        except ValueError as error:
            self._preview.clear()
            self._dialog.set_error(str(error))
            return

        self._dialog.set_error(None)
        self._preview.show(extent)

        to_meters = QgsUnitTypes.fromUnitToUnitFactor(
            self._canvas_crs().mapUnits(), Qgis.DistanceUnit.Meters
        )
        self._dialog.set_area(extent.width() * to_meters, extent.height() * to_meters)

        canvas = self.iface.mapCanvas()
        if ensure_visible and not canvas.extent().contains(extent):
            # zoom out so the whole print area can be seen; the centre is kept
            canvas.setExtent(extent.buffered(max(extent.width(), extent.height()) * 0.1))
            canvas.refresh()

    def _on_accepted(self):
        try:
            self._open_layout()
        finally:
            self._cleanup()

    def _open_layout(self):
        project = QgsProject.instance()
        try:
            result = build_print_layout(project, self._current_request())
            layout = register_layout(project, result.layout)
        except ValueError as error:
            utils.printWarningMessage(str(error))
            return

        self.last_layout = layout

        if not result.legend_fits:
            utils.printWarningMessage(
                "Tegnforklaringen er for stor for malen og kan være kuttet. "
                "Juster den i Layout Designer.",
                message_duration=8,
            )

        designer = self.iface.openLayoutDesigner(layout)
        if designer is None:
            utils.printWarningMessage("Kunne ikke åpne QGIS Layout Designer.")
            return
        add_save_template_action(designer, self.template_folder)

    def _cleanup(self, *_args):
        if self._preview is not None:
            self._preview.clear()
            self._preview = None
        if self._dialog is not None:
            try:
                self.iface.mapCanvas().extentsChanged.disconnect(self._update_preview)
            except (TypeError, RuntimeError):
                pass
            self._dialog.deleteLater()
            self._dialog = None
