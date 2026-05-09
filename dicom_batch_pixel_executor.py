from __future__ import annotations

from typing import Any, Callable

SUPPORTED_ANALYSIS_TYPES = {"snr", "cnr", "uniformity", "mtf"}


def load_dicom_pixel_data_for_batch(dicom_path: str, *, pixel_loader: Callable[[str], Any] | None = None) -> dict[str, Any]:
    if not dicom_path:
        raise ValueError("dicom_path is empty")
    if pixel_loader is not None:
        ds = pixel_loader(dicom_path)
    else:
        try:
            import importlib
            pydicom = importlib.import_module("pydicom")
        except Exception as exc:
            raise RuntimeError("pydicom is not available for pixel-backed execution") from exc
        ds = pydicom.dcmread(dicom_path)
    try:
        pixel_array = ds["pixel_array"] if isinstance(ds, dict) and "pixel_array" in ds else ds.pixel_array
    except Exception as exc:
        raise RuntimeError("failed to read DICOM pixel_array") from exc
    meta = {
        "dicom_path": dicom_path,
        "rows": getattr(ds, "Rows", None) if not isinstance(ds, dict) else ds.get("Rows"),
        "columns": getattr(ds, "Columns", None) if not isinstance(ds, dict) else ds.get("Columns"),
        "photometric_interpretation": getattr(ds, "PhotometricInterpretation", None) if not isinstance(ds, dict) else ds.get("PhotometricInterpretation"),
        "bits_allocated": getattr(ds, "BitsAllocated", None) if not isinstance(ds, dict) else ds.get("BitsAllocated"),
        "bits_stored": getattr(ds, "BitsStored", None) if not isinstance(ds, dict) else ds.get("BitsStored"),
        "rescale_slope": getattr(ds, "RescaleSlope", 1) if not isinstance(ds, dict) else ds.get("RescaleSlope", 1),
        "rescale_intercept": getattr(ds, "RescaleIntercept", 0) if not isinstance(ds, dict) else ds.get("RescaleIntercept", 0),
    }
    return {"pixel_array": pixel_array, "metadata": meta}


def build_batch_analysis_context_for_item(item: dict[str, Any], *, pixel_loader: Callable[[str], Any] | None = None, roi_resolver: Callable[..., Any] | None = None) -> dict[str, Any]:
    dicom_path = str(item.get("dicom_path", ""))
    if not dicom_path:
        raise ValueError("dicom_path is required")
    pixel_data = load_dicom_pixel_data_for_batch(dicom_path, pixel_loader=pixel_loader)
    return {"item_id": item.get("item_id"), "dicom_path": dicom_path, "pixel_data": pixel_data, "pixel_array": pixel_data["pixel_array"], "dicom_metadata": dict(pixel_data.get("metadata") or {}), "roi_resolver": roi_resolver, "item_metadata": dict(item.get("metadata") or {})}


def resolve_task_rois_for_pixel_executor(task: dict[str, Any], item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    roi_ids = list(task.get("roi_ids") or [])
    if not roi_ids:
        raise ValueError("task roi_ids is empty")
    return {"roi_ids": roi_ids}


def run_pixel_backed_analysis_task(task: dict[str, Any], item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    analysis_type = str(task.get("analysis_type", "")).strip().lower()
    if analysis_type not in SUPPORTED_ANALYSIS_TYPES:
        raise ValueError(f"unsupported analysis_type: {analysis_type}")
    dispatcher = context.get("analysis_dispatcher")
    if not callable(dispatcher):
        raise RuntimeError("analysis_dispatcher is required")
    roi_payload = resolve_task_rois_for_pixel_executor(task, item, context)
    return dispatcher(dict(task), dict(item), {**dict(context), **roi_payload})


def build_pixel_executor_run_context(execution_plan: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"execution_plan": dict(execution_plan or {}), "metadata": dict(metadata or {}), "dicom_cache": {}}


def create_dicom_batch_pixel_analysis_executor(*, pixel_loader: Callable[[str], Any] | None = None, roi_resolver: Callable[..., Any] | None = None, analysis_dispatcher: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None) -> Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def _executor(task: dict[str, Any], item: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        run_cache = context.setdefault("dicom_cache", {})
        key = str(item.get("dicom_path", ""))
        if key not in run_cache:
            run_cache[key] = build_batch_analysis_context_for_item(item, pixel_loader=pixel_loader, roi_resolver=roi_resolver)
        local_ctx = dict(run_cache[key])
        local_ctx["analysis_dispatcher"] = analysis_dispatcher
        local_ctx["dicom_cache"] = run_cache
        return run_pixel_backed_analysis_task(task, item, local_ctx)
    return _executor
