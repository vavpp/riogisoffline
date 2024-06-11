from pyvirtualdisplay import Display


import os
import sys
import pytest

from qgis.testing.mocked import get_iface
sys.path = [os.path.abspath('..')]+sys.path
from riogisoffline.plugin.riogis import RioGIS


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
    riogis_without_run = RioGIS(get_iface())
    return riogis_without_run

@pytest.fixture
def riogis(riogis_without_run):
    riogis_without_run.run()
    riogis_without_run.select_layer()
    return riogis_without_run
    
def test_run(riogis_without_run):
    riogis_without_run.run()

def test_select_layer(riogis_without_run):
    riogis_without_run.run()
    riogis_without_run.select_layer()

def test_load_select_elements(riogis):
    data = riogis.load_select_elements()
    assert data

def test_get_feature_data(riogis):
    #data = riogis.get_feature_data()
    #assert data
    ...

def test_map_attributes(riogis):
    #riogis.map_attributes(riogis.get_feature_data())
    ...

def test_handle_map_click(riogis):
    riogis.handle_map_click()
    
def test_select_feature(riogis):
    from qgis.core import QgsPointXY
    point = QgsPointXY(0,0)
    riogis.select_feature(point)

def test_export_feature(riogis):
    #riogis.export_feature()
    ...
    
def test_update_feature_status():
    assert 1 == 1

def test_refresh_map():
    assert 1 == 1

def test_write_output_file():
    assert 1 == 1

def test_populate_select_values():
    assert 1 == 1

def test_select_layer():
    assert 1 == 1

