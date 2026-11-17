"""Tests for map printing: layout, legend fitting, dialog and print preview."""

import gc
import os
import sys
from types import SimpleNamespace

import pytest
from pyvirtualdisplay import Display

from qgis.testing.mocked import get_iface  # noqa: F401  (starts QgsApplication)
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsLayoutExporter,
    QgsPointXY,
    QgsProject,
    QgsReadWriteContext,
    QgsRectangle,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas
from qgis.PyQt import sip
from qgis.PyQt.QtWidgets import QMenu, QWidget

sys.path = [os.path.abspath('..')] + sys.path
from riogisoffline.plugin import print_options_dialog as dialog_module
from riogisoffline.plugin.print_controller import PrintController
from riogisoffline.plugin.print_layout import (
    LEGEND_ID,
    MAP_ID,
    PRINT_SCALES,
    PrintRequest,
    add_save_template_action,
    build_print_layout,
    export_layout_to_pdf,
    print_extent,
    register_layout,
    scale_bar_segment_length,
)
from riogisoffline.plugin.print_options_dialog import PrintOptionsDialog, nearest_print_scale

CRS = QgsCoordinateReferenceSystem("EPSG:25832")
CENTER = QgsPointXY(597000, 6643000)


@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    display = Display(visible=0, size=(800, 600))
    display.start()
    yield


@pytest.fixture(autouse=True)
def fake_qsettings(monkeypatch):
    """Keep the dialog from writing to the real QGIS settings."""
    store = {}

    class Settings:
        def value(self, key, default=None, type=None):
            value = store.get(key, default)
            return type(value) if type is not None and value is not None else value

        def setValue(self, key, value):
            store[key] = value

    monkeypatch.setattr(dialog_module, "QSettings", Settings)
    return store


@pytest.fixture
def project():
    project = QgsProject.instance()
    project.clear()
    yield project
    project.clear()


def _line_layer(name, rules=3, features=True, center=CENTER):
    layer = QgsVectorLayer(
        "LineString?crs=EPSG:25832&field=kind:integer", name, "memory"
    )
    if features:
        feature = QgsFeature(layer.fields())
        feature.setAttributes([1])
        feature.setGeometry(QgsGeometry.fromWkt(
            f"LINESTRING({center.x() - 20} {center.y()}, {center.x() + 20} {center.y()})"
        ))
        layer.dataProvider().addFeatures([feature])

    renderer = QgsRuleBasedRenderer(QgsSymbol.defaultSymbol(layer.geometryType()))
    root = renderer.rootRule()
    # clone before removing: removeChildAt deletes the original rule
    template = root.children()[0].clone()
    root.removeChildAt(0)
    for i in range(rules):
        rule = template.clone()
        rule.setLabel(f"{name} regel {i + 1}")
        rule.setFilterExpression(f'"kind" = {i + 1}')
        root.appendChild(rule)
    layer.setRenderer(renderer)
    return layer


def _request(layers, scale=1000, template_path=None, operator="Ola Nordmann"):
    return PrintRequest(
        center=CENTER, scale=scale, operator=operator, layers=layers,
        crs=CRS, template_path=template_path,
    )


# ------------------------------------------------------------------ layout

def test_print_extent_matches_scale():
    extent = print_extent(CENTER, 1000, (200, 190), CRS)
    assert extent.width() == pytest.approx(200)
    assert extent.height() == pytest.approx(190)
    assert extent.center().x() == pytest.approx(CENTER.x())


@pytest.mark.parametrize("scale", PRINT_SCALES)
def test_map_gets_exact_scale_and_center(project, scale):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)

    layout = build_print_layout(project, _request([layer], scale=scale)).layout
    map_item = layout.itemById(MAP_ID)

    assert map_item.scale() == pytest.approx(scale, rel=1e-3)
    assert map_item.extent().center().x() == pytest.approx(CENTER.x(), abs=0.5)
    assert map_item.extent().center().y() == pytest.approx(CENTER.y(), abs=0.5)


