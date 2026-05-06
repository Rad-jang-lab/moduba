from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

from iqa_result_schema import IQAContext, IQAMetrics, IQAResult


_VALID_DATA_RANGE_POLICIES = {"bits", "actual_peak", "actual_union", "explicit"}


def _as_float64_pair(reference: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ref = np.asarray(reference)
    tar = np.asarray(target)
    if ref.shape != tar.shape:
        raise ValueError(f"reference/target shape mismatch: reference={ref.shape}, target={tar.shape}")
    return ref.astype(np.float64, copy=False), tar.astype(np.float64, copy=False)


def calculate_mse(reference: np.ndarray, target: np.ndarray) -> float:
    ref, tar = _as_float64_pair(reference, target)
    diff = ref - tar
    return float(np.mean(diff * diff))


def calculate_rmse(reference: np.ndarray, target: np.ndarray) -> float:
    return float(math.sqrt(calculate_mse(reference, target)))


def calculate_psnr(mse: float, data_range: float) -> float:
    mse_value = float(mse)
    data_range_value = float(data_range)
    if mse_value == 0:
        return math.inf
    if mse_value < 0 or data_range_value <= 0:
        return math.nan
    return float(20.0 * math.log10(data_range_value / math.sqrt(mse_value)))


def calculate_histogram_correlation(
    reference: np.ndarray,
    target: np.ndarray,
    bins: int = 256,
    hist_range: tuple[float, float] | None = None,
) -> float:
    ref, tar = _as_float64_pair(reference, target)
    if hist_range is None:
        min_value = float(min(np.min(ref), np.min(tar)))
        max_value = float(max(np.max(ref), np.max(tar)))
        if max_value <= min_value:
            max_value = min_value + 1.0
        hist_range = (min_value, max_value)
    hist_ref, _ = np.histogram(ref, bins=int(bins), range=hist_range, density=False)
    hist_tar, _ = np.histogram(tar, bins=int(bins), range=hist_range, density=False)
    hist_ref = hist_ref.astype(np.float64, copy=False)
    hist_tar = hist_tar.astype(np.float64, copy=False)
    if float(np.std(hist_ref)) == 0.0 or float(np.std(hist_tar)) == 0.0:
        return math.nan
    return float(np.corrcoef(hist_ref, hist_tar)[0, 1])


def calculate_ssim(reference: np.ndarray, target: np.ndarray, data_range: float, **params: Any) -> float:
    ref, tar = _as_float64_pair(reference, target)
    data_range_value = float(data_range)
    if data_range_value <= 0:
        return math.nan
    k1 = float(params.get("k1", 0.01))
    k2 = float(params.get("k2", 0.03))
    c1 = (k1 * data_range_value) ** 2
    c2 = (k2 * data_range_value) ** 2
    mu_x = float(np.mean(ref))
    mu_y = float(np.mean(tar))
    sigma_x = float(np.var(ref))
    sigma_y = float(np.var(tar))
    sigma_xy = float(np.mean((ref - mu_x) * (tar - mu_y)))
    numerator = (2.0 * mu_x * mu_y + c1) * (2.0 * sigma_xy + c2)
    denominator = (mu_x * mu_x + mu_y * mu_y + c1) * (sigma_x + sigma_y + c2)
    if denominator == 0:
        return math.nan
    return float(numerator / denominator)


def resolve_iqa_data_range(
    reference: np.ndarray,
    target: np.ndarray,
    policy: str,
    bits_stored: int | None = None,
    explicit_data_range: float | None = None,
) -> dict[str, Any]:
    ref, tar = _as_float64_pair(reference, target)
    normalized_policy = str(policy or "").strip().lower()
    if normalized_policy not in _VALID_DATA_RANGE_POLICIES:
        raise ValueError(f"unsupported IQA data_range policy: {policy}")

    warnings: list[str] = []
    data_range: float
    if normalized_policy == "bits":
        if bits_stored is None:
            warnings.append("data_range_ambiguous: bits policy requires bits_stored")
            data_range = float(max(np.max(ref), np.max(tar)) - min(np.min(ref), np.min(tar)))
        else:
            data_range = float((2 ** int(bits_stored)) - 1)
    elif normalized_policy == "actual_peak":
        data_range = float(max(np.max(ref), np.max(tar)))
    elif normalized_policy == "actual_union":
        data_range = float(max(np.max(ref), np.max(tar)) - min(np.min(ref), np.min(tar)))
    else:
        if explicit_data_range is None:
            warnings.append("data_range_ambiguous: explicit policy requires explicit_data_range")
            data_range = math.nan
        else:
            data_range = float(explicit_data_range)

    if not math.isfinite(data_range) or data_range <= 0:
        warnings.append("data_range <= 0")
    return {
        "policy": normalized_policy,
        "data_range": float(data_range),
        "bits_stored": None if bits_stored is None else int(bits_stored),
        "warnings": warnings,
    }


def build_iqa_context(
    reference: np.ndarray,
    target: np.ndarray,
    *,
    input_mode: str = "array",
    scope: str = "full_image",
    data_range_policy: str = "actual_union",
    data_range_used: float | None = None,
    bits_stored: int | None = None,
    histogram_bins: int = 256,
    histogram_range: tuple[float, float] | None = None,
    ssim_params: Mapping[str, Any] | None = None,
) -> IQAContext:
    ref, _tar = _as_float64_pair(reference, target)
    return IQAContext(
        input_mode=str(input_mode),
        scope=str(scope),
        image_shape=tuple(int(item) for item in ref.shape),
        data_range_policy=str(data_range_policy),
        data_range_used=float(data_range_used) if data_range_used is not None else math.nan,
        bits_stored=None if bits_stored is None else int(bits_stored),
        histogram_bins=int(histogram_bins),
        histogram_range=None if histogram_range is None else (float(histogram_range[0]), float(histogram_range[1])),
        ssim_params=dict(ssim_params or {}),
    )


def _resolve_options(context: Mapping[str, Any] | IQAContext | None, options: Mapping[str, Any] | None) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    if isinstance(context, IQAContext):
        resolved.update(
            {
                "input_mode": context.input_mode,
                "scope": context.scope,
                "data_range_policy": context.data_range_policy,
                "data_range_used": context.data_range_used,
                "bits_stored": context.bits_stored,
                "histogram_bins": context.histogram_bins,
                "histogram_range": context.histogram_range,
                "ssim_params": context.ssim_params,
            }
        )
    elif context is not None:
        resolved.update(dict(context))
    if options is not None:
        resolved.update(dict(options))
    return resolved


def calculate_iqa_metrics(
    reference: np.ndarray,
    target: np.ndarray,
    context: Mapping[str, Any] | IQAContext | None = None,
    options: Mapping[str, Any] | None = None,
) -> IQAResult:
    ref, tar = _as_float64_pair(reference, target)
    resolved_options = _resolve_options(context, options)
    policy = str(resolved_options.get("data_range_policy", "actual_union"))
    bits_stored = resolved_options.get("bits_stored")
    explicit_data_range = resolved_options.get("data_range_used", resolved_options.get("explicit_data_range"))
    if policy != "explicit" and (explicit_data_range is None or (isinstance(explicit_data_range, float) and math.isnan(explicit_data_range))):
        explicit_data_range = None

    warnings: list[str] = []
    scope = str(resolved_options.get("scope", "full_image"))
    if scope in {"full", "full_image", "Full Image"}:
        warnings.append("full image scope may include background")

    range_resolution = resolve_iqa_data_range(
        ref,
        tar,
        policy,
        bits_stored=None if bits_stored is None else int(bits_stored),
        explicit_data_range=None if explicit_data_range is None else float(explicit_data_range),
    )
    warnings.extend(range_resolution["warnings"])
    data_range = float(range_resolution["data_range"])

    histogram_bins = int(resolved_options.get("histogram_bins", 256))
    histogram_range = resolved_options.get("histogram_range")
    if histogram_range is not None:
        histogram_range = (float(histogram_range[0]), float(histogram_range[1]))
    ssim_params = dict(resolved_options.get("ssim_params") or {})

    mse = calculate_mse(ref, tar)
    rmse = float(math.sqrt(mse))
    psnr = calculate_psnr(mse, data_range)
    ssim = calculate_ssim(ref, tar, data_range, **ssim_params)
    hist_corr = calculate_histogram_correlation(ref, tar, bins=histogram_bins, hist_range=histogram_range)
    if math.isnan(hist_corr):
        warnings.append("constant histogram: correlation unavailable")

    result_context = build_iqa_context(
        ref,
        tar,
        input_mode=str(resolved_options.get("input_mode", "array")),
        scope=scope,
        data_range_policy=str(range_resolution["policy"]),
        data_range_used=data_range,
        bits_stored=range_resolution["bits_stored"],
        histogram_bins=histogram_bins,
        histogram_range=histogram_range,
        ssim_params=ssim_params,
    )
    return IQAResult(
        metrics=IQAMetrics(mse=mse, rmse=rmse, psnr=psnr, ssim=ssim, hist_corr=hist_corr),
        context=result_context,
        warnings=sorted(set(warnings)),
    )
