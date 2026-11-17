"""
Crash and error reports for the RioGIS plugin.

What is captured
- Python exceptions that come from this plugin's code (other plugins and
  QGIS itself are ignored). QGIS still shows its own error dialog.
- Errors from the background workers (sync, upload).
- Sessions that ended without the plugin being unloaded (QGIS crashed or was
  killed). Detected at the next start, with the user's last actions.

Privacy
- Reports include the operator name from the user settings, so the GIS team
  can contact the user (there are few users). This makes the reports personal
  data: keep the retention rule and access to the container limited.
- Before anything is written to disk, Azure keys/SAS signatures and the value
  of the azure key are removed. User names in file paths and e-mail addresses
  are removed too; the operator field is enough to know who to contact.
- Reports are written locally and sent to the GIS team's Azure container at
  the next sync/upload (which already needs a network connection). Sending
  can be turned off in the user settings; local reports are always kept
  (max MAX_REPORTS) so support can still ask for them.
"""

import json
import os
import platform
import re
import sys
import traceback
import uuid
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QLockFile, QSettings

SEND_SETTING = "riogisoffline/send_crash_reports"
MACHINE_ID_SETTING = "riogisoffline/crash_machine_id"
CRASH_CONTAINER = "plugin-crash-reports"
MAX_REPORTS = 50
MAX_BREADCRUMBS = 20

PLUGIN_PACKAGE_DIR = os.path.normcase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_active = None


def breadcrumb(text):
    """Record a user action in the active reporter (no-op when none is running)."""
    if _active is not None:
        _active.breadcrumb(text)


def active_reporter():
    return _active


# --------------------------------------------------------------------------
# Scrubbing
# --------------------------------------------------------------------------

_PATTERNS = [
    # Azure connection strings and SAS tokens
    (re.compile(r"(AccountKey=)[^;\"'\s]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"(SharedAccessSignature=)[^;\"'\s]+", re.IGNORECASE), r"\1<redacted>"),
    (re.compile(r"([?&]sig=)[^&\"'\s]+", re.IGNORECASE), r"\1<redacted>"),
    # user names in paths
    (re.compile(r"([A-Za-z]:[\\/]+Users[\\/]+)[^\\/\"'\s]+", re.IGNORECASE), r"\1<user>"),
    (re.compile(r"(/home/|/Users/)[^/\"'\s]+"), r"\1<user>"),
    # e-mail addresses
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "<email>"),
]


def scrub(text, secrets=()):
    """Remove secrets and personal data from a text."""
    if text is None:
        return None
    text = str(text)
    for secret in sorted((s for s in secrets if s and len(str(s)) >= 3), key=lambda s: -len(str(s))):
        text = text.replace(str(secret), "<redacted>")
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def is_plugin_traceback(tb):
    """True if any frame of the traceback is in this plugin's code."""
    for frame, _ in traceback.walk_tb(tb):
        if os.path.normcase(os.path.abspath(frame.f_code.co_filename)).startswith(PLUGIN_PACKAGE_DIR):
            return True
    return False


# --------------------------------------------------------------------------
# Reporter
# --------------------------------------------------------------------------

