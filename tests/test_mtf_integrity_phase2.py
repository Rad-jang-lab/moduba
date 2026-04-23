import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mtf_integrity import evaluate_mtf_integrity


def _phase1_result(freq, mtf):
    return {
        "calculation_status": "pass",
        "mtf_curve": {"frequency_cy_per_pixel": freq, "mtf": mtf},
        "mtf50": 0.2,
        "mtf10": 0.4,
        "edge_angle_deg": 5.0,
    }


def test_integrity_pass_when_curve_is_clean_and_snr_good():
    freq = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    mtf = [1.0, 0.8, 0.6, 0.4, 0.2, 0.1]
    res = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=35, clipping_detected=False)

    assert res["integrity_status"] == "pass"
    assert res["warnings"] == []
    assert res["questionable_result"] is False
    assert res["edge_snr_status"] == "ok"


def test_flags_peak_gt_one_and_possible_sharpening():
    freq = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    mtf = [1.08, 1.1, 0.9, 0.6, 0.3, 0.15]
    res = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=35)

    assert res["integrity_status"] == "warning"
    assert "MTF_PEAK_GT_ONE" in res["reason_codes"]
    assert "POSSIBLE_SHARPENING" in res["reason_codes"]


def test_flags_nonmonotonic_tail_behavior():
    freq = [0.0, 0.08, 0.16, 0.24, 0.32, 0.4, 0.45, 0.5]
    mtf = [1.0, 0.86, 0.68, 0.52, 0.34, 0.2, 0.27, 0.22]
    res = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=35)

    assert res["tail_behavior_status"] == "nonmonotonic"
    assert "NONMONOTONIC_TAIL" in res["reason_codes"]
    assert "POSSIBLE_ALIASING" in res["reason_codes"]


def test_snr_policy_low_and_borderline_and_not_assessed():
    freq = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    mtf = [1.0, 0.8, 0.6, 0.4, 0.2, 0.1]

    low = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=15)
    assert low["edge_snr_status"] == "low"
    assert "EDGE_SNR_LOW" in low["reason_codes"]

    borderline = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=25)
    assert borderline["edge_snr_status"] == "borderline"
    assert "EDGE_SNR_BORDERLINE" in borderline["reason_codes"]

    not_assessed = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=None)
    assert not_assessed["edge_snr_status"] == "not_assessed"
    assert "EDGE_SNR_NOT_ASSESSED" in not_assessed["reason_codes"]


def test_questionable_result_when_multiple_anomalies_trigger():
    freq = [0.0, 0.08, 0.16, 0.24, 0.32, 0.4, 0.45, 0.5]
    mtf = [1.1, 1.07, 0.75, 0.5, 0.35, 0.25, 0.31, 0.28]

    res = evaluate_mtf_integrity(_phase1_result(freq, mtf), edge_snr=18, clipping_detected=True)
    assert res["questionable_result"] is True
    assert "RESULT_QUESTIONABLE" in res["reason_codes"]
    assert "EDGE_CLIPPING_DETECTED" in res["reason_codes"]
