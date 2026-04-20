# shared_preprocessing.py — Usage Guide

## Purpose

`shared_preprocessing.py` provides a single, model-agnostic preprocessing function for fluorescence microscopy images. It converts raw input images into a normalized grayscale format suitable for Cellpose (and other segmentation models) by removing uneven illumination and stretching contrast based on actual signal pixels.

---

## Installation / Dependencies

```
numpy
opencv-python   (cv2)
```

No CLI entrypoint — import and call the function directly.

---

## API

### `preprocess_shared_clean_baseline(image, config=None, channel=None)`

**Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `image` | `np.ndarray` | Input image. Accepts 2D grayscale `(H, W)`, RGB `(H, W, 3)`, RGBA `(H, W, 4)`, or channel-first `(C, H, W)`. Any integer or float dtype. |
| `config` | `dict \| None` | Optional overrides for processing parameters (see below). |
| `channel` | `int \| str \| None` | Extract a specific channel instead of converting to grayscale. Integer index (`0`=R, `1`=G, `2`=B) or string shorthand: `"r"`, `"g"`, `"b"`, `"gray"`. `None` (default) uses weighted grayscale. Ignored for already-2D inputs. |

**Returns** `np.ndarray` — 2D array, dtype `uint16` by default (shape `(H, W)`).

### Config keys

| Key | Default | Description |
|-----|---------|-------------|
| `lower_percentile` | `1.0` | Lower bound for contrast stretch (computed on non-zero pixels). |
| `upper_percentile` | `99.8` | Upper bound for contrast stretch. Clips outlier bright pixels. |
| `background_blur_fraction` | `0.02` | Gaussian sigma = `max(4, min_dim × fraction)`. Controls the spatial scale of background estimation. |
| `apply_background_subtraction` | `True` | Set to `False` to skip background removal (e.g. already-flat-field images). |
| `output_dtype` | `"uint16"` | Output dtype. `"uint8"` or `"uint16"`. |

---

## Processing Steps (in order)

1. **Channel selection / RGB → grayscale** — If `channel` is specified, extracts that single channel as-is. Otherwise converts to grayscale via weighted average (`0.299R + 0.587G + 0.114B`). Already-2D inputs pass through unchanged.
2. **Sanitize** — casts to `float32`; replaces NaN, ±Inf, and negative values with `0`.
3. **Gaussian background subtraction** — blurs the image with sigma ≈ 2% of the smallest dimension, then subtracts it. Corrects vignetting and uneven illumination. Negative residuals are clamped to 0.
4. **Percentile contrast stretch** — computes the 1st and 99.8th percentile **on non-zero pixels only**, clips to that range, and rescales to `[0, 1]`. This maximises dynamic range while ignoring dark background pixels and bright outliers.
5. **Cast to output dtype** — multiplies by 255 (`uint8`) or 65535 (`uint16`) and rounds.

---

## Usage Examples

### Basic usage

```python
import tifffile
import numpy as np
from shared_preprocessing import preprocess_shared_clean_baseline

raw = tifffile.imread("my_image.tif")          # any shape/dtype
processed = preprocess_shared_clean_baseline(raw)
# → uint16 numpy array, shape (H, W)

tifffile.imwrite("processed.tif", processed)
```

### Custom config

```python
# Skip background subtraction, output uint8
processed = preprocess_shared_clean_baseline(raw, config={
    "apply_background_subtraction": False,
    "output_dtype": "uint8",
})
```

### Single fluorescence channel (e.g. GFP)

```python
# RGB image where green channel carries the signal
processed = preprocess_shared_clean_baseline(rgb_image, channel="g")
# Equivalent using index
processed = preprocess_shared_clean_baseline(rgb_image, channel=1)
```

### Live / dead assay (two-dye fluorescence)

A live/dead assay typically has at least two channels — e.g. calcein AM (green, live cells) and propidium iodide (red, dead cells). Each channel must be preprocessed independently so they can be segmented and thresholded separately.

```python
import tifffile
from cellpose import models
from shared_preprocessing import preprocess_shared_clean_baseline

# Multi-channel TIFF: ch0 = structural/nuclear, ch1 = live (calcein), ch2 = dead (PI)
stack = tifffile.imread("experiment.tif")  # shape (3, H, W) or (H, W, 3)

# 1. Preprocess structural channel → use for Cellpose segmentation (total cells)
structural = preprocess_shared_clean_baseline(stack, channel=0)

# 2. Preprocess each reporter channel independently → use for intensity thresholding
live_channel = preprocess_shared_clean_baseline(stack, channel=1)   # calcein green
dead_channel = preprocess_shared_clean_baseline(stack, channel=2)   # PI red

# 3. Segment total cells from structural channel
model = models.CellposeModel(gpu=True, pretrained_model="cpsam")
masks, _, _ = model.eval(structural, diameter=None, flow_threshold=0.4, cellprob_threshold=0.0)

# 4. Classify each cell by sampling reporter channels inside its mask
n_cells = int(masks.max())
results = []
for cell_id in range(1, n_cells + 1):
    roi = masks == cell_id
    live_intensity = float(live_channel[roi].mean())
    dead_intensity = float(dead_channel[roi].mean())
    # Apply your threshold logic here
    results.append({"cell_id": cell_id, "live": live_intensity, "dead": dead_intensity})
```

### Passing directly to Cellpose

```python
from cellpose import models
from shared_preprocessing import preprocess_shared_clean_baseline

model = models.CellposeModel(gpu=True, pretrained_model="cpsam")
processed = preprocess_shared_clean_baseline(raw)   # uint16 2D array

masks, flows, _ = model.eval(
    processed,
    diameter=None,
    flow_threshold=0.4,
    cellprob_threshold=0.0,
)
```

### Behind a REST API (FastAPI example)

```python
from fastapi import FastAPI, UploadFile
import numpy as np
import tifffile
import io
from shared_preprocessing import preprocess_shared_clean_baseline

app = FastAPI()

@app.post("/preprocess")
async def preprocess(file: UploadFile):
    data = await file.read()
    raw = tifffile.imread(io.BytesIO(data))
    processed = preprocess_shared_clean_baseline(raw)
    buf = io.BytesIO()
    tifffile.imwrite(buf, processed)
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/tiff")
```

---

## Input Compatibility

| Format | Supported |
|--------|-----------|
| 2D grayscale (uint8, uint16, float32) | ✅ |
| RGB JPEG/PNG (H, W, 3) | ✅ |
| RGBA (H, W, 4) | ✅ |
| Channel-first (3, H, W) | ✅ |
| Multi-channel with `channel` specified (any C) | ✅ |
| Multi-channel without `channel` (> 4 channels) | ❌ Raises `ValueError` |
| 3D z-stack | ❌ Process slices individually |

---

## Notes

- **Single-channel fluorescence**: If your signal is in one specific channel (e.g. green GFP in an RGB image), pass `channel="g"` (or `channel=1`). This extracts that channel directly instead of mixing all three via weighted grayscale, preserving the full dynamic range of the signal channel.
- **Live/dead and multi-dye assays**: Call the function once per reporter channel with the appropriate `channel` argument. Do not pass the composite RGB image without specifying a channel — the weighted average will mix signals from different dyes and make thresholding unreliable.
- **Double normalization**: Cellpose internally applies its own 1st–99th percentile normalization. The two normalizations interact: this function's stretch is applied to raw pixel values, Cellpose's is applied to the output. On very faint images this produces strong contrast amplification which improves detection.
- **Background subtraction scale**: The default `blur_fraction=0.02` assumes structures are much smaller than 2% of the image. For very large cells or low-magnification images, increase this value.
