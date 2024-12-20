from pyvirtualdisplay import Display


import os
import sys
import pytest

from qgis.testing.mocked import get_iface
sys.path = [os.path.abspath('..')]+sys.path
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

