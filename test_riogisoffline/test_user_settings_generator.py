import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from riogisoffline.plugin import user_settings_generator
from riogisoffline.plugin.user_settings_generator import UserSettingsGenerator


def make_dialog(operator, background_url, azure_key, folder_path):
    return SimpleNamespace(
        lineOperator=SimpleNamespace(text=lambda: operator),
        lineBGURL=SimpleNamespace(text=lambda: background_url),
        lineAzurekey=SimpleNamespace(text=lambda: azure_key),
        usersettingsPath=SimpleNamespace(filePath=lambda: str(folder_path)),
        done=Mock(),
    )


@pytest.mark.parametrize("select_project_folder", [False, True])
def test_run_writes_settings_and_backup(tmp_path, monkeypatch, select_project_folder):
    selected_folder = tmp_path / "RioGIS offline" if select_project_folder else tmp_path
    selected_folder.mkdir(exist_ok=True)
    settings_path = tmp_path / "bruker_settings.json"
    monkeypatch.setattr(
        user_settings_generator.utils,
        "get_user_settings_path",
        lambda: str(settings_path),
    )
    dialog = make_dialog(
        operator="Ola Nordmann",
        background_url="https://example.test/background.gpkg",
        azure_key="connection-string",
        folder_path=selected_folder,
    )

    generator = UserSettingsGenerator(dialog)
    generator.run()

    userfolder = tmp_path / "RioGIS offline"
    expected = {
        "operator": "Ola Nordmann",
        "background_url": "https://example.test/background.gpkg",
        "azure_key": "connection-string",
        "userfolder": str(userfolder),
        "output_folder": str(userfolder / "output"),
        "file_folder": str(userfolder / "filer"),
    }
    backup_path = userfolder / "filer" / "bruker_settings_BACKUP.json"

    assert json.loads(settings_path.read_text(encoding="utf-8")) == expected
    assert json.loads(backup_path.read_text(encoding="utf-8")) == expected
    dialog.done.assert_called_once_with(1)


@pytest.mark.parametrize(
    ("field_overrides", "folder_path", "warning"),
    [
        (
            {"azure_key": ""},
            None,
            "Alle felt må fylles ut",
        ),
        (
            {"background_url": "https://example.test/background.tif"},
            None,
            "Feil verdi for URL bakgrunnskart",
        ),
        (
            {"operator": "Ola"},
            None,
            "Operatørnavn ikke godkjent. Husk å skrive både navn og etternavn (på formen Navn Etternavn)",
        ),
        (
            {},
            "missing-folder",
            "Ugyldig mappeplassering. Velg en eksisternde mappe",
        ),
    ],
)
def test_validate_input_rejects_invalid_values(
    tmp_path, monkeypatch, field_overrides, folder_path, warning
):
    warnings = Mock()
    monkeypatch.setattr(
        user_settings_generator.utils, "printWarningMessage", warnings
    )
    generator = UserSettingsGenerator(make_dialog("", "", "", tmp_path))
    generator.user_settings_dict = {
        "operator": "Ola Nordmann",
        "background_url": "https://example.test/background.gpkg",
        "azure_key": "connection-string",
    }
    generator.user_settings_dict.update(field_overrides)
    generator.user_input_folder_path = (
        str(tmp_path / folder_path) if folder_path else str(tmp_path)
    )

    assert not generator.validate_input()
    warnings.assert_called_once_with(warning)


def test_run_leaves_dialog_open_when_validation_fails(tmp_path, monkeypatch):
    settings_path = tmp_path / "bruker_settings.json"
    monkeypatch.setattr(
        user_settings_generator.utils,
        "get_user_settings_path",
        lambda: str(settings_path),
    )
    monkeypatch.setattr(user_settings_generator.utils, "printWarningMessage", Mock())
    dialog = make_dialog(
        operator="Ola Nordmann",
        background_url="https://example.test/background.tif",
        azure_key="connection-string",
        folder_path=tmp_path,
    )

    UserSettingsGenerator(dialog).run()

    assert not settings_path.exists()
    dialog.done.assert_not_called()
