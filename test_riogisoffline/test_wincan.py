"""Tests for WinCan live inspections: reader, model, calculator, watcher, map layers."""

import os
import sqlite3
import sys
import time
import uuid
import zipfile

import pytest
from pyvirtualdisplay import Display

from qgis.testing.mocked import get_iface  # noqa: F401  (starts QgsApplication)
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QEventLoop, QTimer

sys.path = [os.path.abspath('..')] + sys.path
from riogisoffline.plugin import wincan_controller as controller_module
from riogisoffline.plugin.condition_calculator import calculate_grade, is_condition_code
from riogisoffline.plugin.observation_layers import (
    CAMERA_LAYER, LINE_LAYER, POINT_LAYER, TRACK_LAYER, DEFAULT_STYLES, PipeLocator,
)
from riogisoffline.plugin.observation_model import (
    build_observations, is_reversed, parse_start_psid,
)
from riogisoffline.plugin.wincan_controller import WincanController, WincanPanel
from riogisoffline.plugin.wincan_reader import (
    Inspection, Observation, SnapshotBusy, find_active_database, read_database,
)
from riogisoffline.plugin.wincan_watcher import WincanWatcher

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    display = Display(visible=0, size=(800, 600))
    display.start()
    yield


@pytest.fixture(autouse=True)
def fake_qsettings(monkeypatch):
    store = {}

    class Settings:
        def value(self, key, default=None, type=None):
            value = store.get(key, default)
            return type(value) if type is not None and value is not None else value

        def setValue(self, key, value):
            store[key] = value

    monkeypatch.setattr(controller_module, "QSettings", Settings)
    return store


# --------------------------------------------------------------------------
# Synthetic WinCan database (same tables and columns as WinCan VX)
# --------------------------------------------------------------------------

