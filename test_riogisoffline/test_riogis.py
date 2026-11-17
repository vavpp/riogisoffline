from pyvirtualdisplay import Display


import os
import sys
import builtins
import pytest

from qgis.testing.mocked import get_iface
sys.path = [os.path.abspath('..')]+sys.path
from riogisoffline.plugin import riogis as riogis_module
from riogisoffline.plugin.riogis import RioGIS
from riogisoffline.plugin.utils import get_plugin_dir
from mock_extension import Layer, Point
from qgis.core import QgsPointXY

FEATURE_LAYER_NAME = "Bestillinger"

@pytest.fixture(scope="session", autouse=True)
def virtual_display():
    # Start a virtual display
    display = Display(visible=0, size=(800, 600))
    display.start()

    # Yield to allow tests to run inside the virtual display context
    yield


def test_import_pckg():
    try:
        import riogisoffline
    except:
        raise AssertionError ("The riogisoffline package failed to import")
        
def test_import_qgis():
    try:
        import qgis.core
    except:
        raise AssertionError ("qgis package failed to import")

def test_pckg_in_syspath():
    passed = False
    for path in sys.path:
        if 'riogisoffline' in path:
            passed = True
    assert passed

@pytest.fixture
def riogis_without_run():
    iface = get_iface()
    riogis_without_run = RioGIS(iface)
    return riogis_without_run

@pytest.fixture
def riogis(riogis_without_run):
    riogis_without_run.run()
    riogis_without_run.select_layer([Layer()], FEATURE_LAYER_NAME)
    #riogis_without_run.layer = Layer()
    return riogis_without_run
    
def test_run(riogis_without_run):
    riogis_without_run.run()

def test_missing_azure_package_shows_installation_instructions(
    riogis_without_run, tmp_path, monkeypatch
):
    settings_path = tmp_path / "bruker_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        riogis_module.utils, "get_user_settings_path", lambda: str(settings_path)
    )
    monkeypatch.delitem(
        sys.modules, "riogisoffline.plugin.azure_blob_storage_connection", raising=False
    )

    messages = []

    class MessageBox:
        @staticmethod
        def warning(parent, title, text):
            messages.append((title, text))

    monkeypatch.setattr(riogis_module, "QMessageBox", MessageBox)
    original_import = builtins.__import__

    def import_without_azure(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "azure.storage.blob":
            raise ModuleNotFoundError("No module named 'azure'", name="azure")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_azure)

    assert not riogis_without_run.establish_azure_connection()
    assert len(messages) == 1
    assert "OSGeo4W Shell" in messages[0][1]
    assert "pip install --user azure-storage-blob" in messages[0][1]

def test_select_layer(riogis_without_run):
    riogis_without_run.run()
    riogis_without_run.select_layer([Layer()], FEATURE_LAYER_NAME)
    
def test_select_nearest_feature(riogis):
    
    point = QgsPointXY(0,0)
    riogis.select_nearest_feature(point, layers=[Layer()])
    assert riogis.feature is not None

def test_get_feature_data(riogis):
    
    riogis.select_layer([Layer()], FEATURE_LAYER_NAME)
    point = QgsPointXY(0,0)
    riogis.select_nearest_feature(point, layers=[Layer()])
    data = riogis.get_feature_data()
    assert data

def test_map_attributes(riogis):
    riogis.select_layer([Layer()], FEATURE_LAYER_NAME)
    point = QgsPointXY(0,0)
    riogis.select_nearest_feature(point, layers=[Layer()])
    riogis.data = riogis.get_feature_data()
    riogis.settings.update({
        "operator": "Operator"
    })
    riogis.map_attributes()

def test_handle_map_click(riogis):
    riogis.handle_map_click(lambda: ...)
    
def test_export_feature(riogis):
    riogis.select_layer([Layer()], FEATURE_LAYER_NAME)
    point = QgsPointXY(0,0)
    riogis.select_nearest_feature(point, layers=[Layer()])
    riogis.data = riogis.get_feature_data()
    riogis.settings.update({
        "operator": "Operator"
    })
    riogis.map_attributes()
    riogis.iface.activeLayer = lambda: Layer()
    riogis.handle_select_feature(point, None)
    
