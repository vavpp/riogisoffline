"""
Reading WinCan VX inspection databases (<project>/DB/<project>.db3).

WinCan writes to the database while an inspector is working. To never block
WinCan, this module does not open the live file with SQLite. It copies the
file with plain file I/O and reads the copy. A copy taken while WinCan is in
the middle of a write (journal file present, or the file changes during the
copy) is thrown away; the caller simply tries again later.

No QGIS imports here, so the module can be tested on its own.
"""

import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

META_SUFFIX = "_Meta.db3"


class SnapshotBusy(Exception):
    """The database was being written while it was copied; try again later."""


@dataclass
class Observation:
    pk: str
    distance: float
    opcode: str
    text: str
    grade_s: Optional[int]
    clock: Optional[int]
    cd_code1: Optional[int]
    cd_code2: Optional[int]
    memo: str
    timestamp: str
    sort_order: int = 0
    media: List[str] = field(default_factory=list)


@dataclass
class Inspection:
    pk: str
    lsid: Optional[str]
    from_psid: Optional[str]
    to_psid: Optional[str]
    section_length: float
    section_type: Optional[str]
    inspected_length: float
    start_time: str
    timestamp: str
    observations: List[Observation] = field(default_factory=list)

    @property
    def start_memo(self):
        """Memo of the "Start inspeksjon" (SI) observation, where the start manhole is written."""
        for obs in self.observations:
            if obs.opcode == "SI":
                return obs.memo or ""
        return ""

    @property
    def is_finished(self):
        return any(obs.opcode == "IF" for obs in self.observations)

    @property
    def camera_distance(self):
        """Furthest distance recorded so far (where the camera was at the last observation)."""
        return max((obs.distance for obs in self.observations), default=0.0)

    @property
    def last_change(self):
        return max([self.timestamp or ""] + [obs.timestamp or "" for obs in self.observations])


def find_inspection_databases(folder):
    """WinCan inspection databases in <folder>/DB (the _Meta database is skipped)."""
    db_folder = os.path.join(folder, "DB")
    if not os.path.isdir(db_folder):
        return []
    return [
        os.path.join(db_folder, name)
        for name in os.listdir(db_folder)
        if name.lower().endswith(".db3") and not name.endswith(META_SUFFIX)
    ]


def find_active_database(root):
    """
    The WinCan database written most recently below root.

    root may be the folder with all WinCan projects (e.g. D:\\TV-rapporter)
    or a single project folder (one that contains DB).
    """
    if not root or not os.path.isdir(root):
        return None
    candidates = find_inspection_databases(root)
    if not candidates:
        for entry in os.scandir(root):
            if entry.is_dir():
                candidates.extend(find_inspection_databases(entry.path))
    candidates = [path for path in candidates if os.path.isfile(path)]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def file_signature(path):
    """(mtime, size) of a file, or None if it does not exist."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _journal_present(db_path):
    return os.path.exists(db_path + "-journal") or os.path.exists(db_path + "-wal")


def read_database(db_path) -> List[Inspection]:
    """
    Read all inspections from a WinCan database without touching the live file.

    Raises:
        SnapshotBusy: if WinCan was writing; try again later
        OSError: if the file cannot be read
    """
    if _journal_present(db_path):
        raise SnapshotBusy()
    before = file_signature(db_path)

    handle, copy_path = tempfile.mkstemp(suffix=".db3", prefix="riogis_wincan_")
    os.close(handle)
    try:
        shutil.copyfile(db_path, copy_path)
        if _journal_present(db_path) or file_signature(db_path) != before:
            raise SnapshotBusy()
        try:
            return read_copy(copy_path)
        except sqlite3.DatabaseError as error:
            # a torn copy looks like a corrupt database; treat it as busy
            raise SnapshotBusy() from error
    finally:
        try:
            os.remove(copy_path)
        except OSError:
            pass


def _key(value):
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.lower() == "null" else text


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _columns(con, table):
    return {row[1] for row in con.execute(f'pragma table_info("{table}")')}


def _not_deleted(con, table, column, alias):
    return f"{alias}.{column} IS NULL" if column in _columns(con, table) else "1=1"


def read_copy(path) -> List[Inspection]:
    """Read inspections from a (copied) WinCan database, read-only."""
    uri = "file:{}?mode=ro".format(path.replace("\\", "/"))
    con = sqlite3.connect(uri, uri=True)
    try:
        return _read(con)
    finally:
        con.close()


def _read(con):
    inspections = {}
    query = f"""
        SELECT i.INS_PK, s.OBJ_Key, fn.OBJ_Key, tn.OBJ_Key, s.OBJ_Length, s.OBJ_SectionType,
               i.INS_InspectedLength, i.INS_StartDate, i.INS_TimeStamp
        FROM SECINSP i
        JOIN SECTION s ON i.INS_Section_FK = s.OBJ_PK
        LEFT JOIN NODE fn ON s.OBJ_FromNode_REF = fn.OBJ_PK
        LEFT JOIN NODE tn ON s.OBJ_ToNode_REF = tn.OBJ_PK
        WHERE {_not_deleted(con, 'SECINSP', 'INS_Deleted', 'i')}
          AND {_not_deleted(con, 'SECTION', 'OBJ_Deleted', 's')}
        ORDER BY i.INS_StartDate
    """
    for row in con.execute(query):
        inspection = Inspection(
            pk=row[0],
            lsid=_key(row[1]),
            from_psid=_key(row[2]),
            to_psid=_key(row[3]),
            section_length=_float(row[4]),
            section_type=_key(row[5]),
            inspected_length=_float(row[6]),
            start_time=row[7] or "",
            timestamp=row[8] or "",
        )
        inspections[inspection.pk] = inspection

    media = {}
    if "SECOBSMM" in {r[0] for r in con.execute("select name from sqlite_master where type='table'")}:
        media_query = f"""
            SELECT m.OMM_Observation_FK, m.OMM_FileName FROM SECOBSMM m
            WHERE {_not_deleted(con, 'SECOBSMM', 'OMM_Deleted', 'm')} AND m.OMM_FileName IS NOT NULL
            ORDER BY m.OMM_SortOrder
        """
        for observation_pk, filename in con.execute(media_query):
            media.setdefault(observation_pk, []).append(filename)

    observation_query = f"""
        SELECT o.OBS_PK, o.OBS_Inspection_FK, o.OBS_Distance, o.OBS_OpCode, o.OBS_Observation,
               o.OBS_GradeS, o.OBS_ClockPos1, o.OBS_CD_Code1, o.OBS_CD_Code2, o.OBS_Memo,
               o.OBS_TimeStamp, o.OBS_SortOrder
        FROM SECOBS o
        WHERE {_not_deleted(con, 'SECOBS', 'OBS_Deleted', 'o')}
        ORDER BY o.OBS_Distance, o.OBS_SortOrder
    """
    for row in con.execute(observation_query):
        inspection = inspections.get(row[1])
        if inspection is None:
            continue
        inspection.observations.append(Observation(
            pk=row[0],
            distance=_float(row[2]),
            opcode=(row[3] or "").strip(),
            text=row[4] or "",
            grade_s=_int(row[5]),
            clock=_int(row[6]),
            cd_code1=_int(row[7]),
            cd_code2=_int(row[8]),
            memo=row[9] or "",
            timestamp=row[10] or "",
            sort_order=_int(row[11]) or 0,
            media=media.get(row[0], []),
        ))

    return list(inspections.values())