class WincanDb:
    SCHEMA = """
    CREATE TABLE NODE (OBJ_PK TEXT, OBJ_Key TEXT, OBJ_Deleted TEXT);
    CREATE TABLE SECTION (OBJ_PK TEXT, OBJ_Key TEXT, OBJ_Length REAL, OBJ_SectionType TEXT,
                          OBJ_FromNode_REF TEXT, OBJ_ToNode_REF TEXT, OBJ_Deleted TEXT);
    CREATE TABLE SECINSP (INS_PK TEXT, INS_Section_FK TEXT, INS_InspectedLength REAL,
                          INS_StartDate TEXT, INS_TimeStamp TEXT, INS_Deleted TEXT);
    CREATE TABLE SECOBS (OBS_PK TEXT, OBS_Inspection_FK TEXT, OBS_Distance REAL, OBS_OpCode TEXT,
                         OBS_Observation TEXT, OBS_GradeS INTEGER, OBS_ClockPos1 INTEGER,
                         OBS_CD_Code1 INTEGER, OBS_CD_Code2 INTEGER, OBS_Memo TEXT,
                         OBS_TimeStamp TEXT, OBS_SortOrder INTEGER, OBS_Deleted TEXT);
    CREATE TABLE SECOBSMM (OMM_PK TEXT, OMM_Observation_FK TEXT, OMM_FileName TEXT,
                           OMM_SortOrder INTEGER, OMM_Deleted TEXT);
    """

    def __init__(self, path):
        self.path = str(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.executescript(self.SCHEMA)
        self._order = 0

    def _insert(self, sql, *args):
        con = sqlite3.connect(self.path)
        with con:
            con.execute(sql, args)
        con.close()

    def node(self, psid):
        pk = str(uuid.uuid4())
        self._insert("insert into NODE values (?,?,NULL)", pk, str(psid))
        return pk

    def section(self, lsid, from_psid, to_psid, length, deleted=None):
        pk = str(uuid.uuid4())
        self._insert("insert into SECTION values (?,?,?,?,?,?,?)", pk, str(lsid), length, "VL",
                     self.node(from_psid), self.node(to_psid), deleted)
        return pk

    def inspection(self, section_pk, start="2026-11-12 08:00:00", deleted=None):
        pk = str(uuid.uuid4())
        self._insert("insert into SECINSP values (?,?,0,?,?,?)", pk, section_pk, start, start, deleted)
        return pk

    def obs(self, inspection_pk, distance, code, grade=None, cd1=None, cd2=None, memo="",
            deleted=None, media=None, text=None):
        self._order += 1
        pk = str(uuid.uuid4())
        self._insert(
            "insert into SECOBS values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            pk, inspection_pk, distance, code, text or code, grade, 12, cd1, cd2, memo,
            "2026-11-12 08:{:02d}:00".format(self._order % 60), self._order, deleted,
        )
        if media:
            self._insert("insert into SECOBSMM values (?,?,?,1,NULL)", str(uuid.uuid4()), pk, media)
        return pk


def _inspection(observations, lsid="100", from_psid="1", to_psid="2", length=100.0):
    return Inspection(pk="i1", lsid=lsid, from_psid=from_psid, to_psid=to_psid,
                      section_length=length, section_type="VL", inspected_length=0,
                      start_time="", timestamp="", observations=observations)


def _obs(distance, code, grade=None, cd1=None, cd2=None, memo="", pk=None):
    return Observation(pk=pk or "{}@{}".format(code, distance), distance=distance, opcode=code,
                       text=code, grade_s=grade, clock=None, cd_code1=cd1, cd_code2=cd2,
                       memo=memo, timestamp="")


# --------------------------------------------------------------------------
# Condition calculator (port of VAV's FME calculator)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("fcode, code, grade, percent, expected", [
    ("AF", "SR3", 3, 0, 3),
    ("SP", "SR3", 3, 0, 3),
    ("OV", "SR2", 2, 0, 1),
    ("AF", "DF2", 2, 0, 1),
    ("AF", "SM1", 4, 0, 1),
    ("AF", "HI1", None, 0, 2),     # empty grade counts as 1 -> HI table gives 2
    ("AF", "HI1", 0, 0, 2),
    ("VL", "SR3", 3, 0, 1),        # pipe type not in the tables -> 1
    ("AF", "XX1", 3, 0, 1),        # unknown code -> 1
    ("AF", "SR2", 2, 60, 3),       # >= 50 % overrides
    ("AF", "SR2", 2, 49.9, 2),     # int(49.9) = 49, no override
    ("OV", "SR3", 3, 50, 3),
    ("AF", "KO2", 2, 80, 2),
    ("AF", "PF2", 2, 80, 2),       # no override for PF
])
def test_condition_calculator(fcode, code, grade, percent, expected):
    assert calculate_grade(fcode, code, grade, percent) == expected


def test_info_codes_are_not_graded():
    assert not any(is_condition_code(c) for c in ("SI", "IF", "VN", "ANM", "ME", "TK", "RE"))
    assert all(is_condition_code(c) for c in ("SR3", "PF1", "SM1", "HI2", "RØ1"))


# --------------------------------------------------------------------------
# Observation model
# --------------------------------------------------------------------------

def test_length_observations_are_paired_by_cd_codes():
    inspection = _inspection([
        _obs(0, "SI"),
        _obs(12.321, "SM1", 1, cd1=102, cd2=1),
        _obs(20.262, "SM1", cd1=202, cd2=9),
        _obs(22.607, "SM1", 1, cd1=103, cd2=1),
        _obs(27.32, "SM1", cd1=203, cd2=9),
        _obs(68.245, "IF"),
    ], length=73.94)

    lines = [o for o in build_observations(inspection, "AF") if o.is_line]

    assert [(o.start, o.end, o.open) for o in lines] == [(12.321, 20.262, False), (22.607, 27.32, False)]
    assert lines[0].percent == pytest.approx((20.262 - 12.321) / 73.94 * 100, abs=0.1)


def test_open_length_observation_ends_at_camera_while_inspecting():
    inspection = _inspection([_obs(0, "SI"), _obs(8.5, "PF1", 1, cd1=101, cd2=1), _obs(30.2, "SR1", 1)])
    line = next(o for o in build_observations(inspection, "AF") if o.is_line)
    assert (line.start, line.end, line.open) == (8.5, 30.2, True)


