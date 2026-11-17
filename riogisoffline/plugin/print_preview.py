"""Shows the area that will be printed as a rectangle on the map canvas."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis, QgsGeometry
from qgis.gui import QgsRubberBand


class PrintAreaPreview:
    """Draws (and removes) the print area on the canvas."""

    FILL_COLOR = QColor(0, 98, 186, 30)
    STROKE_COLOR = QColor(0, 98, 186, 220)

    def __init__(self, canvas):
        self._canvas = canvas
        self._band = None

    def show(self, extent):
        """Show the rectangle (map units of the canvas CRS)."""
        if self._band is None:
            self._band = QgsRubberBand(self._canvas, Qgis.GeometryType.Polygon)
            self._band.setFillColor(self.FILL_COLOR)
            self._band.setStrokeColor(self.STROKE_COLOR)
            self._band.setWidth(2)
            self._band.setLineStyle(Qt.PenStyle.DashLine)
        self._band.setToGeometry(QgsGeometry.fromRect(extent), None)
        self._band.show()

    def geometry(self):
        return self._band.asGeometry() if self._band is not None else None

    def clear(self):
        if self._band is None:
            return
        self._band.reset(Qgis.GeometryType.Polygon)
        self._canvas.scene().removeItem(self._band)
        self._band = None
