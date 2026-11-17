"""Regression tests for bugs found in code review."""

import json
import os
import sys
from types import SimpleNamespace

import pytest
from pyvirtualdisplay import Display

from qgis.testing.mocked import get_iface
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import QListWidget

sys.path = [os.path.abspath('..')] + sys.path
from riogisoffline.plugin import utils
from riogisoffline.plugin.riogis import RioGIS
from riogisoffline.plugin.change_status_dialog import ChangeStatusDialog
from riogisoffline.plugin.change_project_status_dialog import ChangeProjectStatusDialog
from riogisoffline.plugin.multi_thread_job import SyncWorker, UploadWorker
from riogisoffline.plugin.search_box import SearchBox


@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    display = Display(visible=0, size=(800, 600))
    display.start()
    yield


@pytest.fixture
def user_settings(tmp_path, monkeypatch):
    """Point user settings and status CSV files at a temp folder."""
    file_folder = tmp_path / "filer"
    file_folder.mkdir()
    settings_path = tmp_path / "bruker_settings.json"
    settings_path.write_text(json.dumps({"file_folder": str(file_folder)}), encoding="utf-8")
    monkeypatch.setattr(utils, "get_user_settings_path", lambda: str(settings_path))
    monkeypatch.setattr(utils, "save_and_write_project", lambda: None)
    return file_folder


@pytest.fixture
def layers():
    """An order layer and a project layer whose features share feature id 1."""
    project = QgsProject.instance()
    project.clear()

    orders = QgsVectorLayer(
        "LineString?crs=EPSG:25832&field=lsid:integer&field=status_internal:integer"
        "&field=project_area_id:string&field=fcode:string",
        "Bestillinger",
        "memory",
    )
    order = QgsFeature(orders.fields())
    order.setAttributes([123, 1, "P1", "AF"])
    order.setGeometry(QgsGeometry.fromWkt("LINESTRING(0 0, 10 0)"))
    orders.dataProvider().addFeatures([order])

    projects = QgsVectorLayer(
        "Polygon?crs=EPSG:25832&field=project_area_id:string&field=status:integer"
        "&field=project_name:string&field=comments:string",
        "Prosjekt",
        "memory",
    )
    proj = QgsFeature(projects.fields())
    proj.setAttributes(["P1", 4, "Testprosjekt", ""])
    proj.setGeometry(QgsGeometry.fromWkt("POLYGON((-5 -5, 15 -5, 15 5, -5 5, -5 -5))"))
    projects.dataProvider().addFeatures([proj])

    project.addMapLayers([orders, projects])
    yield SimpleNamespace(orders=orders, projects=projects)
    project.clear()


@pytest.fixture
def riogis():
    plugin = RioGIS(get_iface())
    plugin.run()
    return plugin


def _snapshot(layer):
    return [(f.id(), f.attributes(), f.geometry().asWkt()) for f in layer.getFeatures()]


def test_change_status_writes_to_order_layer_even_if_project_layer_was_selected_last(
    riogis, layers, user_settings
):
    # state after "select project" followed by clicking an order in the list
    riogis.layer = layers.projects
    riogis.feature = next(layers.orders.getFeatures())
    projects_before = _snapshot(layers.projects)

    dialog = ChangeStatusDialog(riogis)
    dialog.populate_select_values()
    dialog.cmbSelectStatus.setCurrentText("Kunne ikke inspiseres")
    dialog.textComment.setPlainText("Blokkert")
    dialog.run()

    assert next(layers.orders.getFeatures())["status_internal"] == 3
    assert _snapshot(layers.projects) == projects_before
    assert (user_settings / "changed_status.csv").exists()


def test_change_project_status_writes_to_project_layer_even_if_order_layer_was_selected_last(
    riogis, layers, user_settings
):
    # state after "select project" followed by clicking a pipe on the map
    riogis.layer = layers.orders
    riogis.selected_project = next(layers.projects.getFeatures())
    orders_before = _snapshot(layers.orders)

    dialog = ChangeProjectStatusDialog(riogis)
    dialog.populate_select_values()
    dialog.cmbSelectStatus.setCurrentText("Bestilt")
    dialog.run()

    assert next(layers.projects.getFeatures())["status"] == 1
    assert _snapshot(layers.orders) == orders_before


def test_export_status_update_does_not_touch_project_layer(riogis, layers, user_settings):
    riogis.layer = layers.projects
    riogis.feature = next(layers.orders.getFeatures())
    projects_before = _snapshot(layers.projects)

    riogis.update_feature_status()

    assert next(layers.orders.getFeatures())["status_internal"] == 2
    assert _snapshot(layers.projects) == projects_before


