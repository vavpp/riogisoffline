"""
Building of RioGIS print layouts.

This module has no GUI code. It builds a QgsPrintLayout from the RioGIS
standard design or from a saved template (.qpt), places the map at an exact
centre and scale, and shrinks the legend until it fits its frame.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeatureRequest,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLayoutUtils,
    QgsLegendRenderer,
    QgsLegendStyle,
    QgsPointXY,
    QgsPrintLayout,
    QgsReadWriteContext,
    QgsRectangle,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayer,
)

import riogisoffline.plugin.utils as utils


# Fixed scales offered to the user
PRINT_SCALES = (500, 1000, 2000, 5000, 10000)

DEFAULT_LAYOUT_NAME = "RioGIS - Kartutskrift"

# Layers in this layer tree group are background and are left out of the legend
BACKGROUND_GROUP_NAME = "Bakgrunnskart"

# Item ids. Saved templates rely on these, so do not rename them.
MAP_ID = "riogis_print_map"
LEGEND_ID = "riogis_print_legend"
SCALE_BAR_ID = "riogis_print_scale_bar"
SCALE_NUMERIC_ID = "riogis_print_scale_numeric"
NORTH_ARROW_ID = "riogis_print_north_arrow"
SIGNATURE_ID = "riogis_print_signature"

# Legend fitting: font size factors and column counts that are tried, in order
LEGEND_SIZE_FACTORS = (1.0, 0.9, 0.8, 0.7, 0.6)
LEGEND_MAX_COLUMNS = 3

# Wanted length of one scale bar segment on paper (mm), and "nice" ground lengths (m)
_SCALE_BAR_SEGMENT_MM = 20
_NICE_SEGMENT_LENGTHS_M = (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000)

_MM = Qgis.LayoutUnit.Millimeters
_TEXT_COLOR = QColor(33, 37, 41)
_MUTED_COLOR = QColor(95, 99, 104)
_FRAME_COLOR = QColor(60, 64, 67)


@dataclass(frozen=True)
class PrintRequest:
    """Everything needed to build one printout."""

    center: QgsPointXY
    scale: int
    operator: str
    layers: list
    crs: QgsCoordinateReferenceSystem
    template_path: Optional[str] = None


@dataclass
class PrintLayoutResult:
    layout: QgsPrintLayout
    legend_fits: bool = True
    legend_layers: List = field(default_factory=list)


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def print_extent(center, scale, frame_size_mm, crs) -> QgsRectangle:
    """
    Area on the ground covered by a map frame at a given scale.

    Args:
        center (QgsPointXY): centre of the area, in map units of crs
        scale (float): scale denominator, e.g. 1000 for 1:1000
        frame_size_mm (tuple): (width, height) of the map frame on paper, in mm
        crs (QgsCoordinateReferenceSystem): CRS of the map

    Returns:
        QgsRectangle: printed area in map units
    """
    meters_to_map_units = QgsUnitTypes.fromUnitToUnitFactor(
        Qgis.DistanceUnit.Meters, crs.mapUnits()
    )
    width = frame_size_mm[0] / 1000.0 * scale * meters_to_map_units
    height = frame_size_mm[1] / 1000.0 * scale * meters_to_map_units
    return QgsRectangle(
        center.x() - width / 2,
        center.y() - height / 2,
        center.x() + width / 2,
        center.y() + height / 2,
    )


def scale_bar_segment_length(scale) -> int:
    """Ground length (m) of one scale bar segment, about 20 mm on paper."""
    wanted = _SCALE_BAR_SEGMENT_MM / 1000.0 * scale
    return min(_NICE_SEGMENT_LENGTHS_M, key=lambda length: abs(length - wanted))


def map_frame_size_mm(layout) -> Tuple[float, float]:
    map_item = find_main_map(layout)
    if map_item is None:
        raise ValueError("Layoutmalen mangler et kartobjekt.")
    size = layout.convertToLayoutUnits(map_item.sizeWithUnits())
    return size.width(), size.height()


def find_main_map(layout):
    item = layout.itemById(MAP_ID)
    if isinstance(item, QgsLayoutItemMap):
        return item
    return next(
        (candidate for candidate in layout.items() if isinstance(candidate, QgsLayoutItemMap)),
        None,
    )


# --------------------------------------------------------------------------
# Standard layout
# --------------------------------------------------------------------------

def _text_format(size, bold=False, color=_TEXT_COLOR):
    font = QFont()
    font.setBold(bold)
    text_format = QgsTextFormat()
    text_format.setFont(font)
    text_format.setSize(size)
    text_format.setSizeUnit(Qgis.RenderUnit.Points)
    text_format.setColor(color)
    return text_format


def _place(layout, item, item_id, x, y, width=None, height=None):
    item.setId(item_id)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, _MM))
    if width is not None and height is not None:
        item.attemptResize(QgsLayoutSize(width, height, _MM))
    return item


def _add_label(layout, item_id, text, x, y, width, height, size, bold=False,
               color=_TEXT_COLOR, align=Qt.AlignmentFlag.AlignLeft):
    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    label.setTextFormat(_text_format(size, bold, color))
    label.setHAlign(align)
    label.setVAlign(Qt.AlignmentFlag.AlignVCenter)
    label.setMargin(0)
    return _place(layout, label, item_id, x, y, width, height)


def create_standard_layout(project) -> QgsPrintLayout:
    """
    RioGIS standard layout, A4 landscape.

    A large map on the left and an information panel on the right with title,
    date, signature, scale, legend, north arrow, scale bar and disclaimer.
    """
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(DEFAULT_LAYOUT_NAME)
    layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(297, 210, _MM))

    margin = 10
    panel_x = 217
    panel_w = 287 - panel_x

    map_item = QgsLayoutItemMap(layout)
    map_item.setFrameEnabled(True)
    map_item.setFrameStrokeColor(_FRAME_COLOR)
    map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, _MM))
    _place(layout, map_item, MAP_ID, margin, margin, panel_x - margin - 6, 210 - 2 * margin)

    # header
    _add_label(layout, "riogis_print_title", "RioGIS", panel_x, 10, panel_w, 8, 16, bold=True)
    _add_label(layout, "riogis_print_subtitle", "Kartutskrift – Vann- og avløpsetaten",
               panel_x, 18, panel_w, 5, 8, color=_MUTED_COLOR)

    # facts
    _add_label(layout, "riogis_print_date", "Dato: [% format_date(now(), 'dd.MM.yyyy') %]",
               panel_x, 27, panel_w, 5, 8)
    _add_label(layout, SIGNATURE_ID, "Signatur:", panel_x, 32, panel_w, 5, 8)
    _add_label(layout, "riogis_print_scale_title", "Målestokk:", panel_x, 37, 15, 5, 8)

    numeric_scale = QgsLayoutItemScaleBar(layout)
    numeric_scale.setStyle("Numeric")
    numeric_scale.setTextFormat(_text_format(8))
    numeric_scale.setLinkedMap(map_item)
    numeric_scale.setFrameEnabled(False)
    numeric_scale.setBackgroundEnabled(False)
    _place(layout, numeric_scale, SCALE_NUMERIC_ID, panel_x + 14, 37)
    numeric_scale.applyDefaultSize()

    # legend frame; the legend is filled and fitted into it when the layout is prepared
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Tegnforklaring")
    legend.setFrameEnabled(False)
    legend.setBackgroundEnabled(False)
    legend.setSymbolWidth(5)
    legend.setSymbolHeight(3)
    legend.setBoxSpace(0)
    legend.setColumnSpace(3)
    legend.setResizeToContents(False)
    _set_legend_style(legend, QgsLegendStyle.Title, 9, bold=True)
    _set_legend_style(legend, QgsLegendStyle.Group, 7.5, bold=True)
    _set_legend_style(legend, QgsLegendStyle.Subgroup, 7.5, bold=True)
    _set_legend_style(legend, QgsLegendStyle.SymbolLabel, 7)
    legend.setLinkedMap(map_item)
    _place(layout, legend, LEGEND_ID, panel_x, 46, panel_w, 112)

    # north arrow and scale bar
    _add_label(layout, "riogis_print_north_label", "N", panel_x, 160, 9, 4, 8,
               bold=True, align=Qt.AlignmentFlag.AlignHCenter)
    north_arrow = QgsLayoutItemPicture(layout)
    north_arrow.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
    north_arrow.setLinkedMap(map_item)
    _place(layout, north_arrow, NORTH_ARROW_ID, panel_x, 164, 9, 12)

    scale_bar = QgsLayoutItemScaleBar(layout)
    scale_bar.setStyle("Single Box")
    scale_bar.setUnits(Qgis.DistanceUnit.Meters)
    scale_bar.setUnitLabel("m")
    scale_bar.setNumberOfSegments(2)
    scale_bar.setNumberOfSegmentsLeft(0)
    scale_bar.setUnitsPerSegment(20)
    scale_bar.setHeight(1.5)
    scale_bar.setTextFormat(_text_format(7))
    scale_bar.setLinkedMap(map_item)
    _place(layout, scale_bar, SCALE_BAR_ID, panel_x + 13, 166)
    scale_bar.applyDefaultSize()

    # disclaimer
    note = _add_label(
        layout,
        "riogis_print_note",
        "Kartgrunnlaget kan inneholde feil og mangler. Kartutsnittet er kun "
        "veiledende. Kontroller alltid mot gjeldende kilder. "
        "Levert av Oslo kommune, Vann- og avløpsetaten.",
        panel_x, 180, panel_w, 20, 6.5, color=_MUTED_COLOR,
    )
    note.setVAlign(Qt.AlignmentFlag.AlignBottom)

    return layout


def _set_legend_style(legend, component, size, bold=False):
    style = legend.rstyle(component)
    text_format = style.textFormat()
    font = text_format.font()
    font.setBold(bold)
    text_format.setFont(font)
    text_format.setSize(size)
    text_format.setSizeUnit(Qgis.RenderUnit.Points)
    style.setTextFormat(text_format)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

def load_layout(project, template_path=None) -> QgsPrintLayout:
    """
    Standard layout, or a layout loaded from a .qpt template. Not prepared yet.

    Raises:
        ValueError: if the template cannot be read or has no map
    """
    if not template_path:
        return create_standard_layout(project)

    try:
        with open(template_path, "rb") as template_file:
            template_content = template_file.read()
    except OSError as error:
        raise ValueError("Kunne ikke lese layoutmalen: {}".format(error))

    document = QDomDocument()
    parsed = document.setContent(template_content)
    if not (parsed[0] if isinstance(parsed, tuple) else parsed):
        raise ValueError("Layoutmalen er ugyldig.")

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    _, loaded = layout.loadFromTemplate(document, QgsReadWriteContext(), True)
    if not loaded:
        raise ValueError("QGIS kunne ikke laste den valgte layoutmalen.")
    if find_main_map(layout) is None:
        raise ValueError("Layoutmalen mangler et kartobjekt.")

    layout.setName(os.path.splitext(os.path.basename(template_path))[0])
    return layout


def add_save_template_action(designer, template_folder):
    action = QAction("Lagre som RioGIS-mal...", designer.window())

    def save_template(_checked=False):
        os.makedirs(template_folder, exist_ok=True)
        suggested_path = os.path.join(
            template_folder, "{}.qpt".format(designer.layout().name())
        )
        path, _ = QFileDialog.getSaveFileName(
            designer.window(),
            "Lagre layout som mal",
            suggested_path,
            "QGIS layoutmal (*.qpt)",
        )
        if not path:
            return
        if not path.lower().endswith(".qpt"):
            path += ".qpt"
        if not designer.layout().saveAsTemplate(path, QgsReadWriteContext()):
            utils.printWarningMessage("Kunne ikke lagre layoutmalen.")
            return
        utils.printSuccessMessage("Layoutmal lagret: {}".format(path))

    action.triggered.connect(save_template)
    menu = designer.layoutMenu()
    menu.addSeparator()
    menu.addAction(action)
    return action


# --------------------------------------------------------------------------
# Preparing a layout for a print request
# --------------------------------------------------------------------------

def legend_layers(project, layers, extent, scale):
    """
    Layers that belong in the legend: thematic (not background), visible at the
    print scale and with at least one feature inside the printed area.
    """
    root = project.layerTreeRoot()
    result = []
    for layer in layers:
        node = root.findLayer(layer.id())
        group = node.parent() if node is not None else None
        if group is not None and group.name() == BACKGROUND_GROUP_NAME:
            continue
        if layer.hasScaleBasedVisibility() and not layer.isInScaleRange(scale):
            continue
        if isinstance(layer, QgsVectorLayer):
            request = QgsFeatureRequest().setFilterRect(extent).setLimit(1).setNoAttributes()
            if next(iter(layer.getFeatures(request)), None) is None:
                continue
        result.append(layer)
    return result


def _set_legend_manual(legend):
    """Stop the legend from following the project layer tree (API differs by QGIS version)."""
    if hasattr(legend, "setSyncMode") and hasattr(Qgis, "LegendSyncMode"):
        legend.setSyncMode(Qgis.LegendSyncMode.Manual)
    else:
        legend.setAutoUpdateModel(False)


_LEGEND_TEXT_COMPONENTS = (
    QgsLegendStyle.Title,
    QgsLegendStyle.Group,
    QgsLegendStyle.Subgroup,
    QgsLegendStyle.SymbolLabel,
)
# spacing between legend rows; it does not follow the font size by itself
_LEGEND_SPACING_COMPONENTS = _LEGEND_TEXT_COMPONENTS + (QgsLegendStyle.Symbol,)
_LEGEND_SPACING_SIDES = (QgsLegendStyle.Top, QgsLegendStyle.Bottom)


def _legend_base_style(legend):
    return {
        "fonts": {c: legend.rstyle(c).textFormat().size() for c in _LEGEND_TEXT_COMPONENTS},
        "margins": {
            (c, side): legend.rstyle(c).margin(side)
            for c in _LEGEND_SPACING_COMPONENTS
            for side in _LEGEND_SPACING_SIDES
        },
        "symbol": (legend.symbolWidth(), legend.symbolHeight()),
    }


def _apply_legend_size(legend, base, factor, columns):
    for component, size in base["fonts"].items():
        style = legend.rstyle(component)
        text_format = style.textFormat()
        text_format.setSize(size * factor)
        style.setTextFormat(text_format)
    for (component, side), margin in base["margins"].items():
        legend.rstyle(component).setMargin(side, margin * factor)
    legend.setSymbolWidth(base["symbol"][0] * factor)
    legend.setSymbolHeight(base["symbol"][1] * factor)
    legend.setColumnCount(columns)


def fit_legend(legend, width, height) -> bool:
    """
    Shrink the legend (font and symbol sizes, then more columns) until its
    content fits inside width x height mm. The legend item keeps exactly that
    frame, so it never grows past the space the layout has for it.

    Returns:
        bool: True if the content fits, False if it was shrunk as much as allowed
    """
    position = legend.positionWithUnits()
    base = _legend_base_style(legend)

    legend.setSplitLayer(True)
    legend.setEqualColumnWidth(False)
    legend.setResizeToContents(False)

    def fits_frame(size):
        return size.width() <= width + 0.01 and size.height() <= height + 0.01

    fits = False
    for factor in LEGEND_SIZE_FACTORS:
        for columns in range(1, LEGEND_MAX_COLUMNS + 1):
            _apply_legend_size(legend, base, factor, columns)
            if fits_frame(measure_legend(legend)):
                fits = True
                break
        if fits:
            break

    if not fits:
        # smallest allowed text, in the column count that uses the width best
        smallest = LEGEND_SIZE_FACTORS[-1]
        best_columns = 1
        for columns in range(1, LEGEND_MAX_COLUMNS + 1):
            _apply_legend_size(legend, base, smallest, columns)
            if measure_legend(legend).width() <= width + 0.01:
                best_columns = columns
        _apply_legend_size(legend, base, smallest, best_columns)

    legend.attemptMove(position)
    legend.attemptResize(QgsLayoutSize(width, height, _MM))
    legend.updateLegend()
    return fits


def measure_legend(legend):
    """
    Size (mm) the legend content needs with its current settings.

    QgsLayoutItemLegend.adjustBoxSize() does nothing until the item has been
    painted once, so it cannot be used while a layout is being built. The
    legend renderer measures the content directly.
    """
    context = QgsLayoutUtils.createRenderContextForLayout(legend.layout(), None)
    renderer = QgsLegendRenderer(legend.model(), legend.legendSettings())
    return renderer.minimumSize(context)


def _prepare_layout(layout, request: PrintRequest) -> PrintLayoutResult:
    map_item = find_main_map(layout)
    if map_item is None:
        raise ValueError("Layoutmalen mangler et kartobjekt.")

    project = layout.project()
    frame_size = map_frame_size_mm(layout)
    extent = print_extent(request.center, request.scale, frame_size, request.crs)

    map_item.setCrs(request.crs)
    map_item.setLayers(request.layers)
    map_item.setKeepLayerSet(True)
    map_item.setMapRotation(0)
    map_item.setExtent(extent)
    map_item.setScale(float(request.scale))

    result = PrintLayoutResult(layout=layout)

    for item in layout.items():
        if isinstance(item, QgsLayoutItemLegend):
            item.setLinkedMap(map_item)
            item.setLegendFilterByMapEnabled(False)
            _set_legend_manual(item)
            root = item.model().rootGroup()
            root.removeAllChildren()
            result.legend_layers = legend_layers(project, request.layers, extent, request.scale)
            for layer in result.legend_layers:
                root.addLayer(layer)
            frame = layout.convertToLayoutUnits(item.sizeWithUnits())
            result.legend_fits = fit_legend(item, frame.width(), frame.height()) and result.legend_fits
            # hide legend entries (e.g. rules) without features in the printed area
            item.setLegendFilterByMapEnabled(True)
        elif isinstance(item, QgsLayoutItemScaleBar):
            item.setLinkedMap(map_item)
            if item.id() == SCALE_BAR_ID:
                item.setUnitsPerSegment(scale_bar_segment_length(request.scale))
                item.applyDefaultSize()
        elif isinstance(item, QgsLayoutItemPicture) and item.id() == NORTH_ARROW_ID:
            item.setLinkedMap(map_item)

    signature = layout.itemById(SIGNATURE_ID)
    if isinstance(signature, QgsLayoutItemLabel):
        signature.setText("Signatur: {}".format(request.operator))

    layout.refresh()
    return result


def build_print_layout(project, request: PrintRequest) -> PrintLayoutResult:
    """
    Build a layout for the request. The layout is still owned by Python; call
    register_layout() before opening it in the layout designer.

    Raises:
        ValueError: if the template is unusable
    """
    layout = load_layout(project, request.template_path)
    return _prepare_layout(layout, request)


def register_layout(project, layout):
    """
    Hand the layout over to the project's layout manager, replacing an older
    layout with the same name.

    The layout designer only keeps a pointer to the layout. If Python still
    owns it, the layout is deleted when the calling function returns and QGIS
    crashes. Once the layout manager owns it, it lives as long as the project.
    """
    manager = project.layoutManager()
    existing = manager.layoutByName(layout.name())
    if existing is not None:
        manager.removeLayout(existing)
    if not manager.addLayout(layout):
        raise ValueError("Kunne ikke legge utskriften til i prosjektet.")
    return layout


def export_layout_to_pdf(layout, path):
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = 300
    return QgsLayoutExporter(layout).exportToPdf(path, settings)
