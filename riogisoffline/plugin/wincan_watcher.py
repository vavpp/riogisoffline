"""
Follows the WinCan folder and reads the active inspection database when it changes.

QFileSystemWatcher reports changes quickly, but is not reliable on all drives,
so a poll timer checks the file's (mtime, size) as a fallback. The poll also
notices when WinCan starts writing to another project folder (new day / new
car). Reads are debounced so a burst of writes gives one read.
"""

import os

from qgis.PyQt.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

from .wincan_reader import (
    SnapshotBusy,
    file_signature,
    find_active_database,
    read_database,
)

POLL_INTERVAL_MS = 2000
DEBOUNCE_MS = 1000


class WincanWatcher(QObject):
    """
    Signals:
        inspectionsChanged(str db_path, list inspections)
        databaseChanged(str db_path): another project database became active ("" if none)
        readFailed(str message)
    """

    inspectionsChanged = pyqtSignal(str, list)
    databaseChanged = pyqtSignal(str)
    readFailed = pyqtSignal(str)

    def __init__(self, parent=None, poll_ms=POLL_INTERVAL_MS, debounce_ms=DEBOUNCE_MS,
                 reader=read_database):
        super().__init__(parent)
        self._root = None
        self._db_path = None
        self._read_signature = None
        self._reader = reader

        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.fileChanged.connect(self._schedule_read)
        self._fs_watcher.directoryChanged.connect(self._schedule_read)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(poll_ms)
        self._poll_timer.timeout.connect(self.poll)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(debounce_ms)
        self._debounce.timeout.connect(self.read_now)

    # ---------------------------------------------------------------- public

    @property
    def root(self):
        return self._root

    @property
    def db_path(self):
        return self._db_path

    @property
    def is_running(self):
        return self._poll_timer.isActive()

    def set_root(self, root):
        self._root = root or None
        self._switch_database(None)
        if self.is_running:
            self.poll()

    def start(self):
        self._poll_timer.start()
        self.poll()

    def stop(self):
        self._poll_timer.stop()
        self._debounce.stop()
        self._switch_database(None)

    def poll(self):
        """Pick up a new active database and schedule a read if the file changed."""
        active = find_active_database(self._root) if self._root else None
        if active != self._db_path:
            self._switch_database(active)
            if active:
                self.read_now()
            return
        if active and file_signature(active) != self._read_signature:
            self._schedule_read()

    def read_now(self):
        if not self._db_path:
            return
        signature = file_signature(self._db_path)
        try:
            inspections = self._reader(self._db_path)
        except SnapshotBusy:
            # WinCan is writing; the next poll tries again
            return
        except OSError as error:
            self.readFailed.emit("Kunne ikke lese WinCan-databasen: {}".format(error))
            return
        self._read_signature = signature
        self.inspectionsChanged.emit(self._db_path, inspections)

    # --------------------------------------------------------------- private

    def _schedule_read(self, *_args):
        self._debounce.start()

    def _switch_database(self, db_path):
        watched = self._fs_watcher.files() + self._fs_watcher.directories()
        if watched:
            self._fs_watcher.removePaths(watched)
        self._db_path = db_path
        self._read_signature = None
        if db_path:
            self._fs_watcher.addPath(db_path)
            self._fs_watcher.addPath(os.path.dirname(db_path))
        self.databaseChanged.emit(db_path or "")