def test_update_feature_status(riogis):
    riogis.select_layer([Layer()], FEATURE_LAYER_NAME)
    point = QgsPointXY(0,0)
    riogis.select_nearest_feature(point, layers=[Layer()])
    riogis.data = riogis.get_feature_data()
    riogis.settings.update({
        "operator": "Operator"
    })
    riogis.map_attributes()
    riogis.update_feature_status()

def test_refresh_map(riogis):
    riogis.refresh_map()

def test_write_output_file(riogis):
    riogis.select_layer([Layer()], FEATURE_LAYER_NAME)
    point = QgsPointXY(0,0)
    riogis.select_nearest_feature(point, layers=[Layer()])
    riogis.data = riogis.get_feature_data()
    riogis.settings.update({
        "operator": "Operator",
        "output_folder": get_plugin_dir()
    })
    riogis.map_attributes()
    riogis.iface.activeLayer = lambda: Layer()
    riogis.handle_select_feature(point, None)
    riogis.write_output_file()
    output_dirlist = os.listdir(get_plugin_dir())
    print(output_dirlist)
    assert 'AF-123.txt' in output_dirlist

def test_map_refresher_registers_fresh_layers_after_project_clear(
    riogis_without_run, tmp_path, monkeypatch
):
    monkeypatch.setenv("BACKGROUND_MAP", str(tmp_path / "background.gpkg"))
    monkeypatch.setenv("SOURCE_MAP", str(tmp_path / "source.db"))
    from qgis.core import QgsProject, QgsVectorLayer
    import importlib
    from riogisoffline.plugin import refresh_map as refresh_map_module

    refresh_map_module = importlib.reload(refresh_map_module)
    project = QgsProject.instance()
    project.clear()
    refresher = refresh_map_module.MapRefresher()
    source_layer = QgsVectorLayer("Point?crs=EPSG:4326", "Test layer", "memory")

    first_group = project.layerTreeRoot().addGroup("First group")
    refresher.add_map_layers(first_group, {"geometry": source_layer, "rules": []}, "Test")

    assert len(project.mapLayers()) == 1
    first_registered_layer = next(iter(project.mapLayers().values()))
    assert first_group.findLayer(first_registered_layer) is not None

    project.clear()

    second_group = project.layerTreeRoot().addGroup("Second group")
    refresher.add_map_layers(second_group, {"geometry": source_layer, "rules": []}, "Test")

    assert len(project.mapLayers()) == 1
    second_registered_layer = next(iter(project.mapLayers().values()))
    assert second_group.findLayer(second_registered_layer) is not None
    assert source_layer.isValid()
    project.clear()

def test_map_refresher_skips_invalid_layers(riogis_without_run, tmp_path, monkeypatch):
    monkeypatch.setenv("BACKGROUND_MAP", str(tmp_path / "background.gpkg"))
    monkeypatch.setenv("SOURCE_MAP", str(tmp_path / "source.db"))
    from qgis.core import QgsProject, QgsVectorLayer
    import importlib
    from riogisoffline.plugin import refresh_map as refresh_map_module

    refresh_map_module = importlib.reload(refresh_map_module)
    warnings = []
    monkeypatch.setattr(refresh_map_module.utils, "printWarningMessage", warnings.append)
    project = QgsProject.instance()
    project.clear()
    group = project.layerTreeRoot().addGroup("Invalid group")
    invalid_layer = QgsVectorLayer(
        str(tmp_path / "missing.gpkg") + "|layername=Missing",
        "Missing layer",
        "ogr",
    )

    assert not invalid_layer.isValid()
    refresh_map_module.MapRefresher().add_map_layers(
        group, {"geometry": invalid_layer, "rules": []}, "Test"
    )

    assert not project.mapLayers()
    assert warnings == ["Kan ikke laste ugyldig kartlag: Missing layer"]
    project.clear()