def test_open_length_observation_ends_at_inspection_end():
    inspection = _inspection([_obs(0, "SI"), _obs(8.5, "PF1", 1, cd1=101, cd2=1), _obs(68.2, "IF")])
    line = next(o for o in build_observations(inspection, "AF") if o.is_line)
    assert line.end == 68.2
    assert not line.open      # the inspection is finished, so it is no longer "ongoing"


def test_end_without_start_is_shown_as_point():
    inspection = _inspection([_obs(0, "SI"), _obs(20, "SM1", cd1=205, cd2=9)])
    observations = build_observations(inspection, "AF")
    assert [o.is_line for o in observations if o.opcode == "SM1"] == [False]


def test_info_and_point_observations():
    inspection = _inspection([_obs(0, "SI"), _obs(1.6, "SR3", 3), _obs(10, "ANM")])
    by_code = {o.opcode: o for o in build_observations(inspection, "AF")}
    assert by_code["SR3"].grade == 3 and not by_code["SR3"].is_info
    assert by_code["ANM"].is_info and by_code["ANM"].grade is None


@pytest.mark.parametrize("memo, expected", [
    ("I kum 396525", "396525"),
    ("I kum 388311", "388311"),
    ("Grøft ved kum 383255", None),
    ("", None),
])
def test_start_manhole_from_memo(memo, expected):
    assert parse_start_psid(memo, "388311", "396525") == expected


def test_direction_from_memo_and_flip():
    to_start = _inspection([_obs(0, "SI", memo="I kum 2")])
    from_start = _inspection([_obs(0, "SI", memo="I kum 1")])
    unknown = _inspection([_obs(0, "SI", memo="Grøft ved kum 9")])

    assert is_reversed(to_start)
    assert not is_reversed(from_start)
    assert not is_reversed(unknown)
    assert not is_reversed(to_start, flipped=True)
    assert is_reversed(unknown, flipped=True)


# --------------------------------------------------------------------------
# Reader
# --------------------------------------------------------------------------

def _project_db(root, name="2026_11_12_B210"):
    return WincanDb(os.path.join(str(root), name, "DB", name + ".db3"))


def test_reader_skips_deleted_rows_and_reads_media(tmp_path):
    db = _project_db(tmp_path)
    section = db.section(413460, 396120, 396121, 73.94)
    inspection = db.inspection(section)
    db.obs(inspection, 0, "SI", memo="I kum 396120")
    db.obs(inspection, 16.069, "SM1", cd1=202, cd2=9, deleted="2026-11-12 08:33:31")
    db.obs(inspection, 20.262, "SM1", cd1=202, cd2=9, media="bilde.jpg")
    deleted_section = db.section(414199, 1, 2, 11.24, deleted="2026-11-11")
    db.obs(db.inspection(deleted_section), 0, "SI")

    inspections = read_database(db.path)

    assert len(inspections) == 1
    read = inspections[0]
    assert (read.lsid, read.from_psid, read.to_psid, read.section_length) == ("413460", "396120", "396121", 73.94)
    assert [o.distance for o in read.observations] == [0, 20.262]
    assert read.observations[1].media == ["bilde.jpg"]
    assert read.start_memo == "I kum 396120"


def test_reader_treats_null_keys_as_missing(tmp_path):
    db = _project_db(tmp_path)
    db.obs(db.inspection(db.section(413925, "null", "null", 319.9)), 0, "SI")
    inspection = read_database(db.path)[0]
    assert inspection.from_psid is None and inspection.to_psid is None


def test_reader_does_not_touch_the_live_file(tmp_path):
    db = _project_db(tmp_path)
    db.obs(db.inspection(db.section(1, 1, 2, 10)), 0, "SI")
    before = os.stat(db.path)
    read_database(db.path)
    after = os.stat(db.path)
    assert (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size)
    assert not os.path.exists(db.path + "-journal")


def test_reader_backs_off_while_wincan_writes(tmp_path):
    db = _project_db(tmp_path)
    open(db.path + "-journal", "wb").close()
    with pytest.raises(SnapshotBusy):
        read_database(db.path)


