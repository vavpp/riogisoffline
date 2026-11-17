"""
Map side of the WinCan integration: finding the pipe, placing observations
along it, and the memory layers that show them.
"""

from dataclasses import dataclass

from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
GROUP_NAME = "WinCan-inspeksjon"
POINT_LAYER = "Observasjoner (punkt)"
LINE_LAYER = "Observasjoner (lengde)"
TRACK_LAYER = "Inspisert strekning"
CAMERA_LAYER = "Kamera"

MIN_SEGMENT_M = 0.05

DEFAULT_STYLES = {
    # Not "Stikkledninger": their lsid field holds the main pipe's LSID, so many
    # laterals share the LSID of the pipe being inspected.
    "pipe_layers": ["Avløpsledning", "Vannledning", "Bestillinger"],
    "node_layers": ["Kum", "Kum (ikke kommunalt)"],
    "grade_colors": {"1": "#2e7d32", "2": "#f2c200", "3": "#f57c00", "4": "#c62828"},
    "info_color": "#8a8f98",
    "track_color": "#1565c0",
    "shapes": {
        "circle": ["SR", "DF", "KO", "IR"],
        "square": ["PF", "FS", "SP", "DO"],
        "triangle": ["SM", "HI", "RØ", "IS"],
        "diamond": ["TF", "DG", "DH"],
    },
    "label_max_scale": 1000,
}

try:
    _PROP_NAME = QgsSymbolLayer.Property.Name
    _PROP_STROKE_COLOR = QgsSymbolLayer.Property.StrokeColor
    _PROP_OFFSET = QgsSymbolLayer.Property.Offset
except AttributeError:  # older enum naming
    _PROP_NAME = QgsSymbolLayer.PropertyName
    _PROP_STROKE_COLOR = QgsSymbolLayer.PropertyStrokeColor
    _PROP_OFFSET = QgsSymbolLayer.PropertyOffset


def merged_styles(settings):
    styles = dict(DEFAULT_STYLES)
    styles.update((settings or {}).get("wincan", {}))
    return styles


# --------------------------------------------------------------------------
# Pipe lookup and linear referencing
# --------------------------------------------------------------------------

def _single_line(geometry):
    geometry = QgsGeometry(geometry)
    if geometry.isMultipart():
        merged = geometry.mergeLines()
        if not merged.isEmpty() and not merged.isMultipart():
            return merged
        parts = (merged if not merged.isEmpty() else geometry).asGeometryCollection()
        return max(parts, key=lambda part: part.length())
    return geometry


def _equality(field, value):
    if value is not None and str(value).isdigit():
        value = int(value)
    return QgsExpression.createFieldEqualityExpression(field, value)


@dataclass
class PipeGeometry:
    """A pipe from the map, with linear referencing for WinCan distances."""

    lsid: str
    geometry: QgsGeometry
    fcode: str
    digitized_from_to: bool
    crs: object

    @property
    def length(self):
        return self.geometry.length()

    def along(self, distance, reversed_, section_length):
        """Position along the geometry (map units) for a WinCan distance."""
        length = self.length
        reference = section_length if section_length and section_length > 0 else length
        position = min(max(distance * length / reference, 0.0), length)
        inspected_from_to = not reversed_
        return position if inspected_from_to == self.digitized_from_to else length - position

    def point_at(self, distance, reversed_, section_length):
        return self.geometry.interpolate(self.along(distance, reversed_, section_length))

    def segment(self, start, end, reversed_, section_length):
        a = self.along(start, reversed_, section_length)
        b = self.along(end, reversed_, section_length)
        low, high = min(a, b), max(a, b)
        if high - low < MIN_SEGMENT_M:
            return None
        curve = self.geometry.constGet()
        return QgsGeometry(curve.curveSubstring(low, high))


