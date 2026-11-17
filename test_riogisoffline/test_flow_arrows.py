"""Tests for the animated flow arrows on wastewater pipes."""

import os
import sys

import pytest
from pyvirtualdisplay import Display

from qgis.testing.mocked import get_iface  # noqa: F401  (starts QgsApplication)
from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QEventLoop, QObject, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QColor

sys.path = [os.path.abspath('..')] + sys.path
from riogisoffline.plugin.flow_arrows import (
    FLOW_ARROW_INITIAL_OFFSET_MM,
    FLOW_ARROW_INTERVAL_MM,
    FLOW_ARROW_MAX_SCALE,
    FLOW_ARROW_OFFSET_EXPRESSION,
    FlowArrowAnimator,
    _arrow_symbols,
    is_animated,
)


@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    display = Display(visible=0, size=(800, 600))
    display.start()
    yield


class FakeCanvas(QObject):
    scaleChanged = pyqtSignal(float)

    def __init__(self, scale=FLOW_ARROW_MAX_SCALE / 2):
        super().__init__()
        self._scale = scale

    def scale(self):
        return self._scale

    def set_scale(self, scale):
        self._scale = scale
        self.scaleChanged.emit(scale)


@pytest.fixture
def project():
    project = QgsProject.instance()
    project.clear()
    yield project
    project.clear()


def _pipe_layer(name="Avløpsledning"):
    """A layer styled like the real map (arrows only on 'Avløpsledning')."""
    from riogisoffline.plugin.refresh_map import MapRefresher

    layer = QgsVectorLayer("LineString?crs=EPSG:25832&field=fcode:string", name, "memory")
    MapRefresher()._add_rules(
        layer,
        {"rules": [{"expression": "1 = 1", "color": QColor(0, 0, 200),
                    "legend_label": "Avløp", "width": 0.6}]},
        "VA-data",
        None,
    )
    return layer


def _repaints_within(layer, ms=600):
    """Deferred repaint requests (QGIS animation frames) seen within ms."""
    calls = []
    layer.repaintRequested.connect(lambda deferred=False: calls.append(deferred))
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    return [deferred for deferred in calls if deferred]


def _offset_property(layer):
    from riogisoffline.plugin.flow_arrows import _OFFSET_ALONG_LINE

    _, markers = next(_arrow_symbols(layer.renderer()))
    return markers[0].dataDefinedProperties().property(_OFFSET_ALONG_LINE)


@pytest.mark.parametrize("frame, expected", [(0, 5), (3, 8), (20, 0), (21, 1)])
def test_offset_moves_one_step_per_frame_and_wraps(frame, expected):
    scope = QgsExpressionContextScope()
    scope.setVariable("symbol_frame", frame)
    context = QgsExpressionContext()
    context.appendScope(scope)
    assert QgsExpression(FLOW_ARROW_OFFSET_EXPRESSION).evaluate(context) == pytest.approx(expected)
    assert 0 <= expected < FLOW_ARROW_INTERVAL_MM


def test_enabled_animator_animates_arrows_when_zoomed_in(project):
    layer = _pipe_layer()
    project.addMapLayer(layer)

    animator = FlowArrowAnimator(FakeCanvas(), enabled=True)
    try:
        assert is_animated(layer)
        assert _offset_property(layer).isActive()
        # QGIS itself now repaints the layer for each frame, deferred
        assert len(_repaints_within(layer)) >= 3
    finally:
        animator.stop()


def test_no_animation_when_disabled(project):
    layer = _pipe_layer()
    project.addMapLayer(layer)

    animator = FlowArrowAnimator(FakeCanvas(), enabled=False)
    try:
        assert not is_animated(layer)
        assert _repaints_within(layer) == []
    finally:
        animator.stop()


def test_animation_follows_scale(project):
    layer = _pipe_layer()
    project.addMapLayer(layer)
    canvas = FakeCanvas()

    animator = FlowArrowAnimator(canvas, enabled=True)
    try:
        canvas.set_scale(FLOW_ARROW_MAX_SCALE * 5)
        assert not is_animated(layer)

        canvas.set_scale(FLOW_ARROW_MAX_SCALE / 4)
        assert is_animated(layer)
    finally:
        animator.stop()


def test_toggling_off_restores_static_arrows(project):
    layer = _pipe_layer()
    project.addMapLayer(layer)

    animator = FlowArrowAnimator(FakeCanvas(), enabled=True)
    try:
        animator.set_enabled(False)

        assert not is_animated(layer)
        assert not _offset_property(layer).isActive()
        _, markers = next(_arrow_symbols(layer.renderer()))
        assert markers[0].offsetAlongLine() == pytest.approx(FLOW_ARROW_INITIAL_OFFSET_MM)
    finally:
        animator.stop()


def test_layers_added_later_are_animated(project):
    """Regression: the map opened from the project file was never animated."""
    animator = FlowArrowAnimator(FakeCanvas(), enabled=True)
    try:
        layer = _pipe_layer()
        project.addMapLayer(layer)

        assert layer.id() in animator.layer_ids
        assert is_animated(layer)
    finally:
        animator.stop()


def test_layers_without_arrows_are_not_touched(project):
    plain = _pipe_layer("Vannledning")
    project.addMapLayer(plain)
    renderer_before = plain.renderer()

    animator = FlowArrowAnimator(FakeCanvas(), enabled=True)
    try:
        assert animator.layer_ids == []
        assert plain.renderer() is renderer_before
    finally:
        animator.stop()


def test_stop_turns_animation_off_and_disconnects(project):
    layer = _pipe_layer()
    project.addMapLayer(layer)
    canvas = FakeCanvas()

    animator = FlowArrowAnimator(canvas, enabled=True)
    animator.stop()
    assert not is_animated(layer)

    canvas.set_scale(FLOW_ARROW_MAX_SCALE / 3)
    assert not is_animated(layer)
