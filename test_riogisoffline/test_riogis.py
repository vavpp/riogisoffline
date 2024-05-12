import os
import sys

sys.path = [os.path.abspath('..')]+sys.path
print(os.listdir('..'))
#from riogisoffline.plugin.riogis import RioGIS
import pytest

# testing that tests work
def test_testing():
    assert 1 == 1


@pytest.fixture()
def setup_riogis():
    assert 1 == 1

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
