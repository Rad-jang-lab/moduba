from __future__ import annotations

from typing import Any

import numpy as np
import pydicom
from pydicom import config as pydicom_config
from pydicom.errors import InvalidDicomError


class DicomLoader:
    def __init__(self) -> None:
        self._decoded_cache: dict[str, tuple[pydicom.dataset.FileDataset, list[np.ndarray]]] = {}
        self._load_error_cache: dict[str, str] = {}

    def clear_cache(self) -> None:
        self._decoded_cache = {}
        self._load_error_cache = {}

    def get_decoded_file(self, path: str) -> tuple[pydicom.dataset.FileDataset, list[np.ndarray]]:
        cached = self._decoded_cache.get(path)
        if cached is not None:
            return cached

        cached_error = self._load_error_cache.get(path)
        if cached_error is not None:
            raise ValueError(cached_error)

        try:
            dataset, frames = self.read_dataset_for_display(path)
        except ValueError as exc:
            self._load_error_cache[path] = str(exc)
            raise

        self._decoded_cache[path] = (dataset, frames)
        return dataset, frames

    def read_dataset_for_display(self, path: str) -> tuple[pydicom.dataset.FileDataset, list[np.ndarray]]:
        try:
            dataset = pydicom.dcmread(path)
        except InvalidDicomError as exc:
            raise ValueError("DICOM 형식이 아닌 파일입니다.") from exc
        except Exception as exc:
            raise ValueError("DICOM 파일을 읽지 못했습니다.") from exc

        if "PixelData" not in dataset:
            raise ValueError("Pixel Data가 없는 DICOM 파일입니다.")

        self.ensure_transfer_syntax_supported(dataset, path)

        try:
            frames = self.extract_frames(dataset)
        except NotImplementedError as exc:
            raise ValueError("이 DICOM의 픽셀 형식은 현재 뷰어에서 지원하지 않습니다.") from exc
        except Exception as exc:
            if self.is_probable_decode_error(exc):
                raise ValueError(
                    "압축된 DICOM 픽셀 데이터를 디코딩하지 못했습니다.\n"
                    "Windows Python에 `pylibjpeg`, `pylibjpeg-libjpeg`, "
                    "`pylibjpeg-openjpeg`, `gdcm` 중 필요한 디코더를 설치해 주세요."
                ) from exc
            raise

        if not frames:
            raise ValueError("표시할 프레임이 없습니다.")

        return dataset, frames

    @staticmethod
    def extract_frames(dataset: Any) -> list[np.ndarray]:
        pixel_array = DicomLoader._apply_modality_lut_compat(dataset.pixel_array, dataset)
        pixel_array = np.asarray(pixel_array)

        if pixel_array.ndim == 2:
            return [pixel_array]

        if pixel_array.ndim == 3:
            if getattr(dataset, "SamplesPerPixel", 1) == 3:
                return [pixel_array]
            return [pixel_array[index] for index in range(pixel_array.shape[0])]

        if pixel_array.ndim == 4 and pixel_array.shape[-1] == 3:
            return [pixel_array[index] for index in range(pixel_array.shape[0])]

        raise ValueError(f"지원하지 않는 이미지 차원입니다: {pixel_array.shape}")

    @staticmethod
    def _apply_modality_lut_compat(pixel_array: Any, dataset: Any):
        try:
            from pydicom.pixels import apply_modality_lut as _apply_modality_lut
        except Exception:
            from pydicom.pixel_data_handlers.util import apply_modality_lut as _apply_modality_lut
        return _apply_modality_lut(pixel_array, dataset)

    def ensure_transfer_syntax_supported(self, dataset: Any, _path: str) -> None:
        transfer_syntax = self.get_transfer_syntax(dataset)
        if transfer_syntax is None:
            return
        if self.has_transfer_syntax_handler(transfer_syntax):
            return

        raise ValueError(
            "압축된 DICOM 전송구문을 해제할 수 있는 픽셀 디코더가 없습니다.\n"
            f"Transfer Syntax: {transfer_syntax}\n"
            "Windows Python에 `pylibjpeg`, `pylibjpeg-libjpeg`, "
            "`pylibjpeg-openjpeg`, `gdcm` 중 필요한 디코더를 설치해 주세요."
        )

    @staticmethod
    def is_probable_decode_error(exc: Exception) -> bool:
        text = str(exc).lower()
        keywords = (
            "decoder",
            "decompress",
            "compressed",
            "transfer syntax",
            "pixel data handler",
            "missing required element",
        )
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def get_transfer_syntax(dataset: Any):
        file_meta = getattr(dataset, "file_meta", None)
        return getattr(file_meta, "TransferSyntaxUID", None)

    def has_transfer_syntax_handler(self, transfer_syntax: Any) -> bool:
        if transfer_syntax is None:
            return True

        try:
            is_compressed = bool(transfer_syntax.is_compressed)
        except Exception:
            is_compressed = False

        if not is_compressed:
            return True

        for handler in pydicom_config.pixel_data_handlers:
            try:
                if handler.is_available() and handler.supports_transfer_syntax(transfer_syntax):
                    return True
            except Exception:
                continue
        return False
