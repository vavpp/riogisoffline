import pytest

from riogisoffline.plugin.utils import (
    get_plugin_dir,
    load_json,
    get_settings_path,
    get_user_settings_path
)

def test_get_plugin_dir():
    assert get_plugin_dir()

def test_get_settings_path():
    assert get_settings_path()
    assert "riogisoffline" in get_settings_path()
    assert "settings.json" in get_settings_path()

def test_get_user_settings_path():
    assert get_user_settings_path()
    assert "riogisoffline" in get_user_settings_path()
    assert "bruker_settings.json" in get_user_settings_path()

def test_load_json():
    path = get_settings_path()
    assert load_json(path)