class CrashReporter:
    def __init__(self, report_dir, plugin_version="", secrets_provider=None, qsettings=QSettings,
                 operator_provider=None):
        """
        Args:
            report_dir (str): folder for local reports and the session marker
            plugin_version (str): from metadata.txt
            secrets_provider (callable): returns values that must never appear in a report
            operator_provider (callable): returns the operator name, included so the
                GIS team can contact the user about the error
        """
        self.report_dir = report_dir
        self.plugin_version = plugin_version
        self._secrets_provider = secrets_provider or (lambda: ())
        self._operator_provider = operator_provider or (lambda: "")
        self._qsettings = qsettings
        self._breadcrumbs = []
        self._session_id = None
        self._lock = None
        self._previous_hook = None

    # ------------------------------------------------------------- settings

    @property
    def sending_enabled(self):
        return self._qsettings().value(SEND_SETTING, True, type=bool)

    def set_sending_enabled(self, enabled):
        self._qsettings().setValue(SEND_SETTING, bool(enabled))

    @property
    def machine_id(self):
        """Random id per installation; lets the GIS team group reports without knowing who sent them."""
        settings = self._qsettings()
        machine_id = settings.value(MACHINE_ID_SETTING, "")
        if not machine_id:
            machine_id = uuid.uuid4().hex
            settings.setValue(MACHINE_ID_SETTING, machine_id)
        return machine_id

    # -------------------------------------------------------------- session

    def start(self):
        """Report sessions that ended uncleanly, start a new session and catch exceptions."""
        global _active
        os.makedirs(self.report_dir, exist_ok=True)
        self._report_unclean_sessions()

        self._session_id = uuid.uuid4().hex
        self._lock = QLockFile(self._lock_path(self._session_id))
        self._lock.setStaleLockTime(0)  # only a dead process makes the lock stale
        self._lock.tryLock(0)
        self._write_session_marker()

        self._previous_hook = sys.excepthook
        sys.excepthook = self._excepthook
        _active = self

    def stop(self):
        """Clean end of the session (plugin unload or QGIS closing normally)."""
        global _active
        if sys.excepthook == self._excepthook:
            sys.excepthook = self._previous_hook or sys.__excepthook__
        if self._session_id:
            self._remove(self._marker_path(self._session_id))
            if self._lock is not None:
                self._lock.unlock()
            self._session_id = None
        if _active is self:
            _active = None

    def breadcrumb(self, text):
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._breadcrumbs.append("{} {}".format(stamp, text))
        del self._breadcrumbs[:-MAX_BREADCRUMBS]
        if self._session_id:
            self._write_session_marker()

    def _marker_path(self, session_id):
        return os.path.join(self.report_dir, "session_{}.json".format(session_id))

    def _lock_path(self, session_id):
        return os.path.join(self.report_dir, "session_{}.lock".format(session_id))

    def _write_session_marker(self):
        marker = {
            "session": self._session_id,
            "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "breadcrumbs": self._breadcrumbs,
        }
        try:
            with open(self._marker_path(self._session_id), "w", encoding="utf-8") as file:
                json.dump(marker, file)
        except OSError:
            pass

    def _report_unclean_sessions(self):
        for name in os.listdir(self.report_dir):
            if not (name.startswith("session_") and name.endswith(".json")):
                continue
            session_id = name[len("session_"):-len(".json")]
            lock = QLockFile(self._lock_path(session_id))
            lock.setStaleLockTime(0)
            if not lock.tryLock(0):
                continue  # another QGIS instance is still running this session
            try:
                with open(os.path.join(self.report_dir, name), encoding="utf-8") as file:
                    marker = json.load(file)
            except (OSError, ValueError):
                marker = {}
            self._write_report({
                "type": "unclean_shutdown",
                "message": "Forrige QGIS-økt med RioGIS ble avsluttet uventet (krasj eller tvunget lukking).",
                "session_started": marker.get("started"),
                "breadcrumbs": marker.get("breadcrumbs", []),
            })
            lock.unlock()
            self._remove(os.path.join(self.report_dir, name))
            self._remove(self._lock_path(session_id))

    # --------------------------------------------------------------- capture

    def _excepthook(self, exc_type, exc_value, tb):
        try:
            if is_plugin_traceback(tb):
                self.capture_exception(exc_type, exc_value, tb)
        except Exception:  # never let the reporter itself break error handling
            pass
        previous = self._previous_hook or sys.__excepthook__
        previous(exc_type, exc_value, tb)

    def capture_exception(self, exc_type, exc_value, tb, context=""):
        return self._write_report({
            "type": "exception",
            "context": context,
            "exception": getattr(exc_type, "__name__", str(exc_type)),
            "message": str(exc_value),
            "traceback": "".join(traceback.format_exception(exc_type, exc_value, tb)),
            "breadcrumbs": list(self._breadcrumbs),
        })

    def capture_text(self, kind, message, traceback_text="", context=""):
        """For errors that arrive as text, e.g. from the background workers."""
        return self._write_report({
            "type": kind,
            "context": context,
            "message": message,
            "traceback": traceback_text,
            "breadcrumbs": list(self._breadcrumbs),
        })

    def _write_report(self, data):
        secrets = [s for s in self._secrets_provider() if s]
        now = datetime.now(timezone.utc)
        report = {
            "id": uuid.uuid4().hex,
            "created": now.isoformat(timespec="seconds"),
            "machine_id": self.machine_id,
            "operator": scrub(self._operator_provider() or "", secrets) or "",
            "plugin_version": self.plugin_version,
            "qgis_version": _qgis_version(),
            "python_version": platform.python_version(),
            "os": "{} {}".format(platform.system(), platform.release()),
        }
        for key, value in data.items():
            if isinstance(value, list):
                report[key] = [scrub(item, secrets) for item in value]
            else:
                report[key] = scrub(value, secrets)

        os.makedirs(self.report_dir, exist_ok=True)
        path = os.path.join(self.report_dir, "report_{}_{}.json".format(
            now.strftime("%Y%m%dT%H%M%S"), report["id"][:8]))
        with open(path, "w", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
        self._prune()
        return path

    # ---------------------------------------------------------------- upload

    def pending_reports(self):
        if not os.path.isdir(self.report_dir):
            return []
        return sorted(
            os.path.join(self.report_dir, name)
            for name in os.listdir(self.report_dir)
            if name.startswith("report_") and name.endswith(".json")
        )

    def upload_pending(self, upload_blob):
        """
        Send pending reports and delete the ones that were sent.

        Args:
            upload_blob (callable): upload_blob(blob_name, data_bytes)

        Returns:
            int: number of reports sent
        """
        if not self.sending_enabled:
            return 0
        sent = 0
        for path in self.pending_reports():
            with open(path, "rb") as file:
                data = file.read()
            upload_blob("{}/{}".format(self.machine_id, os.path.basename(path)), data)
            self._remove(path)
            sent += 1
        return sent

    # --------------------------------------------------------------- helpers

    def _prune(self):
        reports = self.pending_reports()
        for path in reports[:-MAX_REPORTS]:
            self._remove(path)

    @staticmethod
    def _remove(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _qgis_version():
    try:
        from qgis.core import Qgis
        return Qgis.version()
    except Exception:
        return ""


def default_report_dir():
    from qgis.core import QgsApplication
    return os.path.join(QgsApplication.qgisSettingsDirPath(), "riogisoffline", "crash_reports")


def plugin_version():
    """Version from metadata.txt."""
    import configparser

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "metadata.txt"), encoding="utf-8")
        return parser.get("general", "version", fallback="")
    except (configparser.Error, OSError):
        return ""