@pytest.mark.parametrize(
    "status_before, status_after, reported_status",
    [
        (1, 2, 2),     # bestilt -> under utførelse
        (2, 2, 2),
        (3, 3, 3),     # kunne ikke inspiseres
        (4, 4, 4),     # fullført stays fullført
        (5, 5, 5),     # avbrutt
        (8, 8, 8),     # må spyles
    ],
)
def test_export_status_reporting(
    riogis, layers, user_settings, tmp_path, status_before, status_after, reported_status
):
    from riogisoffline.plugin.export_dialog import ExportDialog

    feature = next(layers.orders.getFeatures())
    layers.orders.dataProvider().changeAttributeValues(
        {feature.id(): {layers.orders.fields().indexOf("status_internal"): status_before}}
    )
    riogis.feature = next(layers.orders.getFeatures())
    riogis.data = riogis.get_feature_data()
    riogis.settings.update({"operator": "Ola Nordmann", "output_folder": str(tmp_path / "output")})

    ExportDialog(riogis).export()

    rows = (user_settings / "changed_status.csv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    assert rows[1].split(",")[1] == str(reported_status)
    assert next(layers.orders.getFeatures())["status_internal"] == status_after


def _write_sqlite(path, rows):
    """Write a 'Bestillinger' layer to a SQLite file, like oslo_offline.db."""
    from qgis.core import QgsCoordinateTransformContext, QgsVectorFileWriter

    layer = QgsVectorLayer(
        "LineString?crs=EPSG:25832&field=objectid:integer&field=lsid:integer"
        "&field=status_internal:integer&field=project_area_id:string",
        "Bestillinger",
        "memory",
    )
    features = []
    for lsid, status in rows:
        feature = QgsFeature(layer.fields())
        feature.setAttributes([0, lsid, status, "P1"])
        feature.setGeometry(QgsGeometry.fromWkt(f"LINESTRING({lsid} 0, {lsid} 10)"))
        features.append(feature)
    layer.dataProvider().addFeatures(features)

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "SQLite"
    options.layerName = "Bestillinger"
    # QGIS appends the driver extension, so write as .sqlite and rename to .db
    written = str(path) + ".sqlite"
    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, written, QgsCoordinateTransformContext(), options
    )
    assert error[0] == QgsVectorFileWriter.NoError, error
    del layer
    os.replace(written, str(path))


def _read_statuses(path):
    layer = QgsVectorLayer(f"{path}|layername=Bestillinger", "check", "ogr")
    assert layer.isValid()
    return sorted((f["lsid"], f["status_internal"]) for f in layer.getFeatures())


def _syncronizer(tmp_path, worker):
    from riogisoffline.plugin.syncronizer import Syncronizer

    sync = Syncronizer.__new__(Syncronizer)
    sync.worker = worker
    sync._filename = str(tmp_path / "oslo_offline.db")
    sync._up_filename = str(tmp_path / "oslo_offline_update.db")
    sync.changed_status_filepath = str(tmp_path / "changed_status.csv")
    sync.changed_project_status_filepath = str(tmp_path / "changed_project_status.csv")
    sync._layer_definitions = ["Bestillinger"]
    return sync


def _signal_recorder():
    events = []
    signal = lambda name: SimpleNamespace(emit=lambda *args: events.append((name, args)))
    worker = SimpleNamespace(**{name: signal(name) for name in
                                ["progress", "process_name", "info", "warning", "error", "finished"]})
    return worker, events


def test_sync_merges_in_a_worker_thread_without_touching_the_qgis_project(tmp_path, monkeypatch):
    import threading

    _write_sqlite(tmp_path / "oslo_offline.db", [(1, 1), (2, 1)])
    _write_sqlite(tmp_path / "oslo_offline_update.db", [(1, 1), (2, 1), (3, 1)])
    (tmp_path / "changed_status.csv").write_text(
        "lsid,new_status,comment,project_area_id\n2,4,,P1\n", encoding="utf-8"
    )

    def forbidden():
        raise AssertionError("QGIS project must not be written from the sync thread")

    monkeypatch.setattr(utils, "save_and_write_project", forbidden)
    monkeypatch.setattr(QgsProject.instance(), "write", forbidden)

    worker, events = _signal_recorder()
    sync = _syncronizer(tmp_path, worker)
    monkeypatch.setattr(sync, "_setup", lambda: None)
    monkeypatch.setattr(sync, "_fetch", lambda: None)

    errors = []

    def run():
        try:
            sync.sync_now()
        except Exception as e:  # surfaced in the assertion below
            errors.append(e)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=60)

    assert not errors
    assert ("finished", (False,)) in events
    # new feature from the update file is added, local status change is re-applied
    assert _read_statuses(tmp_path / "oslo_offline.db") == [(1, 1), (2, 4), (3, 1)]


