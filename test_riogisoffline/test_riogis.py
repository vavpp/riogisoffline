import os
import sys

sys.path = [os.path.abspath('..')]+sys.path

#from riogisoffline.plugin.riogis import RioGIS
import pytest


def test_import_pckg():
    try:
        import riogisoffline
        assert 1 == 1
    except:
        assert 1==2
        
def test_pckg_in_syspath():
    passed = False
    for path in sys.path:
        if 'riogisoffline' in path:
            passed =True
    assert passed
        
# testing that import qgis work
def test_import_qgis():
    try:
        import qgis.core
        assert 1==1
    except:
        assert 1==2


@pytest.fixture()
def setup_riogis():
    import riogisoffline
    import qgis
    import riogisoffline.plugin.riogis as rio
    import riogisoffline.plugin.utils as utils
    r = rio.RioGis()
    pdir = utils.get_plugin_dir()
    print(pdir,flush=True)

# test as many methods as possible

def test_setup():
    assert 1 == 1

def test_load_select_elements():
    assert 1 == 1

def test_map_attributes():
    assert 1 == 1

def test_handle_map_click():
    assert 1 == 1

def test_export_feature():
    assert 1 == 1

def test_select_feature():
    assert 1 == 1

def test_update_feature_status():
    assert 1 == 1

def test_get_feature_data():
    assert 1 == 1

def test_refresh_map():
    assert 1 == 1

def test_write_output_file():
    assert 1 == 1

def test_populate_select_values():
    assert 1 == 1

def test_select_layer():
    assert 1 == 1

def test_run():
    assert 1 == 1