def test_scale_bar_segments_are_round_numbers():
    assert [scale_bar_segment_length(s) for s in PRINT_SCALES] == [10, 20, 50, 100, 200]


def test_layout_contains_expected_items(project):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)

    layout = build_print_layout(project, _request([layer])).layout

    for item_id in (MAP_ID, LEGEND_ID, "riogis_print_scale_bar", "riogis_print_scale_numeric",
                    "riogis_print_north_arrow", "riogis_print_date", "riogis_print_note"):
        assert layout.itemById(item_id) is not None, item_id
    assert layout.itemById("riogis_print_signature").text() == "Signatur: Ola Nordmann"
    assert "feil og mangler" in layout.itemById("riogis_print_note").text()

    # every item stays on the A4 page
    page = layout.pageCollection().pages()[0].rect()
    for item in layout.items():
        if hasattr(item, "id") and item.id().startswith("riogis_print"):
            assert page.contains(item.sceneBoundingRect().adjusted(0.5, 0.5, -0.5, -0.5)), item.id()


def test_registered_layout_is_owned_by_the_project(project):
    """Regression: the designer crashed because Python deleted the layout."""
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)

    layout = build_print_layout(project, _request([layer])).layout
    assert sip.ispyowned(layout)

    register_layout(project, layout)
    name = layout.name()
    assert not sip.ispyowned(layout)
    del layout
    gc.collect()

    kept = project.layoutManager().layoutByName(name)
    assert kept is not None
    assert kept.itemById(MAP_ID) is not None


def test_registering_twice_replaces_the_old_layout(project):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)

    register_layout(project, build_print_layout(project, _request([layer])).layout)
    register_layout(project, build_print_layout(project, _request([layer], scale=5000)).layout)

    assert len(project.layoutManager().printLayouts()) == 1


def test_export_to_pdf(project, tmp_path):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)
    layout = build_print_layout(project, _request([layer])).layout

    pdf_path = tmp_path / "kart.pdf"
    assert export_layout_to_pdf(layout, str(pdf_path)) == QgsLayoutExporter.Success
    assert pdf_path.read_bytes().startswith(b"%PDF-")


# ------------------------------------------------------------------ legend

def _legend_and_frame(layout):
    legend = layout.itemById(LEGEND_ID)
    size = layout.convertToLayoutUnits(legend.sizeWithUnits())
    return legend, size


def test_small_legend_keeps_full_size(project):
    layer = _line_layer("Avløpsledning", rules=3)
    project.addMapLayer(layer)

    result = build_print_layout(project, _request([layer]))
    legend, _ = _legend_and_frame(result.layout)

    assert result.legend_fits
    assert legend.columnCount() == 1
    assert legend.symbolWidth() == pytest.approx(5)


def test_large_legend_shrinks_to_fit_frame(project):
    layers = [_line_layer(f"Lag {i}", rules=4) for i in range(12)]
    project.addMapLayers(layers)

    standard = build_print_layout(project, _request(layers[:1]))
    frame = standard.layout.convertToLayoutUnits(
        standard.layout.itemById(LEGEND_ID).sizeWithUnits()
    )

    result = build_print_layout(project, _request(layers))
    legend, size = _legend_and_frame(result.layout)

    assert result.legend_fits
    assert legend.symbolWidth() < 5 or legend.columnCount() > 1
    assert size.width() == pytest.approx(frame.width())
    assert size.height() == pytest.approx(frame.height())


def test_legend_that_cannot_fit_is_reported_and_kept_in_its_frame(project):
    layers = [_line_layer(f"Lag {i}", rules=10) for i in range(40)]
    project.addMapLayers(layers)

    result = build_print_layout(project, _request(layers))
    _, size = _legend_and_frame(result.layout)

    assert not result.legend_fits
    assert size.height() == pytest.approx(112)