def test_sync_fails_loudly_when_local_layer_cannot_be_opened(tmp_path):
    _write_sqlite(tmp_path / "oslo_offline_update.db", [(1, 1)])
    worker, _ = _signal_recorder()
    sync = _syncronizer(tmp_path, worker)

    with pytest.raises(RuntimeError, match="Bestillinger"):
        sync._update("Bestillinger")


def test_run_twice_reuses_dock_widget(riogis):
    first = riogis.dlg
    riogis.run()
    assert riogis.dlg is first


class _FakeBlobService:
    def __init__(self):
        self.uploaded = []

    def get_container_client(self, container):
        service = self

        class Container:
            def get_blob_client(self, path):
                class Blob:
                    def upload_blob(self, data, overwrite=False):
                        service.uploaded.append((path, json.loads(data)))
                return Blob()
        return Container()


def _connection():
    from riogisoffline.plugin.azure_blob_storage_connection import AzureBlobStorageConnection

    connection = AzureBlobStorageConnection.__new__(AzureBlobStorageConnection)
    connection.env = "prod"
    connection.wincan_files_container_name = "wincan-files"
    connection.blob_service_client = _FakeBlobService()
    return connection


def test_project_status_is_uploaded_when_there_are_no_pipe_status_changes(riogis, user_settings):
    csv_path = user_settings / "changed_project_status.csv"
    csv_path.write_text("GlobalID,new_status,comments_inspector\nP1,2,ok\n", encoding="utf-8")

    connection = _connection()
    connection.upload_status_changes(riogis.settings)

    uploaded = connection.blob_service_client.uploaded
    assert len(uploaded) == 1
    assert uploaded[0][1] == {"GlobalID": "P1", "new_status": 2, "comments_inspector": "ok"}
    assert not csv_path.exists()


def test_empty_comment_is_uploaded_as_empty_string(riogis, user_settings):
    # this is what export writes: comment=""
    utils.write_changed_status_to_file(riogis.settings, 123, 2, "", "P1")

    connection = _connection()
    connection.upload_status_changes(riogis.settings)

    uploaded = connection.blob_service_client.uploaded
    assert len(uploaded) == 1
    assert uploaded[0][1] == {"lsid": 123, "new_status": 2, "comment": "", "project_area_id": "P1"}


def test_status_file_with_missing_columns_is_kept(riogis, user_settings):
    csv_path = user_settings / "changed_status.csv"
    csv_path.write_text("lsid,new_status\n123,2\n", encoding="utf-8")
    warnings = []
    worker = SimpleNamespace(warning=SimpleNamespace(emit=warnings.append))

    connection = _connection()
    connection.upload_status_changes(riogis.settings, worker=worker)

    assert connection.blob_service_client.uploaded == []
    assert csv_path.exists()
    assert len(warnings) == 1


@pytest.mark.parametrize("worker_class, button", [(SyncWorker, "btnSync"), (UploadWorker, "btnUpload")])
def test_buttons_are_enabled_again_after_failure(riogis, worker_class, button):
    args = (riogis, []) if worker_class is UploadWorker else (riogis,)
    worker = worker_class(*args)
    worker.prepare()
    assert not getattr(riogis.dlg, button).isEnabled()

    worker.finished_running(has_failed=True)

    assert getattr(riogis.dlg, button).isEnabled()


def test_search_with_quote_does_not_break(layers):
    feature = next(layers.projects.getFeatures())
    layers.projects.dataProvider().changeAttributeValues(
        {feature.id(): {layers.projects.fields().indexOf("project_name"): "O'Brien"}}
    )
    results = QListWidget()
    dlg = SimpleNamespace(searchResults=results)
    canvas = SimpleNamespace(layers=lambda: [layers.projects])
    iface = SimpleNamespace(mapCanvas=lambda: canvas)

    SearchBox(dlg, iface).onTextChanged("O'B")

    assert results.count() == 1
    assert results.item(0).text().startswith("O'Brien")
