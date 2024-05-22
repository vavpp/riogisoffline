import os
import sys
import pytest

sys.path = [os.path.abspath('..')]+sys.path

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

@pytest.fixture()
def riogis_instance():
    from riogisoffline.plugin.riogis import RioGIS
    return RioGIS()

def test_run(riogis_instance):
    #riogis_instance.run()
    ...
    
def test_setup(riogis_instance):
    ...

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