def test_active_database_is_the_newest_project(tmp_path):
    old = _project_db(tmp_path, "2026_11_11_B210")
    new = _project_db(tmp_path, "2026_11_12_B210")
    WincanDb(os.path.join(str(tmp_path), "2026_11_12_B210", "DB", "2026_11_12_B210_Meta.db3"))
    os.utime(old.path, (time.time() + 100, time.time() + 100))

    assert find_active_database(str(tmp_path)) == old.path
    os.utime(new.path, (time.time() + 200, time.time() + 200))
    assert find_active_database(str(tmp_path)) == new.path
    # a project folder can also be chosen directly
    assert find_active_database(os.path.dirname(os.path.dirname(new.path))) == new.path
    assert find_active_database(str(tmp_path / "missing")) is None


# --------------------------------------------------------------------------
# Watcher
# --------------------------------------------------------------------------

def _wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_watcher_reads_on_start_and_after_changes(tmp_path):
    db = _project_db(tmp_path)
    inspection = db.inspection(db.section(1, 1, 2, 10))
    db.obs(inspection, 0, "SI")

    watcher = WincanWatcher(poll_ms=50, debounce_ms=20)
    received = []
    watcher.inspectionsChanged.connect(lambda path, inspections: received.append(inspections))
    watcher.set_root(str(tmp_path))
    watcher.start()
    try:
        assert len(received) == 1 and len(received[0][0].observations) == 1

        time.sleep(0.02)
        db.obs(inspection, 4.2, "SR3", 3)
        os.utime(db.path, (time.time() + 5, time.time() + 5))
        _wait(400)
        assert len(received[-1][0].observations) == 2
    finally:
        watcher.stop()


def test_watcher_waits_while_journal_exists(tmp_path):
    db = _project_db(tmp_path)
    db.obs(db.inspection(db.section(1, 1, 2, 10)), 0, "SI")
    open(db.path + "-journal", "wb").close()

    watcher = WincanWatcher(poll_ms=50, debounce_ms=20)
    received = []
    watcher.inspectionsChanged.connect(lambda path, inspections: received.append(inspections))
    watcher.set_root(str(tmp_path))
    watcher.start()
    try:
        _wait(200)
        assert received == []
        os.remove(db.path + "-journal")
        _wait(300)
        assert len(received) == 1
    finally:
        watcher.stop()


# --------------------------------------------------------------------------
# Map: locating, placing and drawing
# --------------------------------------------------------------------------

@pytest.fixture
def project():
    project = QgsProject.instance()
    project.clear()
    yield project
    project.clear()


def _map(project, pipe_wkt="LINESTRING(0 0, 100 0)", lsid=100, fcode="AF"):
    pipes = QgsVectorLayer("LineString?crs=EPSG:25832&field=lsid:integer&field=fcode:string",
                           "Avløpsledning", "memory")
    feature = QgsFeature(pipes.fields())
    feature.setAttributes([lsid, fcode])
    feature.setGeometry(QgsGeometry.fromWkt(pipe_wkt))
    pipes.dataProvider().addFeatures([feature])

    nodes = QgsVectorLayer("Point?crs=EPSG:25832&field=psid:integer", "Kum", "memory")
    features = []
    for psid, x in ((1, 0), (2, 100)):
        node = QgsFeature(nodes.fields())
        node.setAttributes([psid])
        node.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, 0)))
        features.append(node)
    nodes.dataProvider().addFeatures(features)
    project.addMapLayers([pipes, nodes])
    return pipes


