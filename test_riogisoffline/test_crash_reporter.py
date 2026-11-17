"""Tests for crash and error reports."""

import json
import os
import subprocess
import sys

import pytest

from qgis.testing.mocked import get_iface  # noqa: F401  (starts QgsApplication)

sys.path = [os.path.abspath('..')] + sys.path
from riogisoffline.plugin import crash_reporter as module
from riogisoffline.plugin import utils
from riogisoffline.plugin.crash_reporter import CrashReporter, MAX_REPORTS, scrub

AZURE_KEY = ("DefaultEndpointsProtocol=https;AccountName=vavtest;"
             "AccountKey=c2VjcmV0LWtleS0xMjM0NTY3ODkw;EndpointSuffix=core.windows.net")
OPERATOR = "Ola Nordmann"


class FakeSettings:
    store = {}

    def value(self, key, default=None, type=None):
        value = self.store.get(key, default)
        return type(value) if type is not None and value is not None else value

    def setValue(self, key, value):
        self.store[key] = value


@pytest.fixture
def reporter(tmp_path):
    FakeSettings.store = {}
    reporter = CrashReporter(str(tmp_path / "reports"), "0.7.0",
                             secrets_provider=lambda: [AZURE_KEY],
                             qsettings=FakeSettings,
                             operator_provider=lambda: OPERATOR)
    yield reporter
    reporter.stop()


def _reports(reporter):
    result = []
    for path in reporter.pending_reports():
        with open(path, encoding="utf-8") as file:
            result.append(json.load(file))
    return result


# ------------------------------------------------------------------ scrubbing

@pytest.mark.parametrize("text, forbidden, kept", [
    (AZURE_KEY, "c2VjcmV0", "AccountKey=<redacted>"),
    ("https://x.blob.core.windows.net/c/b?sv=2024&sig=AbC%2Bdef123&se=2026", "AbC%2Bdef123", "sig=<redacted>"),
    (r'File "C:\Users\VAV377501\AppData\x.py"', "VAV377501", r"C:\Users\<user>"),
    ("File \"/home/kari/.local/x.py\"", "kari", "/home/<user>"),
    ("kontakt ola.nordmann@vav.oslo.kommune.no", "ola.nordmann", "<email>"),
    ("Operatør: Ola Nordmann", "Ola Nordmann", "<redacted>"),
])
def test_scrub_removes_secrets_and_personal_data(text, forbidden, kept):
    # patterns must work also for keys the plugin does not know about
    cleaned = scrub(text, [OPERATOR])
    assert forbidden not in cleaned
    assert kept in cleaned


def test_scrub_replaces_known_secrets_completely():
    cleaned = scrub("Feil med nøkkel {} for {}".format(AZURE_KEY, OPERATOR), [AZURE_KEY, OPERATOR])
    assert cleaned == "Feil med nøkkel <redacted> for <redacted>"


# ------------------------------------------------------------------ capture

def _raise_in_plugin_code():
    try:
        utils.load_json("does-not-exist-{}.json".format(AZURE_KEY))
    except Exception:
        return sys.exc_info()


def test_exception_report_has_operator_but_no_secrets(reporter):
    reporter.breadcrumb("Synkroniser")
    reporter.capture_exception(*_raise_in_plugin_code())

    [report] = _reports(reporter)
    text = json.dumps(report, ensure_ascii=False)
    assert report["type"] == "exception"
    assert report["exception"] == "Exception"
    assert "utils.py" in report["traceback"]
    assert report["plugin_version"] == "0.7.0"
    assert report["breadcrumbs"][-1].endswith("Synkroniser")
    # the operator is included so the GIS team can contact the user
    assert report["operator"] == OPERATOR
    assert "c2VjcmV0" not in text and "AccountName=vavtest" not in text
    assert os.path.expanduser("~") not in text


def test_excepthook_reports_plugin_errors_and_keeps_qgis_handler(reporter, monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: calls.append(args))
    reporter.start()

    sys.excepthook(*_raise_in_plugin_code())

    assert len(calls) == 1                      # QGIS' own handler still runs
    assert len(_reports(reporter)) == 1


