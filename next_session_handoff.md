# Next Session Handoff

_Last updated: April 21, 2026_

## Purpose

This repository packages the shared fluorescence preprocessing baseline into a small, shareable repo for reuse outside the main `CellCounting` workspace.

Primary repo:
- https://github.com/sanksg/cell-image-preprocessing

Local path:
- `C:/Users/Sankalp/Desktop/projects/cambrian/cell-image-preprocessing`

## What Is In This Repo

- `shared_preprocessing.py`: the reusable preprocessing module
- `README.md`: main usage guide for users of the shared module
- `shared_preprocessing_guide.md`: duplicate guide file kept alongside the code for direct sharing
- `requirements.txt`: minimal dependencies (`numpy`, `opencv-python`)
- `experiments/`: ablation report, summary CSV, and heatmaps that justify the selected baseline

## Current API Surface

Main entrypoint:
- `preprocess_shared_clean_baseline(image, config=None, channel=None)`

Important behavior:
- Accepts 2D grayscale, HWC RGB/RGBA, and CHW channel-first inputs
- Supports per-channel extraction via `channel=0/1/2` or `channel="r"/"g"/"b"`
- Uses weighted grayscale only when no explicit channel is requested
- Sanitizes NaN/Inf/negative values
- Applies Gaussian background subtraction by default
- Rescales using percentiles computed on non-zero pixels only
- Returns `uint16` by default, with optional `uint8`

## Why The `channel` Argument Was Added

The original grayscale conversion mixed all RGB channels. That is wrong for live/dead or other multi-dye fluorescence assays where each reporter occupies its own channel.

The fix was to allow explicit channel extraction before preprocessing. This preserves reporter-specific signal and makes downstream thresholding/classification valid.

## Recommended Usage

For standard single-channel fluorescence:
- call `preprocess_shared_clean_baseline(raw_image)`

For RGB images where the biological signal is only in one channel:
- call `preprocess_shared_clean_baseline(raw_image, channel="g")` or the matching channel index

For live/dead workflows:
- preprocess each reporter channel independently
- segment from the structural channel
- classify masks using reporter intensities from the separately preprocessed channels

## Experimental Backing Included Here

The `experiments/` folder contains the preprocessing ablation artifacts that motivated this shared baseline.

Included files:
- `ANALYSIS_REPORT.md`
- `ablation_summary.csv`
- `heatmap_image_variant.png`
- `heatmap_param_sensitivity.png`
- `high_vs_low_signal.png`
- `high_vs_low_signal_cp0.png`

These support the decision to keep the current shared cleaned baseline as the default preprocessing path for fluorescence inputs.

## Relationship To The Main CellCounting Repo

This repo was created by copying the shared preprocessing assets out of the main project. The original source files still exist in the main workspace.

Files duplicated across repos:
- `shared_preprocessing.py`
- `shared_preprocessing_guide.md`

Important maintenance note:
- there is no sync automation between the two repos
- if the preprocessing logic changes in one place, the other copy must be updated deliberately

## Validation State

Completed during this handoff cycle:
- standalone repo created locally
- GitHub repo created and pushed
- guide added both as `README.md` and `shared_preprocessing_guide.md`
- preprocessing module updated to support explicit channel extraction
- ablation artifacts copied into `experiments/`

Not included here:
- a CLI wrapper
- packaging metadata beyond `requirements.txt`
- automated tests for this standalone repo

## Best Next Steps

1. Decide whether the standalone repo becomes the canonical source for `shared_preprocessing.py`, or whether the main `CellCounting` repo remains authoritative.
2. If this repo will be reused by other teams, add a small smoke test file and a pinned installation example.
3. If this repo will be imported directly by services, consider adding `pyproject.toml` and packaging it as an installable module.

## Repo Status At Handoff

The repo was pushed successfully to GitHub and should now be ready for sharing.