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

## Crash and error reports

The plugin writes a report when its own code raises an error, when sync or upload fails,
and when a QGIS session using RioGIS ended unexpectedly (detected at the next start).
Reports contain the error, the plugin/QGIS/Python versions, the user's last actions in
RioGIS and the operator name from the user settings, so the GIS team can contact the user.
The reports are therefore personal data. Azure keys and SAS signatures, user names in file
paths and e-mail addresses are removed before a report is saved.

Reports are stored in the QGIS profile (`riogisoffline/crash_reports`, at most 50) and
sent to the `plugin-crash-reports` container at the next sync or upload, under a random
id per installation. Users can turn sending off in the user settings
("Send feilrapporter til GIS-teamet"). The container and a 90-day deletion rule must be
set up in Azure by the GIS team; until the container exists, reports stay local.

## WinCan live inspections

In the **WinCan live** section of the RioGIS panel, choose the folder WinCan saves its
projects in (for example `D:\TV-rapporter`) and tick **Følg aktive inspeksjoner**. The
plugin follows the project folder WinCan wrote to most recently and draws the inspection
observations on the pipes in the map while the inspection is running (within about two
seconds of a change).

- Pipes and manholes are matched on LSID and PSID. An inspection on a pipe that is not in
  the map is listed in the status text.
- The start manhole is read from the memo of the "Start inspeksjon" observation
  (e.g. "I kum 396525"). Use **Snu retning** if the observations end up at the wrong end.
- Length observations are paired on `OBS_CD_Code2` (1 = start, 9 = end) and the last two
  digits of `OBS_CD_Code1`. A start without an end lasts until the end of the inspection,
  or until the camera position while inspecting. Overlapping ones are drawn side by side.
- Colours show the grade from VAV's condition calculator (same tables as the FME
  workflow), using the pipe type (`fcode`) from the map. Info codes (SI, IF, VN, ANM, ME …)
  are hidden unless **Vis info-koder** is ticked. Colours, shapes and layer names can be
  changed in `settings.json` under `wincan`.
- The plugin never opens WinCan's database directly. It copies the file and reads the
  copy, and skips a read while WinCan is writing, so it cannot lock the database WinCan
  is writing to.

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