def test_excepthook_ignores_errors_from_other_code(reporter, monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: calls.append(args))
    reporter.start()
    try:
        raise ValueError("someone else's bug")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    assert len(calls) == 1
    assert _reports(reporter) == []


def test_stop_restores_previous_excepthook(reporter, monkeypatch):
    previous = lambda *args: None  # noqa: E731
    monkeypatch.setattr(sys, "excepthook", previous)
    reporter.start()
    reporter.stop()
    assert sys.excepthook is previous


def test_number_of_local_reports_is_limited(reporter):
    for i in range(MAX_REPORTS + 5):
        reporter.capture_text("worker_error", "feil {}".format(i))
    assert len(reporter.pending_reports()) == MAX_REPORTS


# ------------------------------------------------------------------ sessions

CRASHING_SESSION = r"""
import json, os, sys
from qgis.PyQt.QtCore import QLockFile
folder, session = sys.argv[1], sys.argv[2]
lock = QLockFile(os.path.join(folder, "session_%s.lock" % session))
lock.setStaleLockTime(0)
assert lock.tryLock(0)
with open(os.path.join(folder, "session_%s.json" % session), "w") as f:
    json.dump({"session": session, "started": "2026-11-17T10:00:00+00:00",
               "breadcrumbs": ["10:01:00 Skriv ut kart"]}, f)
os._exit(1)   # die like a crash: no cleanup, lock file left behind
"""


def test_crash_in_previous_session_is_reported_at_next_start(reporter, tmp_path):
    os.makedirs(reporter.report_dir, exist_ok=True)
    subprocess.run([sys.executable, "-c", CRASHING_SESSION, reporter.report_dir, "deadbeef"],
                   env=os.environ.copy(), check=False, timeout=60)
    assert os.path.exists(os.path.join(reporter.report_dir, "session_deadbeef.lock"))

    reporter.start()

    [report] = _reports(reporter)
    assert report["type"] == "unclean_shutdown"
    assert report["breadcrumbs"] == ["10:01:00 Skriv ut kart"]
    assert not os.path.exists(os.path.join(reporter.report_dir, "session_deadbeef.json"))


def test_clean_exit_is_not_reported(tmp_path):
    folder = str(tmp_path / "reports")
    first = CrashReporter(folder, qsettings=FakeSettings)
    first.start()
    first.breadcrumb("Last kart")
    first.stop()

    second = CrashReporter(folder, qsettings=FakeSettings)
    second.start()
    try:
        assert second.pending_reports() == []
    finally:
        second.stop()


def test_session_of_another_running_qgis_is_left_alone(tmp_path):
    folder = str(tmp_path / "reports")
    running = CrashReporter(folder, qsettings=FakeSettings)
    running.start()
    other = CrashReporter(folder, qsettings=FakeSettings)
    try:
        other.start()
        assert other.pending_reports() == []
    finally:
        other.stop()
        running.stop()


# ------------------------------------------------------------------ upload

def test_upload_sends_and_removes_reports(reporter):
    reporter.capture_text("worker_error", "feil")
    sent = {}

    count = reporter.upload_pending(lambda name, data: sent.update({name: data}))

    assert count == 1
    [name] = sent
    assert name.startswith(reporter.machine_id + "/report_")
    assert json.loads(sent[name])["message"] == "feil"
    assert reporter.pending_reports() == []


def test_upload_respects_opt_out(reporter):
    reporter.capture_text("worker_error", "feil")
    reporter.set_sending_enabled(False)

    assert reporter.upload_pending(lambda name, data: pytest.fail("must not send")) == 0
    assert len(reporter.pending_reports()) == 1


def test_failed_upload_keeps_reports(reporter):
    reporter.capture_text("worker_error", "feil")

    def broken(name, data):
        raise OSError("no network")

    with pytest.raises(OSError):
        reporter.upload_pending(broken)
    assert len(reporter.pending_reports()) == 1


def test_breadcrumb_without_active_reporter_is_harmless():
    module.breadcrumb("ingen rapportør")


def test_plugin_version_is_read_from_metadata():
    assert module.plugin_version().count(".") == 2