class PipeLocator:
    """Finds pipes (by LSID) and manholes (by PSID) in the RioGIS map layers."""

    def __init__(self, project, styles):
        self.project = project
        self.styles = styles

    def _layers(self, names, field):
        for name in names:
            for layer in self.project.mapLayersByName(name):
                if isinstance(layer, QgsVectorLayer) and layer.fields().indexOf(field) >= 0:
                    yield layer

    def _first_feature(self, names, field, value):
        for layer in self._layers(names, field):
            request = QgsFeatureRequest().setFilterExpression(_equality(field, value)).setLimit(1)
            feature = next(iter(layer.getFeatures(request)), None)
            if feature is not None and feature.hasGeometry():
                return layer, feature
        return None, None

    def node_point(self, psid):
        if not psid:
            return None
        _, feature = self._first_feature(self.styles["node_layers"], "psid", psid)
        return feature.geometry().centroid().asPoint() if feature is not None else None

    def find_pipe(self, lsid, from_psid=None, to_psid=None):
        if not lsid:
            return None
        layer, feature = self._first_feature(self.styles["pipe_layers"], "lsid", lsid)
        if feature is None:
            return None
        geometry = _single_line(feature.geometry())
        fcode = feature["fcode"] if layer.fields().indexOf("fcode") >= 0 else None
        return PipeGeometry(
            lsid=str(lsid),
            geometry=geometry,
            fcode=str(fcode) if fcode else None,
            digitized_from_to=self._digitized_from_to(geometry, from_psid, to_psid),
            crs=layer.crs(),
        )

    def _digitized_from_to(self, geometry, from_psid, to_psid):
        """Is the geometry drawn from the from-manhole to the to-manhole? Assumed yes if unknown."""
        from_point = self.node_point(from_psid)
        to_point = self.node_point(to_psid)
        line = geometry.constGet()
        first = line.startPoint()
        if from_point is not None:
            from_distance = first.distance(from_point.x(), from_point.y())
            if to_point is not None:
                return from_distance <= first.distance(to_point.x(), to_point.y())
            last = line.endPoint()
            return from_distance <= last.distance(from_point.x(), from_point.y())
        if to_point is not None:
            last = line.endPoint()
            return last.distance(to_point.x(), to_point.y()) <= first.distance(to_point.x(), to_point.y())
        return True


# --------------------------------------------------------------------------
# Memory layers
# --------------------------------------------------------------------------

def _field_types():
    """QgsField types: QMetaType from QGIS 3.38 (required with Qt 6), QVariant before."""
    if Qgis.QGIS_VERSION_INT >= 33800:
        from qgis.PyQt.QtCore import QMetaType
        return {"string": QMetaType.Type.QString, "double": QMetaType.Type.Double,
                "int": QMetaType.Type.Int}
    from qgis.PyQt.QtCore import QVariant
    return {"string": QVariant.String, "double": QVariant.Double, "int": QVariant.Int}


def _fields(spec):
    types = _field_types()
    fields = QgsFields()
    for name, kind in spec:
        fields.append(QgsField(name, types[kind]))
    return fields


OBSERVATION_FIELDS = [
    ("pk", "string"), ("lsid", "string"), ("inspection", "string"),
    ("code", "string"), ("description", "string"),
    ("distance", "double"), ("end_distance", "double"),
    ("clock", "int"), ("grade_wincan", "int"), ("grade", "int"),
    ("percent", "double"), ("info", "int"), ("open", "int"),
    ("timestamp", "string"), ("media", "string"), ("active", "int"), ("lane", "int"),
]

# overlapping length observations are drawn side by side: lane 0 on the pipe,
# then alternating left/right of it
LANE_WIDTH_MM = 2.6
LANE_OFFSET_EXPRESSION = (
    "CASE WHEN coalesce(\"lane\", 0) = 0 THEN 0 "
    "WHEN \"lane\" % 2 = 1 THEN ((\"lane\" + 1) / 2) * {w} "
    "ELSE -(\"lane\" / 2) * {w} END"
).format(w=LANE_WIDTH_MM)


def assign_lanes(intervals):
    """
    Lane per (start, end) interval so overlapping intervals get different lanes
    (greedy interval colouring, in input order sorted by start).
    """
    order = sorted(range(len(intervals)), key=lambda i: (intervals[i][0], -intervals[i][1]))
    lane_ends = []
    lanes = [0] * len(intervals)
    for index in order:
        start, end = intervals[index]
        for lane, lane_end in enumerate(lane_ends):
            if lane_end <= start:
                lanes[index] = lane
                lane_ends[lane] = end
                break
        else:
            lanes[index] = len(lane_ends)
            lane_ends.append(end)
    return lanes
TRACK_FIELDS = [
    ("lsid", "string"), ("inspection", "string"), ("distance", "double"),
    ("finished", "int"), ("active", "int"),
]
CAMERA_FIELDS = [("lsid", "string"), ("distance", "double")]

LAYER_SPECS = {
    # name: (geometry type, fields); listed bottom to top in the layer tree
    TRACK_LAYER: ("LineString", TRACK_FIELDS),
    LINE_LAYER: ("LineString", OBSERVATION_FIELDS),
    POINT_LAYER: ("Point", OBSERVATION_FIELDS),
    CAMERA_LAYER: ("Point", CAMERA_FIELDS),
}


