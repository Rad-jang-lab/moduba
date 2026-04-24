import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mtf_iec_reporting import evaluate_iec_reporting


def _base_inputs():
    return {
        "iec_reporting_requested": True,
        "calculation_status": "pass",
        "calculation_validity": True,
        "qa_grade": "A",
        "linearity_status": "raw",
        "edge_angle_deg": 5.0,
        "angle_to_nearest_axis_deg": 5.0,
        "roi_size_mm": {"width_mm": 60.0, "height_mm": 120.0},
        "pixel_spacing_available": True,
        "imaging_mode": "general_radiography",
        "operating_mode": "standard",
        "averaging_method": "esf",
        "reason_codes": ["EDGE_SNR_NOT_ASSESSED"],
    }


def test_compliant_when_all_required_conditions_verified():
    res = evaluate_iec_reporting(_base_inputs())
    assert res["iec_reporting_status"] == "compliant"
    assert res["iec_scope_declaration"] == "general_radiography_only"
    assert res["iec_nonconformities"] == []
    assert res["iec_unverifiable_items"] == []


def test_noncompliant_when_roi_below_minimum():
    payload = _base_inputs()
    payload["roi_size_mm"] = {"width_mm": 40.0, "height_mm": 80.0}

    res = evaluate_iec_reporting(payload)
    assert res["iec_reporting_status"] == "noncompliant"
    assert "IEC_ROI_NONCOMPLIANT" in res["inherited_reason_codes"]


def test_unverifiable_when_pixel_spacing_missing_and_roi_unavailable():
    payload = _base_inputs()
    payload["roi_size_mm"] = None
    payload["pixel_spacing_available"] = False

    res = evaluate_iec_reporting(payload)
    assert res["iec_reporting_status"] == "unverifiable"
    assert "IEC_ROI_UNVERIFIABLE" in res["inherited_reason_codes"]


def test_noncompliant_for_invalid_linearity():
    payload = _base_inputs()
    payload["linearity_status"] = "display_transformed"

    res = evaluate_iec_reporting(payload)
    assert res["iec_reporting_status"] == "noncompliant"
    assert "IEC_DATA_NOT_LINEAR" in res["inherited_reason_codes"]


def test_noncompliant_for_non_esf_averaging():
    payload = _base_inputs()
    payload["averaging_method"] = "lsf_average"

    res = evaluate_iec_reporting(payload)
    assert res["iec_reporting_status"] == "noncompliant"
    assert "IEC_AVERAGING_METHOD_NONCOMPLIANT" in res["inherited_reason_codes"]


def test_exploratory_mode_not_reported_as_compliant():
    payload = _base_inputs()
    payload["operating_mode"] = "exploratory_mode"

    res = evaluate_iec_reporting(payload)
    assert res["iec_reporting_status"] in {"noncompliant", "unverifiable"}
    assert "IEC_EXPLORATORY_MODE_NOT_REPORTABLE" in res["inherited_reason_codes"]


def test_not_applicable_when_iec_not_requested():
    payload = _base_inputs()
    payload["iec_reporting_requested"] = False

    res = evaluate_iec_reporting(payload)
    assert res["iec_reporting_status"] == "not_applicable"
