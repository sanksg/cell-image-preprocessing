import math
from typing import Any, Dict, Optional, Union

import cv2
import numpy as np


DEFAULT_PREPROCESSING_CONFIG: Dict[str, Any] = {
    "lower_percentile": 1.0,
    "upper_percentile": 99.8,
    "background_blur_fraction": 0.02,
    "apply_background_subtraction": True,
    "output_dtype": "uint16",
}


def _ensure_2d_grayscale(
    image: np.ndarray,
    channel: Optional[Union[int, str]] = None,
) -> np.ndarray:
    """Convert image to 2D grayscale.

    Args:
        image: Input array (2D, HWC, or CHW).
        channel: Which channel to extract from a multi-channel image instead of
            converting to grayscale.  Accepts an integer index (0=R, 1=G, 2=B)
            or a string shorthand: ``"r"``, ``"g"``, ``"b"``, ``"gray"``
            (``"gray"`` is the default weighted-average behaviour).
            Ignored for already-2D inputs.
    """
    image = np.asarray(image)
    if image.ndim == 2:
        return image
    if image.ndim == 3:
        # Normalise HWC vs CHW
        if image.shape[0] in (3, 4) and image.shape[-1] not in (3, 4):
            image = np.moveaxis(image, 0, -1)  # → HWC
        # Now image is HWC
        n_ch = image.shape[-1]
        if channel is not None and channel != "gray":
            if isinstance(channel, str):
                channel = {"r": 0, "g": 1, "b": 2}[channel.lower()]
            if not (0 <= channel < n_ch):
                raise ValueError(f"channel={channel} out of range for image with {n_ch} channels")
            return image[:, :, channel].astype(np.float32)
        # Default: weighted grayscale
        if n_ch in (3, 4):
            return cv2.cvtColor(image[:, :, :3], cv2.COLOR_RGB2GRAY)
    raise ValueError(f"Expected a 2D grayscale or RGB-like image, got shape {image.shape}")


def _sanitize_float_image(image: np.ndarray) -> np.ndarray:
    image = np.asarray(image, dtype=np.float32)
    image = np.nan_to_num(image, nan=0.0, posinf=0.0, neginf=0.0)
    image[image < 0] = 0.0
    return image


def _compute_background_sigma(image: np.ndarray, blur_fraction: float) -> float:
    min_dim = min(image.shape[:2])
    sigma = max(4.0, float(min_dim) * blur_fraction)
    return sigma


def _subtract_smooth_background(image: np.ndarray, blur_fraction: float) -> np.ndarray:
    sigma = _compute_background_sigma(image, blur_fraction)
    background = cv2.GaussianBlur(image, ksize=(0, 0), sigmaX=sigma, sigmaY=sigma)
    corrected = image - background
    corrected[corrected < 0] = 0.0
    return corrected


def _robust_rescale(image: np.ndarray, lower_percentile: float, upper_percentile: float) -> np.ndarray:
    nonzero = image[image > 0]
    source = nonzero if nonzero.size > 0 else image.reshape(-1)
    lower = float(np.percentile(source, lower_percentile))
    upper = float(np.percentile(source, upper_percentile))

    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        max_val = float(np.max(image))
        if max_val <= 0:
            return np.zeros_like(image, dtype=np.float32)
        return image / max_val

    clipped = np.clip(image, lower, upper)
    return (clipped - lower) / (upper - lower)


def _to_output_dtype(image: np.ndarray, output_dtype: str) -> np.ndarray:
    image = np.clip(image, 0.0, 1.0)
    if output_dtype == "uint8":
        return np.round(image * 255.0).astype(np.uint8)
    if output_dtype == "uint16":
        return np.round(image * 65535.0).astype(np.uint16)
    raise ValueError(f"Unsupported output dtype: {output_dtype}")


def preprocess_shared_clean_baseline(
    image: np.ndarray,
    config: Optional[Dict[str, Any]] = None,
    channel: Optional[Union[int, str]] = None,
) -> np.ndarray:
    """
    Apply the universal, model-agnostic preprocessing steps for the shared cleaned baseline.

    Args:
        image: Input image.  Accepts 2D grayscale, RGB/RGBA ``(H, W, C)``, or
            channel-first ``(C, H, W)`` arrays of any numeric dtype.
        config: Optional parameter overrides (see ``DEFAULT_PREPROCESSING_CONFIG``).
        channel: For multi-channel inputs, extract this channel instead of
            computing a weighted grayscale.  Accepts an integer index
            (``0``=R, ``1``=G, ``2``=B) or a string shorthand
            (``"r"``, ``"g"``, ``"b"``, ``"gray"``).
            Useful for live/dead assays where each dye occupies a separate
            channel and must be preprocessed independently.

    Returns:
        2D ``uint16`` (or ``uint8``) array ready for Cellpose input.
    """
    cfg = dict(DEFAULT_PREPROCESSING_CONFIG)
    if config:
        cfg.update(config)

    gray = _ensure_2d_grayscale(image, channel=channel)
    sanitized = _sanitize_float_image(gray)

    if cfg["apply_background_subtraction"]:
        sanitized = _subtract_smooth_background(sanitized, cfg["background_blur_fraction"])

    scaled = _robust_rescale(sanitized, cfg["lower_percentile"], cfg["upper_percentile"])
    return _to_output_dtype(scaled, cfg["output_dtype"])
