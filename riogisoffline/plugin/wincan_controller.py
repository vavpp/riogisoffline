"""
WinCan live: the panel section, and the glue between the folder watcher,
the observation model and the map layers.
"""

import json
import os

from qgis.core import QgsProject
from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .observation_layers import (
    CAMERA_LAYER,
    LINE_LAYER,
    POINT_LAYER,
    TRACK_LAYER,
    ObservationLayers,
    PipeLocator,
    assign_lanes,
    merged_styles,
)
from .observation_model import (
    active_inspection,
    build_observations,
    end_distance,
    is_reversed,
)
from .crash_reporter import breadcrumb
from .wincan_watcher import WincanWatcher

ROOT_SETTING = "riogisoffline/wincan_root"
FOLLOW_SETTING = "riogisoffline/wincan_follow"
INFO_SETTING = "riogisoffline/wincan_show_info"
FLIP_SETTING = "riogisoffline/wincan_flipped"


class WincanPanel(QGroupBox):
    """Panel section "WinCan live"."""

    def __init__(self, parent=None):
        super().__init__("WinCan live", parent)

        help_text = QLabel(
            "Velg mappen WinCan lagrer inspeksjoner i (f.eks. D:\\TV-rapporter). "
            "Observasjonene tegnes i kartet mens inspeksjonen pågår."
        )
        help_text.setWordWrap(True)

        self.folder = QgsFileWidget()
        self.folder.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)
        self.folder.setDialogTitle("Velg WinCan-mappe")

        self.follow = QCheckBox("Følg aktive inspeksjoner")
        self.status = QLabel("Ikke startet")
        self.status.setWordWrap(True)
        self.status.setObjectName("wincanStatus")

        self.zoom_button = QPushButton("Zoom til aktiv")
        self.flip_button = QPushButton("Snu retning")
        self.flip_button.setToolTip(
            "Bruk når observasjonene havner i feil ende av ledningen "
            "(startkummen er lest fra merknaden ved \"Start inspeksjon\")."
        )
        buttons = QHBoxLayout()
        buttons.addWidget(self.zoom_button)
        buttons.addWidget(self.flip_button)

        self.show_info = QCheckBox("Vis info-koder (SI, IF, VN, ANM …)")

        layout = QVBoxLayout(self)
        layout.addWidget(help_text)
        layout.addWidget(self.folder)
        layout.addWidget(self.follow)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        layout.addWidget(self.show_info)


