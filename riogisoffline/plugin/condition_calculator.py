"""
VAV condition calculator for WinCan observations.

A 1:1 port of the FME PythonCaller "ConditionCalculator" used by VAV. The
tables and the rules are kept exactly as in FME, so the plugin gives the same
grade as the FME workflow:

- category = first two characters of the observation code (e.g. "SR3" -> "SR")
- an empty, zero or non-numeric WinCan grade counts as 1
- grade = scoremap[fcode][category][grade], 1 when not found
- if the observation covers >= 50 % of the pipe (percent), the
  linescore_50percent table overrides the grade where it has an entry
"""

OBSERVATIONS = {
    'DF': 'Deformasjon',
    'SR': 'Sprukket rør',
    'KO': 'Korrosjon/Slitasje',
    'PF': 'Produktfeil',
    'IR': 'Innstrukket rør',
    'TF': 'tilkoplingsfeil',
    'DG': 'Defekt gjenåpning av tilkobling',
    'DH': 'Defekt hatteprofil',
    'SP': 'Synlig pakning',
    'FS': 'Forskjøvet skjøt',
    'DO': 'Defekt overgangsdel eller punktreparasjon',
    'RØ': 'Røtter',
    'HI': 'Hindring',
    'IS': 'Innsig',
    'SM': '..',
}

# AF and SP use the same table in FME
_SANITARY = {
    'DF': {1: 1, 2: 1, 3: 2, 4: 3},
    'SR': {1: 1, 2: 2, 3: 3, 4: 4},
    'KO': {1: 1, 2: 2, 3: 2, 4: 4},
    'PF': {1: 1, 2: 2, 3: 3, 4: 4},
    'IR': {1: 1, 2: 2, 3: 3, 4: 4},
    'TF': {1: 1, 2: 2, 3: 3, 4: 3},
    'DG': {1: 2, 2: 2, 3: 3, 4: 3},
    'DH': {1: 1, 2: 2, 3: 3, 4: 3},
    'SP': {1: 1, 2: 2, 3: 3, 4: 3},
    'FS': {1: 1, 2: 2, 3: 3, 4: 4},
    'DO': {1: 2, 2: 2, 3: 3, 4: 4},
    'RØ': {1: 1, 2: 2, 3: 3, 4: 4},
    'HI': {1: 2, 2: 2, 3: 3, 4: 4},
    'IS': {1: 1, 2: 2, 3: 3, 4: 3},
    'SM': {1: 1, 2: 1, 3: 1, 4: 1},
}

SCOREMAP = {
    'SP': _SANITARY,
    'AF': _SANITARY,
    'OV': {
        'DF': {1: 1, 2: 1, 3: 2, 4: 3},
        'SR': {1: 1, 2: 1, 3: 2, 4: 4},
        'KO': {1: 1, 2: 1, 3: 2, 4: 3},
        'PF': {1: 1, 2: 1, 3: 2, 4: 3},
        'IR': {1: 1, 2: 1, 3: 2, 4: 3},
        'TF': {1: 1, 2: 1, 3: 2, 4: 3},
        'DG': {1: 1, 2: 1, 3: 2, 4: 3},
        'DH': {1: 1, 2: 1, 3: 2, 4: 3},
        'SP': {1: 1, 2: 1, 3: 2, 4: 3},
        'FS': {1: 1, 2: 1, 3: 2, 4: 3},
        'DO': {1: 1, 2: 1, 3: 2, 4: 3},
        'RØ': {1: 1, 2: 1, 3: 2, 4: 4},
        'HI': {1: 1, 2: 2, 3: 3, 4: 4},
        'IS': {1: 1, 2: 1, 3: 2, 4: 3},
        'SM': {1: 1, 2: 1, 3: 1, 4: 1},
    },
}

LINESCORE_50PERCENT = {
    'AF': {
        'SR': {2: 3},
        'KO': {2: 2, 3: 3},
        'RØ': {2: 3},
        'SM': {1: 1, 2: 1, 3: 1, 4: 1},
    },
    'SP': {
        'SR': {2: 3},
        'KO': {2: 2, 3: 3},
        'RØ': {2: 3},
        'SM': {1: 1, 2: 1, 3: 1, 4: 1},
    },
    'OV': {
        'SR': {2: 1, 3: 3},
        'RØ': {2: 1, 3: 3},
        'SM': {1: 1, 2: 1, 3: 1, 4: 1},
    },
}

FCODEMAP = {1: 'VL', 2: 'SP', 3: 'AF', 4: 'OV', 5: 'DR'}


def category(opcode):
    return (opcode or "")[:2]


def is_condition_code(opcode):
    """True for damage codes the calculator grades; False for info codes (SI, IF, VN, ANM ...)."""
    return category(opcode) in OBSERVATIONS


def _wincan_grade(grade_s):
    try:
        grade = int(grade_s)
    except (TypeError, ValueError):
        grade = grade_s
    if not grade or grade == '0':
        grade = 1
    return grade


def calculate_grade(fcode, opcode, grade_s, percent=0.0):
    """
    Grade (1-4) of one observation.

    Args:
        fcode (str): pipe type from the map, e.g. "AF", "SP", "OV"
        opcode (str): WinCan observation code, e.g. "SR3"
        grade_s: WinCan grade (OBS_GradeS), may be None
        percent (float): share of the pipe covered by the observation (0-100)
    """
    cat = category(opcode)
    grade = _wincan_grade(grade_s)

    new_grade = SCOREMAP.get(fcode, {}).get(cat, {}).get(grade, 1)

    if int(float(percent or 0)) >= 50:
        override = LINESCORE_50PERCENT.get(fcode, {}).get(cat, {})
        if cat in OBSERVATIONS and grade in override:
            new_grade = override[grade]

    return new_grade
