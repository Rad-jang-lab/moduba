from __future__ import annotations

from typing import Any, Dict, List, Sequence


_MAJOR_RISK_CODES = {
    "NONMONOTONIC_TAIL",
    "POSSIBLE_ALIASING",
    "EDGE_SNR_LOW",
    "EDGE_CLIPPING_DETECTED",
    "RESULT_QUESTIONABLE",
}

_MINOR_RISK_CODES = {
    "MTF_PEAK_GT_ONE",
    "POSSIBLE_SHARPENING",
    "EDGE_SNR_BORDERLINE",
    "HIGH_FREQUENCY_NOISE_BIAS_RISK",
}



def grade_mtf_for_internal_qa(
    phase1_result: Dict[str, Any],
    phase2_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Phase-3 internal QA grading from prior-phase outputs.

    This layer must not recalculate MTF or re-run integrity checks.
    """

    calculation_status = str(phase1_result.get("calculation_status", "")).lower()
    rejection_reason = phase1_result.get("rejection_reason")

    integrity_status = str(phase2_result.get("integrity_status", "")).lower()
    warnings = _to_list(phase2_result.get("warnings"))
    reason_codes = _ordered_unique(_to_list(phase2_result.get("reason_codes")))
    questionable_result = bool(phase2_result.get("questionable_result", False))

    if calculation_status != "pass":
        qa_grade = "D"
        qa_status_summary = "Phase 1 calculation rejected; result is not suitable for interpretation."
        qa_reasoning = [
            "Grade D assigned because calculation_status is not pass.",
            f"Rejection reason: {rejection_reason or 'not provided'}",
            "QA grade is an internal trustworthiness judgment and separate from IEC compliance.",
        ]
        return _build_output(qa_grade, qa_status_summary, qa_reasoning, reason_codes)

    major_count = len(_MAJOR_RISK_CODES & set(reason_codes))
    minor_count = len(_MINOR_RISK_CODES & set(reason_codes))

    severe_integrity_block = (
        integrity_status == "warning"
        and questionable_result
        and major_count >= 2
        and ("EDGE_SNR_LOW" in reason_codes or "EDGE_CLIPPING_DETECTED" in reason_codes)
    )

    if severe_integrity_block:
        qa_grade = "D"
        qa_status_summary = "Calculation passed, but integrity findings indicate result is not suitable for practical interpretation."
    elif questionable_result or major_count >= 1:
        qa_grade = "C"
        qa_status_summary = "Calculation passed with substantial interpretation risk; use only with caution."
    elif integrity_status == "warning" or warnings or minor_count >= 1:
        qa_grade = "B"
        qa_status_summary = "Calculation passed with minor interpretation caveats."
    else:
        qa_grade = "A"
        qa_status_summary = "Calculation and integrity findings are technically clean and highly reliable."

    qa_reasoning = [
        "Grade derived from Phase 1 validity and Phase 2 integrity findings only.",
        f"Phase 1 calculation_status={calculation_status}",
        f"Phase 2 integrity_status={integrity_status}, questionable_result={questionable_result}",
        f"Major risk count={major_count}, minor risk count={minor_count}",
        "QA grade is internal and explicitly separate from IEC compliance determination.",
    ]
    if warnings:
        qa_reasoning.append(f"Warnings considered: {len(warnings)}")

    return _build_output(qa_grade, qa_status_summary, qa_reasoning, reason_codes)



def _build_output(
    qa_grade: str,
    qa_status_summary: str,
    qa_reasoning: Sequence[str],
    inherited_reason_codes: Sequence[str],
) -> Dict[str, Any]:
    return {
        "qa_grade": qa_grade,
        "qa_status_summary": qa_status_summary,
        "qa_reasoning": list(qa_reasoning),
        "inherited_reason_codes": list(inherited_reason_codes),
        "downstream_ready": True,
    }



def _to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]



def _ordered_unique(items: Sequence[Any]) -> List[Any]:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
