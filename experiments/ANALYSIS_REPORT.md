# Preprocessing Ablation Sweep: Analysis Report

## Experiment Summary
- **11 CP HEK293 fluorescence images** (green channel, transfection assay)
- **7 preprocessing variants**: A (raw grayscale), B (green channel extract), C (current pipeline / shared_preprocessing.py), D (CLAHE), E (CLAHE + denoise), F (rolling ball), G (rolling ball + CLAHE)
- **9 flow thresholds**: 0.2 → 1.0 (step 0.1)
- **6 cellprob thresholds**: -3.0, -2.0, -1.0, 0.0, 1.0, 2.0
- **Total**: 4,158 inference runs on GCP (NVIDIA L4)
- **Model**: CP-SAM (Cellpose 4), `diameter=None` (auto-estimated)

---

## Key Finding: Two Distinct Image Classes

The 11 images split cleanly into two groups:

| Group | Images | Max cell count | Characteristic |
|-------|--------|---------------|----------------|
| **HIGH signal** (4) | (9), (10), (15), (16) | 400-567 | Dense bright cells, clearly visible |
| **LOW signal** (7) | (2), (3), (6), (7), (11), (12), (13) | 0-27 | Very dim/sparse fluorescence |

Visual inspection confirms:
- HIGH signal images show hundreds of bright green fluorescent cells
- LOW signal images are nearly dark — genuine low-transfection-efficiency samples with very few faint cells

---

## Finding 1: C_current_pipeline Dominates on Low-Signal Images

At `flow=0.4, cellprob=0.0`:

| Variant | HIGH signal (mean) | LOW signal (mean) | LOW signal range |
|---------|-------------------|-------------------|------------------|
| **C:CurrPipe** | **304** | **13.9** | [5, 21] |
| D:CLAHE | **348** | 0.7 | [0, 4] |
| G:RB+CLAHE | 332 | 0.4 | [0, 1] |
| A:Raw | 299 | 2.3 | [0, 5] |
| B:Ch.Ext | 295 | 2.6 | [0, 5] |
| E:CLAHE+Dn | 323 | 0.6 | [0, 2] |
| F:RollBall | 281 | 1.4 | [0, 4] |

**C:CurrPipe detects 5-7x more cells on dim images than any other variant.** This is because `shared_preprocessing.py` does aggressive percentile clipping + background subtraction + rescale to uint16, which combined with Cellpose's internal 1-99 percentile normalization, creates extreme contrast stretching that reveals very faint cells.

---

## Finding 2: D_CLAHE is Best on High-Signal Images

On well-lit images, CLAHE-based variants produce 10-16% more detections:

| Variant | HIGH signal mean (flow=0.4, cp=0) | vs Raw |
|---------|-----------------------------------|--------|
| D:CLAHE | 348 | **+16.4%** |
| G:RB+CLAHE | 332 | +11.0% |
| E:CLAHE+Dn | 323 | +8.0% |
| C:CurrPipe | 304 | +1.7% |
| A:Raw | 299 | baseline |
| B:Ch.Ext | 295 | -1.3% |
| F:RollBall | 281 | -6.0% |

---

## Finding 3: Parameter Sensitivity

### Flow threshold
- Cell counts increase with flow threshold but plateau at **0.6-0.7**
- Little benefit going above 0.7
- Diminishing returns: 0.2→0.4 adds ~35% cells; 0.7→1.0 adds ~3%

### Cellprob threshold
- Sweet spot is **cellprob = -1 to 0**
- Peak detection at cellprob = -1 (slightly more cells than 0, but may include more noise)
- cellprob = 1 or 2 aggressively filters, dropping count 20-45%
- cellprob = -3 produces very few cells (overly permissive → Cellpose internal filtering kicks in differently)

### Recommended parameters
- **flow_threshold = 0.4-0.7** (0.4 is more conservative, 0.7 captures stragglers)
- **cellprob_threshold = 0.0** (best balance of sensitivity vs specificity)

---

## Finding 4: A_raw vs B_channel Are Nearly Identical

Green channel extraction (B) performs almost identically to raw grayscale conversion (A), confirming that Cellpose's internal normalization handles the RGB→grayscale conversion adequately. The noise amplification concern from RGB channels is not significant for images that are already predominantly green.

---

## Recommendations

### For Transfection Efficiency Pipeline

The fluorescence channel images naturally span from very few cells (low TE) to many cells (high TE). We need a single pipeline that works across the full range.

**Recommended: `C_current_pipeline` (existing shared_preprocessing.py)**

Rationale:
1. **Only variant that works on low-signal images** — 5-7x more detections than alternatives
2. **Competitive on high-signal** — 90% of best variant's count (304 vs 348)
3. The low-signal detection gap is far more impactful than the high-signal deficit
4. For TE calculation, missing 50% of numerator cells on sparse images is catastrophic; missing 13% on dense images is a tolerable bias

**Alternative: Signal-adaptive two-stage approach**
1. Run with D_CLAHE first
2. If cell count < threshold (e.g., 50), re-run with C_current_pipeline
3. Adds complexity but could capture best of both worlds

### Recommended Parameters
- `flow_threshold = 0.4` (conservative, stable; or 0.7 if maximizing recall)
- `cellprob_threshold = 0.0`
- `diameter = None` (auto-estimation)

---

## Open Question: False Positive Rate on Low-Signal Images

C_current_pipeline finding 14-19 cells on images where other variants find 0-4 raises a question: are these real cells or noise artifacts from double-normalization?

Visual inspection of the original images suggests they are plausible (dim but visible spots are present), but **ground truth annotation is needed to validate**. This should be the next step before committing to C_current_pipeline for production.

---

## Files
- Raw data: `preprocessing_ablation/results/ablation_summary.csv`
- Heatmaps: `preprocessing_ablation/results/heatmap_image_variant.png`, `heatmap_param_sensitivity.png`
- Signal comparison: `preprocessing_ablation/results/high_vs_low_signal_cp0.png`
- Comparison grids (per image): `preprocessing_ablation/results/CP HEK293 (N)/_comparison_grid.png`
- Analysis scripts: `preprocessing_ablation/analyze_ablation.py`, `analyze_ablation_heatmaps.py`
