from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


_GENERAL_SCOPE = "general_radiography_only"
_MAMMO_SCOPE = "mammography_only"
_PARTIAL_SCOPE = "partial_iec_reporting_only"
_NOT_DECLARED = "not_declared"


def evaluate_iec_reporting(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """Phase-4 IEC reporting suitability assessment.

    This function only classifies reporting status from upstream evidence and
    never recomputes MTF, QA grading, or anomaly detection.
    """

    iec_requested = bool(inputs.get("iec_reporting_requested", True))
    inherited_codes = _ordered_unique(_to_list(inputs.get("reason_codes")))

    scope = _declare_scope(inputs.get("imaging_mode"), inputs.get("iec_scope_declaration"))

    notes: List[str] = [
        "IEC reporting classification is separate from calculation validity and internal QA grade.",
        "Missing evidence is not treated as evidence of compliance.",
        "Phase 4 does not recompute MTF.",
    ]

    if not iec_requested:
        return _build_result(
            status="not_applicable",
            scope=scope,
            summary="IEC-style external reporting was not requested.",
            nonconformities=[],
            unverifiable_items=[],
            notes=notes,
            disclosures=_build_disclosures(scope, inputs),
            inherited_codes=inherited_codes,
        )

    nonconformities: List[str] = []
    unverifiable: List[str] = []
    new_codes: List[str] = []

    if scope == _NOT_DECLARED:
        unverifiable.append("IEC scope is not declared; required scope-specific conditions cannot be fully verified.")
        new_codes.append("IEC_SCOPE_NOT_DECLARED")

    _check_data_linearity(inputs, nonconformities, unverifiable, new_codes)
    _check_roi(scope, inputs, nonconformities, unverifiable, new_codes)
    _check_edge_geometry(inputs, nonconformities, unverifiable, new_codes)
    _check_averaging(inputs, nonconformities, unverifiable, new_codes)
    _check_exploratory_mode(inputs, nonconformities, unverifiable, new_codes)

    if nonconformities:
        status = "noncompliant"
        summary = "IEC-style reporting is noncompliant due to one or more known requirement violations."
    elif unverifiable:
        status = "unverifiable"
        summary = "IEC-style reporting is unverifiable because one or more required conditions are not confirmed."
    else:
        if scope in (_GENERAL_SCOPE, _MAMMO_SCOPE):
            status = "compliant"
            summary = "IEC-style reporting conditions are positively verified for the declared scope."
        else:
            status = "unverifiable"
            summary = "IEC-style reporting remains unverifiable without a declared reportable IEC scope."
            new_codes.append("IEC_SCOPE_NOT_DECLARED")

    return _build_result(
        status=status,
        scope=scope,
        summary=summary,
        nonconformities=nonconformities,
        unverifiable_items=unverifiable,
        notes=notes,
        disclosures=_build_disclosures(scope, inputs),
        inherited_codes=_ordered_unique(inherited_codes + new_codes),
    )


def _check_data_linearity(
    inputs: Dict[str, Any],
    nonconformities: List[str],
    unverifiable: List[str],
    codes: List[str],
) -> None:
    linearity = str(inputs.get("linearity_status", "unknown")).lower()
    if linearity in {"raw", "original", "linear", "verified_linearized"}:
        return
    if linearity in {"invalid", "nonlinear", "display_transformed"}:
        nonconformities.append("Image data are not linear/raw for IEC-style interpretation.")
        codes.append("IEC_DATA_NOT_LINEAR")
        return
    unverifiable.append("Linearity/raw-data suitability cannot be verified from available metadata.")


def _check_roi(
    scope: str,
    inputs: Dict[str, Any],
    nonconformities: List[str],
    unverifiable: List[str],
    codes: List[str],
) -> None:
    if scope not in (_GENERAL_SCOPE, _MAMMO_SCOPE):
        return

    roi = inputs.get("roi_size_mm") or {}
    width = roi.get("width_mm") if isinstance(roi, dict) else None
    height = roi.get("height_mm") if isinstance(roi, dict) else None

    if width is None or height is None:
        if not bool(inputs.get("pixel_spacing_available", False)):
            unverifiable.append("ROI size in mm cannot be verified because Pixel Spacing is unavailable.")
            codes.append("IEC_ROI_UNVERIFIABLE")
        else:
            unverifiable.append("ROI size in mm is missing and cannot be verified.")
            codes.append("IEC_ROI_UNVERIFIABLE")
        return

    width = float(width)
    height = float(height)

    min_w, min_h = (50.0, 100.0) if scope == _GENERAL_SCOPE else (25.0, 50.0)
    if width < min_w or height < min_h:
        nonconformities.append(
            f"ROI size {width:.1f} mm x {height:.1f} mm is below IEC minimum {min_w:.1f} mm x {min_h:.1f} mm."
        )
        codes.append("IEC_ROI_NONCOMPLIANT")


def _check_edge_geometry(
    inputs: Dict[str, Any],
    nonconformities: List[str],
    unverifiable: List[str],
    codes: List[str],
) -> None:
    calc_status = str(inputs.get("calculation_status", "")).lower()
    calc_validity = inputs.get("calculation_validity")
    if calc_status != "pass" or calc_validity is False:
        nonconformities.append("Upstream edge geometry/calculation validity is not acceptable for IEC reporting.")
        codes.append("IEC_EDGE_GEOMETRY_NONCOMPLIANT")
        return

    angle_from_axis = inputs.get("angle_to_nearest_axis_deg")
    if angle_from_axis is None:
        edge_angle = inputs.get("edge_angle_deg")
        if edge_angle is None:
            unverifiable.append("Edge geometry angle-to-axis cannot be verified for IEC reporting.")
            return
        mod = float(edge_angle) % 90.0
        angle_from_axis = min(mod, 90.0 - mod)

    if float(angle_from_axis) < 2.0:
        nonconformities.append("Edge angle is below acceptable slanted-edge geometry threshold for IEC-style reporting.")
        codes.append("IEC_EDGE_GEOMETRY_NONCOMPLIANT")


def _check_averaging(
    inputs: Dict[str, Any],
    nonconformities: List[str],
    unverifiable: List[str],
    codes: List[str],
) -> None:
    method = inputs.get("averaging_method")
    if method is None:
        unverifiable.append("Averaging method is unknown; IEC-style compliance cannot be confirmed.")
        codes.append("IEC_AVERAGING_METHOD_UNVERIFIABLE")
        return

    m = str(method).strip().lower()
    if m in {"none", "esf", "esf_averaging", "esf_average"}:
        return

    nonconformities.append("Averaging method is not IEC-reportable; only ESF averaging is acceptable.")
    codes.append("IEC_AVERAGING_METHOD_NONCOMPLIANT")


def _check_exploratory_mode(
    inputs: Dict[str, Any],
    nonconformities: List[str],
    unverifiable: List[str],
    codes: List[str],
) -> None:
    mode = str(inputs.get("operating_mode", "")).lower()
    if mode != "exploratory_mode":
        return

    if nonconformities:
        nonconformities.append("Exploratory mode result is not reportable as IEC-compliant.")
        codes.append("IEC_EXPLORATORY_MODE_NOT_REPORTABLE")
    else:
        unverifiable.append("Exploratory mode used; do not claim IEC compliance without fully verified required conditions.")
        codes.append("IEC_EXPLORATORY_MODE_NOT_REPORTABLE")


def _declare_scope(imaging_mode: Any, explicit_scope: Any) -> str:
    if explicit_scope in {_GENERAL_SCOPE, _MAMMO_SCOPE, _PARTIAL_SCOPE, _NOT_DECLARED}:
        return str(explicit_scope)
    mode = str(imaging_mode or "").lower()
    if mode in {"general_radiography", "dr", "general_dr"}:
        return _GENERAL_SCOPE
    if mode in {"mammography", "mg"}:
        return _MAMMO_SCOPE
    return _NOT_DECLARED


def _build_disclosures(scope: str, inputs: Dict[str, Any]) -> List[str]:
    disclosures = [
        "For general DR edge testing, reference device: 1.0 mm tungsten plate, purity > 90%, 100 mm × 75 mm.",
        "IEC general DR ROI reference: 50 mm × 100 mm.",
        "IEC mammography ROI reference: 25 mm × 50 mm.",
    ]
    if scope == _GENERAL_SCOPE:
        disclosures.append("For general DR, focus-to-detector distance of at least 1.50 m is recommended.")

    beam = inputs.get("beam_quality") or inputs.get("target_filter_beam_quality")
    if beam:
        disclosures.append(f"Beam quality/target-filter setting used: {beam} (nonstandard settings must be explicitly disclosed).")
    else:
        disclosures.append("Target/filter/beam quality metadata were not provided; do not imply full IEC equivalence.")
    return disclosures


def _build_result(
    status: str,
    scope: str,
    summary: str,
    nonconformities: Sequence[str],
    unverifiable_items: Sequence[str],
    notes: Sequence[str],
    disclosures: Sequence[str],
    inherited_codes: Sequence[str],
) -> Dict[str, Any]:
    return {
        "iec_reporting_status": status,
        "iec_scope_declaration": scope,
        "iec_reporting_summary": summary,
        "iec_nonconformities": list(nonconformities),
        "iec_unverifiable_items": list(unverifiable_items),
        "iec_notes": list(notes),
        "iec_required_disclosures": list(disclosures),
        "inherited_reason_codes": _ordered_unique(list(inherited_codes)),
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
