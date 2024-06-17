from pyvirtualdisplay import Display


import os
import sys
import pytest

from qgis.testing.mocked import get_iface
sys.path = [os.path.abspath('..')]+sys.path
from riogisoffline.plugin.riogis import RioGIS
from mock_extension import Layer, Point


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
    riogis_without_run.select_layer([Layer()])
    #riogis_without_run.layer = Layer()
    return riogis_without_run
    
def test_run(riogis_without_run):
    riogis_without_run.run()

def test_select_layer(riogis_without_run):
    riogis_without_run.run()
    riogis_without_run.select_layer([Layer()])

def test_load_select_elements(riogis):
    data = riogis.load_select_elements()
    assert data

def test_get_feature_data(riogis):
    # TypeError: 'Mock' object is not iterable
    riogis.select_layer([Layer()])
    data = riogis.get_feature_data()
    assert data

def test_map_attributes(riogis):
    # TypeError: 'Mock' object is not iterable
    
    riogis.map_attributes(riogis.get_feature_data())

def test_handle_map_click(riogis):
    riogis.handle_map_click()
    
def test_select_feature(riogis):
    # TypeError: 'Mock' object is not iterable
    
    from qgis.core import QgsPointXY
    point = QgsPointXY(0,0)
    riogis.select_feature(point)

def test_export_feature(riogis):
    # TypeError: 'Mock' object is not iterable
    
    riogis.export_feature()
    
def test_update_feature_status(riogis):
    # init data
    riogis.map_attributes(riogis.get_feature_data())
    
    riogis.update_feature_status()

def test_refresh_map(riogis):
    # AttributeError: 'NoneType' object has no attribute 'messageBar'
    
    riogis.refresh_map()

def test_write_output_file(riogis):
    # AttributeError: 'NoneType' object has no attribute 'get'
    
    riogis.write_output_file()

def test_populate_select_values(riogis):
    riogis.populate_select_values()

def test_select_layer(riogis):
    riogis.populate_select_values()

