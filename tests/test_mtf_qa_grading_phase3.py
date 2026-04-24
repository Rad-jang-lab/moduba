import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mtf_qa_grading import grade_mtf_for_internal_qa


def _phase1_pass():
    return {
        "calculation_status": "pass",
        "rejection_reason": None,
        "mtf50": 0.2,
        "mtf10": 0.4,
    }


def _phase2_base():
    return {
        "integrity_status": "pass",
        "warnings": [],
        "reason_codes": [],
        "questionable_result": False,
        "tail_behavior_status": "stable",
        "edge_snr_status": "ok",
        "clipping_interpretation_status": "not_detected",
    }


def test_grade_a_clean_result():
    res = grade_mtf_for_internal_qa(_phase1_pass(), _phase2_base())
    assert res["qa_grade"] == "A"
    assert res["downstream_ready"] is True


def test_grade_b_minor_warning_only():
    p2 = _phase2_base()
    p2["integrity_status"] = "warning"
    p2["warnings"] = ["MTF peak exceeds 1.0: possible sharpening or edge-enhancement detected."]
    p2["reason_codes"] = ["MTF_PEAK_GT_ONE", "POSSIBLE_SHARPENING"]

    res = grade_mtf_for_internal_qa(_phase1_pass(), p2)
    assert res["qa_grade"] == "B"


def test_grade_c_questionable_or_major_risk():
    p2 = _phase2_base()
    p2["integrity_status"] = "warning"
    p2["questionable_result"] = True
    p2["reason_codes"] = ["RESULT_QUESTIONABLE", "NONMONOTONIC_TAIL"]

    res = grade_mtf_for_internal_qa(_phase1_pass(), p2)
    assert res["qa_grade"] == "C"


def test_grade_d_when_phase1_rejected():
    p1 = {
        "calculation_status": "reject",
        "rejection_reason": "MTF calculation rejected: no usable slanted edge was detected in the ROI.",
    }
    res = grade_mtf_for_internal_qa(p1, _phase2_base())
    assert res["qa_grade"] == "D"


def test_grade_d_when_integrity_is_severely_blocked():
    p2 = _phase2_base()
    p2["integrity_status"] = "warning"
    p2["questionable_result"] = True
    p2["reason_codes"] = ["RESULT_QUESTIONABLE", "NONMONOTONIC_TAIL", "EDGE_SNR_LOW", "EDGE_CLIPPING_DETECTED"]
    p2["warnings"] = ["w1", "w2"]

    res = grade_mtf_for_internal_qa(_phase1_pass(), p2)
    assert res["qa_grade"] == "D"