def test_legend_leaves_out_background_and_empty_layers(project):
    thematic = _line_layer("Avløpsledning")
    empty = _line_layer("Vannledning", features=False)
    background = _line_layer("Veg")
    project.addMapLayers([thematic, empty])
    project.addMapLayer(background, False)
    project.layerTreeRoot().addGroup("Bakgrunnskart").addLayer(background)

    result = build_print_layout(project, _request([thematic, empty, background]))

    assert [layer.name() for layer in result.legend_layers] == ["Avløpsledning"]
    # all layers are still drawn in the map
    assert len(result.layout.itemById(MAP_ID).layers()) == 3


# ------------------------------------------------------------------ templates

def test_saved_template_loads_with_new_scale_and_signature(project, tmp_path):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)
    layout = build_print_layout(project, _request([layer], scale=1000)).layout
    template_path = tmp_path / "standard.qpt"
    assert layout.saveAsTemplate(str(template_path), QgsReadWriteContext())

    loaded = build_print_layout(
        project, _request([layer], scale=2000, template_path=str(template_path),
                          operator="Kari Nordmann")
    ).layout

    assert loaded.name() == "standard"
    assert loaded.itemById("riogis_print_signature").text() == "Signatur: Kari Nordmann"
    assert loaded.itemById(MAP_ID).scale() == pytest.approx(2000, rel=1e-3)


def test_invalid_template_gives_clear_error(project, tmp_path):
    bad = tmp_path / "bad.qpt"
    bad.write_text("not xml", encoding="utf-8")
    with pytest.raises(ValueError, match="ugyldig"):
        build_print_layout(project, _request([], template_path=str(bad)))


def test_layout_designer_action_saves_template(project, tmp_path, monkeypatch):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)
    layout = build_print_layout(project, _request([layer])).layout
    window = QWidget()
    menu = QMenu(window)
    designer = SimpleNamespace(window=lambda: window, layout=lambda: layout, layoutMenu=lambda: menu)

    template_path = tmp_path / "lagret-mal.qpt"
    monkeypatch.setattr(
        "riogisoffline.plugin.print_layout.QFileDialog.getSaveFileName",
        lambda *args: (str(template_path), ""),
    )
    monkeypatch.setattr("riogisoffline.plugin.print_layout.utils.printSuccessMessage", lambda m: None)

    add_save_template_action(designer, str(tmp_path)).trigger()

    assert template_path.exists()


# ------------------------------------------------------------------ dialog

def test_dialog_offers_only_the_fixed_scales(tmp_path):
    dialog = PrintOptionsDialog(str(tmp_path), 750)
    offered = [dialog.scale_combo.itemData(i) for i in range(dialog.scale_combo.count())]
    assert offered == [500, 1000, 2000, 5000, 10000]


@pytest.mark.parametrize("canvas_scale, expected", [(300, 500), (750, 1000), (1600, 2000), (40000, 10000)])
def test_dialog_preselects_nearest_scale(tmp_path, canvas_scale, expected):
    assert nearest_print_scale(canvas_scale) == expected
    assert PrintOptionsDialog(str(tmp_path), canvas_scale).selected_scale() == expected


def test_dialog_remembers_last_choice(tmp_path):
    (tmp_path / "egen-mal.qpt").write_text("x", encoding="utf-8")
    dialog = PrintOptionsDialog(str(tmp_path), 750)
    dialog.scale_combo.setCurrentIndex(dialog.scale_combo.findData(5000))
    dialog.template_combo.setCurrentIndex(1)
    dialog.accept()

    again = PrintOptionsDialog(str(tmp_path), 750)
    assert again.selected_scale() == 5000
    assert again.selected_template_path() == str(tmp_path / "egen-mal.qpt")