@pytest.mark.parametrize("pipe_wkt, memo, section_length, expected_x", [
    ("LINESTRING(0 0, 100 0)", "I kum 1", 100, 10),    # from -> to, drawn from -> to
    ("LINESTRING(0 0, 100 0)", "I kum 2", 100, 90),    # inspected to -> from
    ("LINESTRING(100 0, 0 0)", "I kum 1", 100, 10),    # drawn to -> from
    ("LINESTRING(100 0, 0 0)", "I kum 2", 100, 90),
    ("LINESTRING(0 0, 100 0)", "I kum 1", 50, 20),     # WinCan length differs from map
])
def test_observation_is_placed_along_the_pipe(project, pipe_wkt, memo, section_length, expected_x):
    _map(project, pipe_wkt)
    inspection = _inspection([_obs(0, "SI", memo=memo)], length=section_length)
    pipe = PipeLocator(project, DEFAULT_STYLES).find_pipe("100", "1", "2")

    point = pipe.point_at(10, is_reversed(inspection), section_length).asPoint()

    assert point.x() == pytest.approx(expected_x)
    assert pipe.fcode == "AF"


@pytest.mark.parametrize("intervals, expected", [
    ([(8.5, 67.9), (12.3, 20.3), (22.6, 27.3), (55.6, 67.9)], [0, 1, 1, 1]),
    ([(0, 10), (10, 20)], [0, 0]),                 # touching, not overlapping
    ([(0, 30), (5, 25), (10, 20)], [0, 1, 2]),
    ([], []),
])
def test_overlapping_length_observations_get_separate_lanes(intervals, expected):
    from riogisoffline.plugin.observation_layers import assign_lanes
    assert assign_lanes(intervals) == expected


def test_laterals_with_the_same_lsid_are_not_used(project):
    """Stikkledninger carry the main pipe's LSID; they must never be taken as the pipe."""
    laterals = QgsVectorLayer("LineString?crs=EPSG:25832&field=lsid:integer&field=fcode:string",
                              "Stikkledninger", "memory")
    lateral = QgsFeature(laterals.fields())
    lateral.setAttributes([100, "AF"])
    lateral.setGeometry(QgsGeometry.fromWkt("LINESTRING(500 500, 505 505)"))
    laterals.dataProvider().addFeatures([lateral])
    project.addMapLayer(laterals)
    locator = PipeLocator(project, DEFAULT_STYLES)

    assert locator.find_pipe("100") is None

    _map(project)
    pipe = locator.find_pipe("100", "1", "2")
    assert pipe.geometry.length() == pytest.approx(100)


def _controller(project, tmp_path, follow=False):
    panel = WincanPanel()
    iface = get_iface()
    controller = WincanController(iface, {}, panel, project=project,
                                  watcher=WincanWatcher(poll_ms=60000))
    if follow:
        panel.folder.setFilePath(str(tmp_path))
        panel.follow.setChecked(True)
    return controller, panel


def test_follow_requires_a_folder(project, tmp_path):
    controller, panel = _controller(project, tmp_path)
    panel.follow.setChecked(True)
    assert not panel.follow.isChecked()
    assert "mappen" in panel.status.text()
    controller.stop()


def _features(controller, name):
    return list(controller.layers.layer(name).getFeatures())


def _demo_db(tmp_path, lsid=100, memo="I kum 1", finished=False):
    db = _project_db(tmp_path)
    inspection = db.inspection(db.section(lsid, 1, 2, 100))
    db.obs(inspection, 0, "SI", memo=memo)
    db.obs(inspection, 5, "SR3", 3)
    db.obs(inspection, 10, "SM1", 1, cd1=101, cd2=1)
    db.obs(inspection, 30, "SM1", cd1=201, cd2=9)
    db.obs(inspection, 40, "ANM")
    db.obs(inspection, 45, "PF1", 1, cd1=102, cd2=1)
    db.obs(inspection, 50, "VN")
    if finished:
        db.obs(inspection, 60, "IF")
    return db


def test_controller_draws_live_inspection(project, tmp_path):
    _map(project)
    db = _demo_db(tmp_path)
    controller, panel = _controller(project, tmp_path, follow=True)

    controller._on_inspections(db.path, read_database(db.path))

    points = {f["code"]: f for f in _features(controller, POINT_LAYER)}
    lines = {f["code"]: f for f in _features(controller, LINE_LAYER)}
    assert points["SR3"]["grade"] == 3 and points["SR3"].geometry().asPoint().x() == pytest.approx(5)
    assert points["ANM"]["info"] == 1
    assert lines["SM1"]["distance"] == 10 and lines["SM1"]["end_distance"] == 30
    assert lines["SM1"].geometry().length() == pytest.approx(20)
    # open length observation runs to the camera
    assert lines["PF1"]["open"] == 1 and lines["PF1"]["end_distance"] == 50
    camera = _features(controller, CAMERA_LAYER)
    assert len(camera) == 1 and camera[0].geometry().asPoint().x() == pytest.approx(50)
    assert _features(controller, TRACK_LAYER)[0].geometry().length() == pytest.approx(50)
    assert "LSID 100" in panel.status.text() and "50.0 m" in panel.status.text()
    controller.stop(remove_layers=True)


