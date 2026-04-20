from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image


class ImagePipeline:
    @staticmethod
    def frame_to_display_image(
        dataset: Any,
        frame: np.ndarray,
        window_width: float | None,
        window_level: float | None,
        scale: float,
        invert_display: bool = False,
    ) -> Image.Image:
        normalized = ImagePipeline.normalize_frame_for_dataset(
            dataset=dataset,
            frame=frame,
            window_width=window_width,
            window_level=window_level,
        )
        if invert_display:
            normalized = 255 - normalized
        image = Image.fromarray(normalized)
        return ImagePipeline.resize_image_for_display(image, scale)

    @staticmethod
    def normalize_frame_for_dataset(
        dataset: Any,
        frame: np.ndarray,
        window_width: float | None,
        window_level: float | None,
    ) -> np.ndarray:
        array = np.asarray(frame, dtype=np.float32)
        if array.ndim == 2:
            array = ImagePipeline.apply_window_level_to_array(array, window_width, window_level)
            array = ImagePipeline.scale_to_uint8(array)
            return ImagePipeline.apply_photometric_interpretation(array, dataset)

        if array.ndim == 3 and array.shape[-1] == 3:
            channels = [ImagePipeline.scale_to_uint8(array[..., index]) for index in range(3)]
            return np.stack(channels, axis=-1)

        raise ValueError(f"지원하지 않는 프레임 형식입니다: {array.shape}")

    @staticmethod
    def apply_photometric_interpretation(array: np.ndarray, dataset: Any) -> np.ndarray:
        photometric = str(getattr(dataset, "PhotometricInterpretation", "")).upper()
        if photometric == "MONOCHROME1":
            # MONOCHROME1 means lower values should appear brighter, so invert after
            # window/level clipping and 8-bit scaling.
            return 255 - array
        return array

    @staticmethod
    def apply_window_level_to_array(
        array: np.ndarray,
        window_width: float | None,
        window_level: float | None,
    ) -> np.ndarray:
        if window_level is None or window_width is None:
            return array
        center = float(window_level)
        width = float(window_width)
        if width <= 1:
            width = 1.0

        lower = center - width / 2.0
        upper = center + width / 2.0
        return np.clip(array, lower, upper)

    @staticmethod
    def scale_to_uint8(array: np.ndarray) -> np.ndarray:
        minimum = float(np.min(array))
        maximum = float(np.max(array))
        if maximum == minimum:
            return np.zeros(array.shape, dtype=np.uint8)
        scaled = (array - minimum) / (maximum - minimum)
        return np.clip(scaled * 255.0, 0, 255).astype(np.uint8)

    @staticmethod
    def resize_image_for_display(image: Image.Image, scale: float) -> Image.Image:
        if scale == 1.0:
            return image

        width, height = image.size
        resized_width = max(int(round(width * scale)), 1)
        resized_height = max(int(round(height * scale)), 1)
        if scale < 1.0:
            resample = Image.Resampling.LANCZOS
        else:
            resample = Image.Resampling.BICUBIC
        return image.resize((resized_width, resized_height), resample)