def test_dialog_error_blocks_printing(tmp_path):
    dialog = PrintOptionsDialog(str(tmp_path), 1000)
    dialog.set_error("Feil i mal")
    assert not dialog.ok_button.isEnabled()
    dialog.set_error(None)
    assert dialog.ok_button.isEnabled()


# ------------------------------------------------------------------ controller

class _Iface:
    def __init__(self, canvas):
        self.canvas = canvas
        self.opened = []

    def mapCanvas(self):
        return self.canvas

    def mainWindow(self):
        return None

    def openLayoutDesigner(self, layout):
        self.opened.append(layout)
        return None


@pytest.fixture
def canvas(project):
    layer = _line_layer("Avløpsledning")
    project.addMapLayer(layer)
    canvas = QgsMapCanvas()
    canvas.resize(800, 600)
    canvas.setDestinationCrs(CRS)
    canvas.setLayers([layer])
    canvas.setExtent(QgsRectangle(CENTER.x() - 200, CENTER.y() - 150, CENTER.x() + 200, CENTER.y() + 150))
    yield canvas
    canvas.deleteLater()


def _controller(canvas, tmp_path, monkeypatch):
    monkeypatch.setattr("riogisoffline.plugin.print_controller.utils.printWarningMessage", lambda *a, **k: None)
    iface = _Iface(canvas)
    controller = PrintController(iface, {"operator": "Ola Nordmann", "output_folder": str(tmp_path)})
    return controller, iface


def test_preview_shows_print_area_and_follows_scale(canvas, tmp_path, monkeypatch):
    controller, _ = _controller(canvas, tmp_path, monkeypatch)
    controller.start()
    try:
        dialog = controller._dialog
        dialog.scale_combo.setCurrentIndex(dialog.scale_combo.findData(1000))
        shown = controller._preview.geometry().boundingBox()
        expected = controller._current_extent()
        assert shown.width() == pytest.approx(expected.width(), rel=1e-6)
        assert shown.height() == pytest.approx(expected.height(), rel=1e-6)

        # a larger scale gives a larger area, and the map zooms out to show all of it
        dialog.scale_combo.setCurrentIndex(dialog.scale_combo.findData(10000))
        bigger = controller._preview.geometry().boundingBox()
        assert bigger.width() == pytest.approx(shown.width() * 10, rel=1e-3)
        assert canvas.extent().contains(bigger)
        assert "m" in dialog.area_label.text()
    finally:
        controller.close()


def test_preview_moves_with_the_map(canvas, tmp_path, monkeypatch):
    controller, _ = _controller(canvas, tmp_path, monkeypatch)
    controller.start()
    try:
        before = controller._preview.geometry().boundingBox().center()
        extent = canvas.extent()
        canvas.setExtent(QgsRectangle(extent.xMinimum() + 50, extent.yMinimum(),
                                      extent.xMaximum() + 50, extent.yMaximum()))
        after = controller._preview.geometry().boundingBox().center()
        assert after.x() == pytest.approx(before.x() + 50, abs=1)
    finally:
        controller.close()


def test_accept_opens_layout_owned_by_project_and_clears_preview(project, canvas, tmp_path, monkeypatch):
    controller, iface = _controller(canvas, tmp_path, monkeypatch)
    controller.start()
    controller._dialog.accept()
    gc.collect()

    assert len(iface.opened) == 1
    assert not sip.ispyowned(iface.opened[0])
    assert project.layoutManager().layoutByName(iface.opened[0].name()) is not None
    assert not controller.is_active
    assert controller._preview is None


def test_cancel_removes_preview(canvas, tmp_path, monkeypatch):
    controller, iface = _controller(canvas, tmp_path, monkeypatch)
    controller.start()
    controller._dialog.reject()

    assert not controller.is_active
    assert iface.opened == []


def test_start_requires_operator(canvas, tmp_path, monkeypatch):
    controller, _ = _controller(canvas, tmp_path, monkeypatch)
    controller.settings["operator"] = ""
    controller.start()
    assert not controller.is_active