def test_finished_inspection_has_no_camera(project, tmp_path):
    _map(project)
    db = _demo_db(tmp_path, finished=True)
    controller, panel = _controller(project, tmp_path)
    controller._on_inspections(db.path, read_database(db.path))

    assert _features(controller, CAMERA_LAYER) == []
    pf1 = next(f for f in _features(controller, LINE_LAYER) if f["code"] == "PF1")
    assert pf1["end_distance"] == 60
    assert pf1["open"] == 0
    controller.stop(remove_layers=True)


def test_flip_direction_mirrors_observations(project, tmp_path):
    _map(project)
    db = _demo_db(tmp_path)
    controller, panel = _controller(project, tmp_path, follow=True)
    controller._on_inspections(db.path, read_database(db.path))

    controller.flip_active()

    sr3 = next(f for f in _features(controller, POINT_LAYER) if f["code"] == "SR3")
    assert sr3.geometry().asPoint().x() == pytest.approx(95)
    controller.stop(remove_layers=True)


def test_missing_pipe_is_reported(project, tmp_path):
    _map(project)
    db = _demo_db(tmp_path, lsid=999)
    controller, panel = _controller(project, tmp_path, follow=True)
    controller._on_inspections(db.path, read_database(db.path))

    assert "999" in panel.status.text()
    controller.stop(remove_layers=True)


def test_layers_come_back_after_map_reload(project, tmp_path):
    _map(project)
    db = _demo_db(tmp_path)
    controller, panel = _controller(project, tmp_path)
    controller._on_inspections(db.path, read_database(db.path))

    project.clear()          # "Last kart" clears the project
    _map(project)
    controller.redraw()

    assert len(_features(controller, POINT_LAYER)) > 0
    assert project.layerTreeRoot().findGroup("WinCan-inspeksjon") is not None
    controller.stop(remove_layers=True)


def test_info_codes_hidden_by_default_and_can_be_shown(project, tmp_path):
    _map(project)
    db = _demo_db(tmp_path)
    controller, panel = _controller(project, tmp_path)
    controller._on_inspections(db.path, read_database(db.path))

    def info_rule_active():
        rules = controller.layers.layer(POINT_LAYER).renderer().rootRule().children()
        return next(r for r in rules if r.label() == "Info-kode").active()

    assert not info_rule_active()
    panel.show_info.setChecked(True)
    assert info_rule_active()
    controller.stop(remove_layers=True)


# --------------------------------------------------------------------------
# Real example data (only when the example zips are present locally)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(os.path.join(EXAMPLES, "2026_11_12_B210.zip")),
                    reason="example WinCan data not available")
def test_real_example_inspections(tmp_path):
    with zipfile.ZipFile(os.path.join(EXAMPLES, "2026_11_12_B210.zip")) as archive:
        archive.extract("2026_11_12_B210/DB/2026_11_12_B210.db3", str(tmp_path))
    db_path = find_active_database(str(tmp_path))
    inspections = {i.lsid: i for i in read_database(db_path)}

    assert is_reversed(inspections["414198"])          # "I kum 396525" = to-manhole
    assert not is_reversed(inspections["413460"])      # "I kum 396120" = from-manhole

    lines = [o for o in build_observations(inspections["413460"], "AF") if o.is_line]
    sm = next(o for o in lines if o.start == pytest.approx(12.321))
    assert sm.end == pytest.approx(20.262)             # deleted end at 16.069 is ignored
    assert all(not o.open for o in lines)
