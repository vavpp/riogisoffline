import pytest

from riogisoffline.plugin.utils import (
    get_plugin_dir,
    load_json
)

def test_get_plugin_dir():
    assert get_plugin_dir()

def test_load_json():
    assert load_json()