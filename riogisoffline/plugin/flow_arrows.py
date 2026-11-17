"""
Animated flow arrows on wastewater pipes.

The arrows are marker-line symbol layers (see refresh_map.MapRefresher._add_rules).
They are animated with QGIS's own symbol animation (QGIS >= 3.26): the
marker offset along the line is driven by the @symbol_frame variable, and
QGIS repaints the layer at the frame rate.

QGIS uses *deferred* repaints for animated layers, so a new frame waits until
the previous one has been drawn. The previous implementation forced an
immediate repaint from a Python timer every 200 ms, which cancels an
unfinished render; on large layers no frame ever finished and nothing moved.
"""

from qgis.core import (
    QgsMarkerLineSymbolLayer,
    QgsProject,
    QgsProperty,
    QgsRuleBasedRenderer,
    QgsSymbolAnimationSettings,
    QgsSymbolLayer,
)

FLOW_ARROW_INTERVAL_MM = 25.0
FLOW_ARROW_INITIAL_OFFSET_MM = 5.0
FLOW_ARROW_STEP_MM = 1.0
FLOW_ARROW_FRAME_RATE = 10  # frames per second -> 10 mm/s on screen
# Animate only when zoomed in closer than this. Higher values show the
# animation on larger areas; more pipes per frame means fewer frames per
# second on slow machines (QGIS waits for each frame, so it never stalls).
FLOW_ARROW_MAX_SCALE = 5000.0

# offset along the line for frame n, wrapping at the arrow interval
FLOW_ARROW_OFFSET_EXPRESSION = (
    f"({FLOW_ARROW_INITIAL_OFFSET_MM} + @symbol_frame * {FLOW_ARROW_STEP_MM}) "
    f"% {FLOW_ARROW_INTERVAL_MM}"
)

try:
    _OFFSET_ALONG_LINE = QgsSymbolLayer.Property.OffsetAlongLine
except AttributeError:  # older enum naming
    _OFFSET_ALONG_LINE = QgsSymbolLayer.PropertyOffsetAlongLine


def _iter_rules(rule):
    yield rule
    for child in rule.children():
        yield from _iter_rules(child)


def _arrow_symbols(renderer):
    """Rule symbols that contain a marker line (the arrows)."""
    for rule in _iter_rules(renderer.rootRule()):
        symbol = rule.symbol()
        if symbol is None:
            continue
        markers = [
            symbol.symbolLayer(i)
            for i in range(symbol.symbolLayerCount())
            if isinstance(symbol.symbolLayer(i), QgsMarkerLineSymbolLayer)
        ]
        if markers:
            yield symbol, markers


def has_flow_arrows(layer):
    renderer = layer.renderer() if hasattr(layer, "renderer") else None
    return isinstance(renderer, QgsRuleBasedRenderer) and any(True for _ in _arrow_symbols(renderer))


def is_animated(layer):
    renderer = layer.renderer()
    return isinstance(renderer, QgsRuleBasedRenderer) and any(
        symbol.animationSettings().isAnimated() for symbol, _ in _arrow_symbols(renderer)
    )


def set_layer_animated(layer, animated):
    """
    Turn the arrow animation on or off for one layer.

    The renderer is cloned and set again, because QGIS only starts or stops
    its frame timer for a layer in setRenderer().
    """
    renderer = layer.renderer().clone()
    for symbol, markers in _arrow_symbols(renderer):
        settings = QgsSymbolAnimationSettings()
        settings.setIsAnimated(animated)
        settings.setFrameRate(FLOW_ARROW_FRAME_RATE)
        symbol.setAnimationSettings(settings)
        for marker in markers:
            properties = marker.dataDefinedProperties()
            if animated:
                properties.setProperty(
                    _OFFSET_ALONG_LINE, QgsProperty.fromExpression(FLOW_ARROW_OFFSET_EXPRESSION)
                )
            else:
                properties.setProperty(_OFFSET_ALONG_LINE, QgsProperty())
                marker.setOffsetAlongLine(FLOW_ARROW_INITIAL_OFFSET_MM)
            marker.setDataDefinedProperties(properties)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


class FlowArrowAnimator:
    """
    Keeps the arrow animation in line with the user's choice and the map scale.

    Layers are picked up whenever they are added to the project, so it also
    works for a project opened from file, not only after "Last kart".
    """

    def __init__(self, canvas, enabled=False, project=None):
        self._canvas = canvas
        self._project = project or QgsProject.instance()
        self._enabled = bool(enabled)
        self._layer_ids = []
        self._connected = False
        self._connect()
        self.refresh_layers()

    # ---------------------------------------------------------------- public

    @property
    def enabled(self):
        return self._enabled

    @property
    def layer_ids(self):
        return list(self._layer_ids)

    def refresh_layers(self, *_args):
        """Find the layers with flow arrows and apply the current state."""
        self._layer_ids = [
            layer.id() for layer in self._project.mapLayers().values() if has_flow_arrows(layer)
        ]
        self._apply()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self._apply()

    def should_animate(self):
        return self._enabled and self._canvas.scale() < FLOW_ARROW_MAX_SCALE

    def stop(self):
        """Stop animating and disconnect (plugin unload)."""
        self._enabled = False
        self._apply()
        self._disconnect()
        self._layer_ids = []

    # --------------------------------------------------------------- private

    def _connect(self):
        self._canvas.scaleChanged.connect(self._apply)
        self._project.layersAdded.connect(self.refresh_layers)
        self._connected = True

    def _disconnect(self):
        if not self._connected:
            return
        for signal, slot in (
            (self._canvas.scaleChanged, self._apply),
            (self._project.layersAdded, self.refresh_layers),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connected = False

    def _apply(self, *_args):
        animate = self.should_animate()
        for layer_id in self._layer_ids:
            layer = self._project.mapLayer(layer_id)
            if layer is None:
                continue
            # only touch layers whose state actually changes
            if is_animated(layer) != animate:
                set_layer_animated(layer, animate)
