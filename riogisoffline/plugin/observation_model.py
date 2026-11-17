"""
Turns WinCan observations into what is drawn on the map.

- Continuous (length) observations: OBS_CD_Code2 is 1 at the start and 9 at
  the end. OBS_CD_Code1 is 1xx at the start and 2xx at the end; the last two
  digits pair them (102 <-> 202). A start without an end lasts until the end
  of the inspection, or (while inspecting) until the camera position.
- Direction: the start manhole is only written as free text in the
  "Start inspeksjon" memo ("I kum 396525"). The PSID found there decides the
  direction; without a match the inspection runs from -> to.
- Grade: VAV's condition calculator (condition_calculator.py).

No QGIS imports here.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .condition_calculator import calculate_grade, category, is_condition_code

CD_START = 1
CD_END = 9


@dataclass
class PlacedObservation:
    pk: str
    opcode: str
    text: str
    start: float           # distance from the start manhole (m, WinCan)
    end: Optional[float]   # None for point observations
    is_info: bool
    open: bool = False     # length observation without an end yet
    grade_s: Optional[int] = None
    grade: Optional[int] = None
    percent: float = 0.0
    clock: Optional[int] = None
    timestamp: str = ""
    media: List[str] = field(default_factory=list)

    @property
    def is_line(self):
        return self.end is not None

    @property
    def category(self):
        return category(self.opcode)

    def signature(self):
        return (self.pk, self.opcode, round(self.start, 3),
                None if self.end is None else round(self.end, 3),
                self.open, self.grade, self.is_info)


def parse_start_psid(memo, from_psid, to_psid):
    """PSID of the start manhole written in the SI memo, if it is one of the pipe's ends."""
    candidates = {str(p) for p in (from_psid, to_psid) if p}
    for number in re.findall(r"\d+", memo or ""):
        if number in candidates:
            return number
    return None


def detected_reversed(inspection):
    """True when the SI memo names the pipe's to-manhole as start (inspection runs to -> from)."""
    start = parse_start_psid(inspection.start_memo, inspection.from_psid, inspection.to_psid)
    return (
        start is not None
        and start == str(inspection.to_psid)
        and inspection.from_psid != inspection.to_psid
    )


def is_reversed(inspection, flipped=False):
    """
    True when the inspection runs from the pipe's to-manhole towards its
    from-manhole. flipped is the user's "Snu retning" for this inspection.
    """
    return detected_reversed(inspection) != bool(flipped)


def end_distance(inspection):
    """Where open length observations end: inspection end, or camera position while inspecting."""
    finished = [obs.distance for obs in inspection.observations if obs.opcode == "IF"]
    if finished:
        return max(finished)
    return inspection.camera_distance


def _percent(start, end, reference_length):
    if not reference_length or reference_length <= 0 or end is None:
        return 0.0
    return max(0.0, (end - start) / reference_length * 100.0)


def build_observations(inspection, fcode, reference_length=None) -> List[PlacedObservation]:
    """
    Observations to draw for one inspection.

    Args:
        inspection (wincan_reader.Inspection)
        fcode (str): pipe type from the map (AF, SP, OV ...), used by the calculator
        reference_length (float): pipe length for percent; defaults to the WinCan
            section length
    """
    reference_length = reference_length or inspection.section_length
    open_end = end_distance(inspection)
    finished = inspection.is_finished

    starts, ends, points = {}, {}, []
    for obs in inspection.observations:
        if obs.cd_code2 in (CD_START, CD_END) and obs.cd_code1 is not None:
            pair_id = obs.cd_code1 % 100
            bucket = starts if obs.cd_code2 == CD_START else ends
            bucket.setdefault(pair_id, []).append(obs)
        else:
            points.append(obs)

    result = []

    for pair_id, start_list in starts.items():
        end_list = sorted(ends.get(pair_id, []), key=lambda o: o.distance)
        for start in sorted(start_list, key=lambda o: o.distance):
            # first unused end at or after the start
            end = next((e for e in end_list if e.distance >= start.distance), None)
            if end is not None:
                end_list.remove(end)
            end_at = end.distance if end is not None else max(open_end, start.distance)
            # without an end it lasts to the end of the inspection; it is only
            # "ongoing" (open) while the inspection itself is still running
            is_open = end is None and not finished
            result.append(_placed(start, start.distance, end_at, is_open,
                                  fcode, reference_length, extra_media=end.media if end else []))
        # an end without a start is shown where it is, as a point
        for orphan in end_list:
            points.append(orphan)
    for pair_id, end_list in ends.items():
        if pair_id not in starts:
            points.extend(end_list)

    for obs in points:
        result.append(_placed(obs, obs.distance, None, False, fcode, reference_length))

    result.sort(key=lambda p: (p.start, p.pk))
    return result


def _placed(obs, start, end, is_open, fcode, reference_length, extra_media=()):
    info = not is_condition_code(obs.opcode)
    percent = _percent(start, end, reference_length)
    grade = None if info else calculate_grade(fcode, obs.opcode, obs.grade_s, percent)
    return PlacedObservation(
        pk=obs.pk,
        opcode=obs.opcode,
        text=obs.text,
        start=start,
        end=end,
        is_info=info,
        open=is_open,
        grade_s=obs.grade_s,
        grade=grade,
        percent=round(percent, 1),
        clock=obs.clock,
        timestamp=obs.timestamp,
        media=list(obs.media) + list(extra_media),
    )


def active_inspection(inspections):
    """The inspection being worked on: newest unfinished one, else the newest one."""
    if not inspections:
        return None
    unfinished = [i for i in inspections if not i.is_finished]
    pool = unfinished or inspections
    return max(pool, key=lambda i: i.last_change)