class WincanController:
    def __init__(self, iface, settings, panel, project=None, watcher=None, default_root=""):
        self.iface = iface
        self.panel = panel
        self.project = project or QgsProject.instance()
        self.styles = merged_styles(settings)

        qsettings = QSettings()
        self._flipped = set(json.loads(qsettings.value(FLIP_SETTING, "[]") or "[]"))
        show_info = qsettings.value(INFO_SETTING, False, type=bool)

        self.locator = PipeLocator(self.project, self.styles)
        self.layers = ObservationLayers(self.project, self.styles, show_info)
        self.watcher = watcher or WincanWatcher()

        self.db_path = ""
        self.inspections = []
        self.active = None
        self.missing_lsids = []

        root = qsettings.value(ROOT_SETTING, "") or default_root or ""
        panel.folder.setFilePath(root)
        panel.show_info.setChecked(show_info)
        panel.follow.setChecked(qsettings.value(FOLLOW_SETTING, False, type=bool) and bool(root))

        self.watcher.set_root(root)
        self.watcher.inspectionsChanged.connect(self._on_inspections)
        self.watcher.databaseChanged.connect(self._on_database)
        self.watcher.readFailed.connect(self._set_status)

        panel.folder.fileChanged.connect(self._on_folder)
        panel.follow.toggled.connect(self._on_follow)
        panel.show_info.toggled.connect(self._on_show_info)
        panel.zoom_button.clicked.connect(self.zoom_to_active)
        panel.flip_button.clicked.connect(self.flip_active)

        self._update_buttons()
        if panel.follow.isChecked():
            self.watcher.start()
        else:
            self._set_status("Ikke startet")

    # ---------------------------------------------------------------- panel

    def _on_folder(self, path):
        QSettings().setValue(ROOT_SETTING, path or "")
        self.watcher.set_root(path)
        if not path:
            self.panel.follow.setChecked(False)

    def _on_follow(self, follow):
        breadcrumb("WinCan: følg {}".format("på" if follow else "av"))
        QSettings().setValue(FOLLOW_SETTING, bool(follow))
        if follow:
            if not self.watcher.root:
                # uncheck first: that runs this handler again and sets "Ikke startet"
                self.panel.follow.setChecked(False)
                self._set_status("Velg WinCan-mappen først.")
                return
            self.watcher.start()
            if not self.watcher.db_path:
                self._set_status("Fant ingen WinCan-database i mappen ennå.")
        else:
            self.watcher.stop()
            self._set_status("Ikke startet")
        self._update_buttons()

    def _on_show_info(self, show):
        QSettings().setValue(INFO_SETTING, bool(show))
        self.layers.set_show_info(show)

    def _update_buttons(self):
        has_active = self.active is not None and self.panel.follow.isChecked()
        self.panel.zoom_button.setEnabled(has_active)
        self.panel.flip_button.setEnabled(has_active)

    def _set_status(self, text):
        self.panel.status.setText(text)

    # -------------------------------------------------------------- watcher

    def _on_database(self, db_path):
        self.db_path = db_path
        if not db_path:
            self.inspections = []
            self.active = None
            self.layers.clear()
            self._update_buttons()

    def _on_inspections(self, db_path, inspections):
        self.db_path = db_path
        self.inspections = inspections
        self.redraw()

    # --------------------------------------------------------------- drawing

    def redraw(self):
        """Draw the current inspections (also used after the map has been reloaded)."""
        self.active = active_inspection(self.inspections)
        rows = {POINT_LAYER: [], LINE_LAYER: [], TRACK_LAYER: [], CAMERA_LAYER: []}
        self.missing_lsids = []
        crs = None

        for inspection in self.inspections:
            pipe = self.locator.find_pipe(inspection.lsid, inspection.from_psid, inspection.to_psid)
            if pipe is None:
                self.missing_lsids.append(inspection.lsid or "?")
                continue
            crs = crs or pipe.crs
            self._rows_for(inspection, pipe, inspection is self.active, rows)

        if self.inspections:
            self.layers.ensure(crs or self.project.crs())
            for name, layer_rows in rows.items():
                signature = tuple(
                    (geometry.asWkt(3), tuple(sorted(attributes.items())))
                    for geometry, attributes in layer_rows
                )
                self.layers.replace(name, layer_rows, signature)
        else:
            self.layers.clear()

        self._update_status()
        self._update_buttons()

    def _rows_for(self, inspection, pipe, is_active, rows):
        reversed_ = is_reversed(inspection, inspection.pk in self._flipped)
        section_length = inspection.section_length
        observations = build_observations(
            inspection, pipe.fcode or inspection.section_type,
            reference_length=section_length or pipe.length,
        )

        track = pipe.segment(0.0, end_distance(inspection), reversed_, section_length)
        if track is not None:
            rows[TRACK_LAYER].append((track, {
                "lsid": inspection.lsid, "inspection": inspection.pk,
                "distance": end_distance(inspection),
                "finished": int(inspection.is_finished), "active": int(is_active),
            }))

        if is_active and not inspection.is_finished:
            rows[CAMERA_LAYER].append((
                pipe.point_at(inspection.camera_distance, reversed_, section_length),
                {"lsid": inspection.lsid, "distance": inspection.camera_distance},
            ))

        line_observations = [obs for obs in observations if obs.is_line]
        lanes = dict(zip(
            (obs.pk for obs in line_observations),
            assign_lanes([(obs.start, obs.end) for obs in line_observations]),
        ))

        for obs in observations:
            geometry = None
            if obs.is_line:
                geometry = pipe.segment(obs.start, obs.end, reversed_, section_length)
            target = LINE_LAYER if geometry is not None else POINT_LAYER
            if geometry is None:
                geometry = pipe.point_at(obs.start, reversed_, section_length)
            rows[target].append((geometry, {
                "pk": obs.pk, "lsid": inspection.lsid, "inspection": inspection.pk,
                "code": obs.opcode, "description": obs.text,
                "distance": round(obs.start, 3),
                "end_distance": None if obs.end is None else round(obs.end, 3),
                "clock": obs.clock, "grade_wincan": obs.grade_s, "grade": obs.grade,
                "percent": obs.percent, "info": int(obs.is_info), "open": int(obs.open),
                "timestamp": obs.timestamp, "media": "; ".join(obs.media),
                "active": int(is_active),
                "lane": lanes.get(obs.pk, 0) if target == LINE_LAYER else 0,
            }))

    def _update_status(self):
        if not self.panel.follow.isChecked():
            return
        if not self.db_path:
            self._set_status("Fant ingen WinCan-database i mappen ennå.")
            return
        project_name = os.path.basename(os.path.dirname(os.path.dirname(self.db_path)))
        parts = ["Følger {}".format(project_name)]
        if self.active is not None:
            count = sum(1 for obs in self.active.observations if obs.opcode not in ("SI", "IF"))
            state = "ferdig" if self.active.is_finished else "{:.1f} m".format(self.active.camera_distance)
            parts.append("LSID {} · {} · {} obs.".format(self.active.lsid, state, count))
        else:
            parts.append("ingen inspeksjoner ennå")
        text = " · ".join(parts)
        if self.missing_lsids:
            text += "\nFinnes ikke i kartet: LSID {}".format(", ".join(self.missing_lsids))
        self._set_status(text)

    # -------------------------------------------------------------- actions

    def zoom_to_active(self):
        if self.active is None:
            return
        pipe = self.locator.find_pipe(self.active.lsid, self.active.from_psid, self.active.to_psid)
        if pipe is None:
            return
        extent = pipe.geometry.boundingBox()
        extent.grow(max(extent.width(), extent.height(), 10) * 0.25)
        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

    def flip_active(self):
        if self.active is None:
            return
        breadcrumb("WinCan: snu retning LSID {}".format(self.active.lsid))
        self._flipped ^= {self.active.pk}
        QSettings().setValue(FLIP_SETTING, json.dumps(sorted(self._flipped)))
        self.redraw()

    def stop(self, remove_layers=False):
        self.watcher.stop()
        if remove_layers:
            self.layers.remove()