def _shape_expression(shapes):
    cases = " ".join(
        "WHEN left(\"code\", 2) IN ({}) THEN '{}'".format(
            ", ".join(QgsExpression.quotedString(code) for code in codes), shape
        )
        for shape, codes in shapes.items()
    )
    return "CASE {} ELSE 'circle' END".format(cases)


def _grade_color_expression(styles):
    cases = " ".join(
        "WHEN \"grade\" = {} THEN '{}'".format(int(grade), color)
        for grade, color in sorted(styles["grade_colors"].items())
    )
    return "CASE WHEN \"info\" = 1 THEN '{}' {} ELSE '{}' END".format(
        styles["info_color"], cases, styles["info_color"]
    )


def _text_format(size=8, color=QColor(30, 30, 30)):
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial"))
    text_format.setSize(size)
    text_format.setColor(color)
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(0.8)
    buffer.setColor(QColor("white"))
    text_format.setBuffer(buffer)
    return text_format


def _labeling(expression, max_scale, placement):
    settings = QgsPalLayerSettings()
    settings.isExpression = True
    settings.fieldName = expression
    settings.setFormat(_text_format())
    settings.placement = placement
    settings.scaleVisibility = True
    settings.minimumScale = max_scale  # visible when zoomed in closer than 1:max_scale
    settings.priority = 9
    settings.enabled = True
    return QgsVectorLayerSimpleLabeling(settings)


def _label_expression(show_info):
    grade = "if(\"grade\" IS NULL, '', ' (' || \"grade\" || ')')"
    if show_info:
        return "\"code\" || {}".format(grade)
    return "if(\"info\" = 1, NULL, \"code\" || {})".format(grade)


def _rule_renderer(rules):
    """
    Rule-based renderer from (symbol, label, filter, active) tuples.

    Every symbol is a fresh Python object, configured before it is handed to
    its rule. Fetching symbols back with rule.symbol() is avoided on purpose:
    sip can hand back a stale wrapper of an already deleted symbol at the same
    memory address (seen as "'QgsLineSymbol' has no attribute 'setSize'").
    """
    root = QgsRuleBasedRenderer.Rule(None)
    for symbol, label, expression, active in rules:
        rule = QgsRuleBasedRenderer.Rule(symbol, 0, 0, expression, label)
        rule.setActive(active)
        root.appendChild(rule)
    return QgsRuleBasedRenderer(root)


def _observation_marker(styles, color, size):
    symbol = QgsMarkerSymbol.createSimple({
        "name": "circle", "size": str(size), "color": color,
        "outline_color": "40,40,40", "outline_width": "0.3",
    })
    symbol.symbolLayer(0).setDataDefinedProperty(
        _PROP_NAME, QgsProperty.fromExpression(_shape_expression(styles["shapes"]))
    )
    return symbol


def _observation_line(color, width, dashed=False, color_expression=None):
    symbol = QgsLineSymbol.createSimple({
        "line_width": str(width), "capstyle": "flat", "line_color": color,
        "line_style": "dash" if dashed else "solid",
    })
    symbol.setOpacity(0.75)
    symbol_layer = symbol.symbolLayer(0)
    symbol_layer.setDataDefinedProperty(_PROP_OFFSET, QgsProperty.fromExpression(LANE_OFFSET_EXPRESSION))
    if color_expression:
        symbol_layer.setDataDefinedProperty(_PROP_STROKE_COLOR, QgsProperty.fromExpression(color_expression))
    return symbol


def _track_line(color, width, opacity):
    symbol = QgsLineSymbol.createSimple({"line_width": str(width), "capstyle": "round", "line_color": color})
    symbol.setOpacity(opacity)
    return symbol


def style_point_layer(layer, styles, show_info):
    rules = [
        (_observation_marker(styles, color, 3.4), "Tilstandsgrad {}".format(grade),
         "\"info\" = 0 AND \"grade\" = {}".format(int(grade)), True)
        for grade, color in sorted(styles["grade_colors"].items())
    ]
    rules.append((_observation_marker(styles, styles["info_color"], 2.2), "Info-kode",
                  "\"info\" = 1", show_info))
    layer.setRenderer(_rule_renderer(rules))
    layer.setLabeling(_labeling(_label_expression(show_info), styles["label_max_scale"],
                                Qgis.LabelPlacement.AroundPoint))
    layer.setLabelsEnabled(True)


