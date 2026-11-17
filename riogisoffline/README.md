QGIS plugin exports attributes of a given feature to a Norwegian module of WinCan VX.

![image](https://raw.githubusercontent.com/vavpp/riogisoffline/a0fa68f0b98a24f70ba023e306580d866fb3a7ca/icon.png)

# Acknowledgments
* [QGIS](https://github.com/qgis/QGIS)

## Azure Storage dependency on Windows

The plugin can be loaded without the Azure SDK. Synchronization and upload require
`azure-storage-blob`; if it is missing, RioGIS displays installation instructions.

Install the package in the Python environment used by the same QGIS installation:

1. Close QGIS and open its OSGeo4W Shell.
2. Run `python -m pip install --user azure-storage-blob`.
3. Restart QGIS.

Do not install the package into an unrelated system Python. See the
[OSGeo4W instructions for external Python packages](https://trac.osgeo.org/osgeo4w/wiki/ExternalPythonPackages).
QGIS's `plugin_dependencies` metadata is for other QGIS plugins, not Python packages
([QGIS plugin documentation](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/plugins/plugins.html#metadata-txt)).

## Map printout and templates

Choose **Forhåndsvis og skriv ut kart** in the RioGIS panel, then select a layout and
one of the fixed scales 1:500, 1:1000, 1:2000, 1:5000 or 1:10000. While the dialog is
open, the area that will be printed is shown as a blue rectangle on the map; pan the
map to move it. The last chosen scale and layout are remembered.

**Åpne forhåndsvisning** opens QGIS Layout Designer with the finished A4 landscape
printout. Adjust it there if needed, then use QGIS's PDF export. The standard layout has
the map on the left and a panel on the right with title, date, operator name, scale,
legend, north arrow, scale bar and a note about map-data limitations and attribution.

The legend only lists thematic layers (not the background map) that have features in
the printed area. It is shrunk (smaller text and symbols, then more columns) until it
fits the space the layout has for it. If it still does not fit, a warning is shown.

To keep an edited layout for later, choose **Layout > Save as RioGIS template...** in
the designer. Templates are stored in the user's `output/print_templates` folder and
appear in the layout selector the next time it opens. The standard layout is always
available. A map with loaded layers and an operator name in user settings is required.

