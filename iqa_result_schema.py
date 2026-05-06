from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class IQAMetrics:
    mse: float
    rmse: float
    psnr: float
    ssim: float
    hist_corr: float


@dataclass(frozen=True)
class IQAContext:
    input_mode: str
    scope: str
    image_shape: tuple[int, ...]
    data_range_policy: str
    data_range_used: float
    bits_stored: int | None = None
    histogram_bins: int = 256
    histogram_range: tuple[float, float] | None = None
    histogram: dict[str, Any] = field(default_factory=dict)
    ssim_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IQAResult:
    metrics: IQAMetrics
    context: IQAContext
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(asdict(self))


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return to_jsonable(value.tolist())
    return value