def style_line_layer(layer, styles, show_info):
    rules = [
        (_observation_line(color, 2.4), "Tilstandsgrad {}".format(grade),
         "\"info\" = 0 AND \"open\" = 0 AND \"grade\" = {}".format(int(grade)), True)
        for grade, color in sorted(styles["grade_colors"].items())
    ]
    rules.append((
        _observation_line(styles["info_color"], 2.4, dashed=True,
                          color_expression=_grade_color_expression(styles)),
        "Pågår (ikke avsluttet)", "\"info\" = 0 AND \"open\" = 1", True,
    ))
    rules.append((_observation_line(styles["info_color"], 1.2), "Info-kode", "\"info\" = 1", show_info))
    layer.setRenderer(_rule_renderer(rules))
    layer.setLabeling(_labeling(_label_expression(show_info), styles["label_max_scale"],
                                Qgis.LabelPlacement.Line))
    layer.setLabelsEnabled(True)


def style_track_layer(layer, styles):
    color = styles["track_color"]
    layer.setRenderer(_rule_renderer([
        (_track_line(color, 4.0, 0.35), "Aktiv inspeksjon", "\"active\" = 1", True),
        (_track_line(color, 2.5, 0.2), "Inspisert i dag", "\"active\" = 0", True),
    ]))


def style_camera_layer(layer, styles):
    symbol = QgsMarkerSymbol.createSimple({
        "name": "circle", "size": "5", "color": styles["track_color"],
        "outline_color": "255,255,255", "outline_width": "0.8",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.setLabeling(_labeling(
        "'Kamera ' || format_number(\"distance\", 1) || ' m'", 100000,
        Qgis.LabelPlacement.AroundPoint,
    ))
    layer.setLabelsEnabled(True)


class ObservationLayers:
    """
    The memory layers in the "WinCan-inspeksjon" group. Layers are found by
    id on every update and recreated if the map was reloaded (project cleared).
    """

    def __init__(self, project, styles, show_info=False):
        self.project = project
        self.styles = styles
        self.show_info = show_info
        self._ids = {}
        self._signatures = {}

    def layer(self, name):
        layer_id = self._ids.get(name)
        return self.project.mapLayer(layer_id) if layer_id else None

    def ensure(self, crs):
        """Create missing layers (first use, or after the project was cleared)."""
        root = self.project.layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        for name, (geometry_type, fields) in LAYER_SPECS.items():
            if self.layer(name) is not None:
                continue
            layer = QgsVectorLayer(
                "{}?crs={}".format(geometry_type, crs.authid() if crs and crs.isValid() else "EPSG:25832"),
                name, "memory",
            )
            layer.dataProvider().addAttributes(_fields(fields).toList())
            layer.updateFields()
            self._style(name, layer)
            self.project.addMapLayer(layer, False)
            if group is None:
                group = root.insertGroup(0, GROUP_NAME)
            group.insertLayer(0, layer)
            self._ids[name] = layer.id()
            self._signatures.pop(name, None)

    def _style(self, name, layer):
        if name == POINT_LAYER:
            style_point_layer(layer, self.styles, self.show_info)
        elif name == LINE_LAYER:
            style_line_layer(layer, self.styles, self.show_info)
        elif name == TRACK_LAYER:
            style_track_layer(layer, self.styles)
        elif name == CAMERA_LAYER:
            style_camera_layer(layer, self.styles)

    def set_show_info(self, show):
        self.show_info = bool(show)
        for name in (POINT_LAYER, LINE_LAYER):
            layer = self.layer(name)
            if layer is not None:
                self._style(name, layer)
                layer.triggerRepaint()

    def replace(self, name, rows, signature):
        """
        Replace all features of a layer with rows [(geometry, {field: value})].
        Nothing happens when the signature is unchanged (no needless repaint).
        """
        layer = self.layer(name)
        if layer is None or self._signatures.get(name) == signature:
            return False
        provider = layer.dataProvider()
        provider.truncate()
        features = []
        for geometry, attributes in rows:
            feature = QgsFeature(layer.fields())
            feature.setGeometry(geometry)
            for key, value in attributes.items():
                feature[key] = value
            features.append(feature)
        provider.addFeatures(features)
        layer.updateExtents()
        layer.triggerRepaint()
        self._signatures[name] = signature
        return True

    def clear(self):
        for name in LAYER_SPECS:
            self.replace(name, [], ("empty",))

    def remove(self):
        """Remove the layers and the group (plugin unload)."""
        ids = [i for i in self._ids.values() if self.project.mapLayer(i) is not None]
        if ids:
            self.project.removeMapLayers(ids)
        group = self.project.layerTreeRoot().findGroup(GROUP_NAME)
        if group is not None:
            group.parent().removeChildNode(group)
        self._ids = {}
        self._signatures = {}
