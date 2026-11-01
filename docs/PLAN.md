# Final Phased Plan — India Cloud Cover Nowcast (Goal 1) and Solar Generation (Goal 2)

Companion to ARCHITECTURE.md and DATA_FLOW.md. Implement one phase at a time. Each phase lists purpose, input, output, methods/tools, where results appear, exit criteria, and the recommended Claude model for building it.

## Fixed decisions (updated with Phase 0 measurements, see docs/products_report.md)

- Data: INSAT-3DS + INSAT-3DR via MOSDAC, May–Oct 2026 backfill (6 months), then live.
- Input route: Asia sector `3SIMG_L1C_ASIA_MER` + `3RIMG_L1C_ASIA_MER` (~23 MB/file), not full-disk `*_L1B_STD` (~410 MB/file). Six-month download 516 GB vs 6.85 TB. Full disk kept only as fallback if the sector product lacks a needed channel.
- Labels: `3SIMG_L2B_CMK` + `3RIMG_L2B_CMK` (~9 MB/file). Cover ~80% of slots; frames without a mask are used as model input but not scored.
- Filenames (confirmed): `3SIMG_27OCT2026_0600_L1C_ASIA_MER_V01R00.h5`, `3RIMG_27OCT2026_0615_L2B_CMK_V01R00.h5`.
- Slots (confirmed): 3DS at :00/:30, 3DR at :15/:45 UTC; interleaved = 15-min series. Image completeness 90–93% in the window.
- Extra products available: `*_L2B_CTP` (cloud top), `*_L2C_FOG`, `*_L2C_INS` (insolation, Goal 2), `3SIMG_L2P_AMV` (motion vectors, 3DS only, for checking our motion fields).
- History: 3DR archive from Oct 2016, 3DS from May 2024 (enough for Phase 7 if approved).
- All timestamps UTC. IST only for display.
- Grid: 0.04 deg, 6–38 N, 66–98 E, 800 x 800.
- Disk: 80 GB free measured (not 100). Pipeline pauses below 15 GB free, so ~65 GB usable. Archive estimate ~60 GB for 6 months; measured after the first converted day in Phase 1, with fallbacks (drop SWIR, or 5 instead of 6 months) if over.
- Training deferred; Phases 0–6 use no trained models of our own.
- Evaluation is a hindcast on the archive; live verification only confirms.
- Split: rotating weekly blocks (dev / val / test) with 1-day gaps.

## Phase summary

| Phase | Work | Developer time | Background / compute time | Claude model | Status |
|---|---|---|---|---|---|
| 0 | MOSDAC catalogue, credentials, skeleton, one file inspected | 1 day | minutes | Haiku 5.5 / Opus 5.5 | Done |
| 1 | Satellite ingestion, calibration, regridding, Zarr archive | 1 day (built) | ~25–26 h unattended via run_backfill.bat (measured 8.5 min/day) | Fable 5.1 | Code done and tested on 2 days; full run pending |
| 2 | Persistence, Lucas–Kanade, VET, ANVIL/LINDA forecasts | 4–5 days | ~1–3 min per forecast on CPU | Opus 5.5 | |
| 3 | Hindcast evaluation and dashboard | 5–7 days | ~1–2 h per model per full hindcast; ~8–12 h for all models | Fable 5.1 (metrics) / Sonnet 5.5 (dashboard) | |
| 4 | GFS blending, CloudCast zero-shot test | 4–5 days | GFS download ~1 h; one hindcast rerun | Opus 5.5 | |
| 5 | Live operations and map layer (Goal 1 done) | 4–5 days + 7 days live soak | continuous | Sonnet 5.5 / Opus 5.5 | |
| 6 | Solar irradiance and PV power (Goal 2) | 3–4 weeks | depends on SCADA access | Fable 5.1 / Opus 5.5 | |
| 7 | Training, only if gate says go | 4–6 weeks | multi-year download ~1–2 weeks; ~1–2 days per training run on A100 | Fable 5.1 | Conditional |

Goal 1 (Phases 0–5): about 5–6 weeks of developer time plus the 7-day live soak. Goal 2 adds 3–4 weeks.

## Choosing the Claude model per phase

| Model | Use for |
|---|---|
| Fable 5.1 | Scientific correctness that is hard to check: calibration and regridding, evaluation and leakage design, hybrid physics-AI, solar physics chain |
| Opus 5.5 | Substantial multi-file implementation with clear specs |
| Sonnet 5.5 | Routine code: API, UI, dashboard views, flows |
| Haiku 5.5 | Small edits, docs, config, quick scripts |

## Project folder layout

```
Cloud cover/
  docs/            ARCHITECTURE.md, PLAN.md, DATA_FLOW.md, products_report.md
  nowcast/
    config/        grid.yaml, products.yaml, splits.yaml, blend_weights.yaml
    ingest/        mosdac.py, gfs.py, isd.py, static.py
    process/       decode_insat.py, regrid.py, cloudmask.py, to_zarr.py, qc.py
    models/        persistence.py, motion.py (LK, VET), extrapolate.py, anvil.py, nwp.py, blend.py, cloudcast_pretrained.py
    evaluate/      hindcast.py, metrics.py, categories.py, sal.py, spectra.py
    serve/         run_forecast.py, export.py, api.py
    flows/         backfill.py, live.py, nightly_verify.py
    solar/         irradiance.py, pv_power.py, site_model.py      (Phase 6)
    train/         datamodule.py, unet.py, hybrid.py, train.py     (Phase 7)
  dashboard_eval/  Streamlit app (localhost:8501)
  data/            gitignored (see DATA_FLOW.md section 6)
  src/             existing Next.js map (localhost:3000), gains forecast layer
```

Progress surfaces: Prefect UI (localhost:4200) for data flows, Streamlit (localhost:8501) for scores, Next.js map (localhost:3000) for forecasts, MLflow (localhost:5000) in Phase 7 only.

---

## Phase 0 — Access, catalogue, setup (1 day) — Haiku 5.5, Opus 5.5 for the catalogue report — DONE except file inspection
- Purpose: confirm what MOSDAC serves before writing the pipeline.
- Input: rotated MOSDAC credentials in env vars; `https://mosdac.gov.in/apios/datasets.json`.
- Output: `nowcast/config/products.yaml` (IDs, first/last date, slot minutes, file size for 3SIMG/3RIMG L1B_STD, L1C_ASIA_MER if present, L2 cloud mask); `docs/products_report.md`; package skeleton; `.gitignore` for data/; hardcoded password removed from updater.
- Exit: cloud-mask product ID confirmed for both satellites (or fallback decided); 3DS slot minutes confirmed; one real file downloaded and its HDF5 tree dumped.

## Phase 1 — Satellite ingestion and archive — Fable 5.1 — CODE DONE, full run pending
- Purpose: raw files -> calibrated, aligned, compressed archive within the disk budget.
- Input: `3SIMG/3RIMG_L1C_ASIA_MER` and `3SIMG/3RIMG_L2B_CMK` HDF5 (MOSDAC).
- Output: `data/inputs.zarr` (tir1, tir2, mir, wv in K; vis albedo; swir radiance), `data/labels.zarr` (cmk classes), `data/backfill_state.json`, `data/logs/backfill.log`.
- Methods/tools: h5py LUT decode; exact Mercator -> 0.04 deg nearest-neighbour index (sector); KD-tree index cached per satellite (cloud mask); uint16 CF encoding in Zarr v3 with chunks (16, 200, 200); one day per unit of work, 4 parallel downloads, raw deleted after each day; resumable; keep-awake; auto-restart launcher.
- Code: `nowcast/process/{decode_insat,regrid,archive}.py`, `nowcast/flows/backfill.py`, `run_backfill.bat`. Runbook: docs/PHASE1_RUNBOOK.md.
- Measured: 2.95 GB raw/day, 0.30 GB archive/day, ~54 GB projected for 181 days, 8.5 min/day, ~26 h total.
- Moved out of Phase 1: GFS cloud fields -> Phase 4 (first consumer); NOAA ISD stations and terrain/land mask -> Phase 3. Each is a short download (< 1 h) that does not need an unattended run. Prefect replaced by the plain resumable script; Prefect can wrap the live flow in Phase 5.
- Visible in: `python -m nowcast.flows.backfill status`; `quicklook` PNGs in `data/quicklook/`.
- Exit: all 181 days done; projected size confirmed; quicklooks for one day per month checked.

## Phase 2 — Motion and baseline forecasts (1 week) — Opus 5.5
- Purpose: first 0–4 h forecasts, no training.
- Input: last 8 frames (inputs.zarr cloud probability + TIR1), static.
- Output: `data/forecasts/<YYYYMMDDTHHMM>/forecast.zarr` per model.
- Methods/models:
  - Persistence.
  - Motion fields: pysteps Lucas–Kanade (fast, sparse features) and VET, Variational Echo Tracking (global variational fit, smoother and more robust on large stratiform decks; slower, run at 400 x 400 and upsample the field).
  - Extrapolation: pysteps semi-Lagrangian of cloud probability with each motion field.
  - Growth/decay: ANVIL and LINDA adapted to cloud probability (experimental; designed for radar).
  - Satellite-mixing test: mixed 15-min 3DS/3DR series vs same-satellite 30-min pairs for motion estimation.
- Visible in: quick-look PNG strips in each forecast folder; temporary model selector on the map.
- Exit: all models run for any issue time in the archive; runtime per forecast logged (target < 3 min CPU).

## Phase 3 — Hindcast evaluation and dashboard (1–1.5 weeks) — Fable 5.1 for design and metrics, Sonnet 5.5 for dashboard views
- Purpose: decide which model is best with leakage-safe evidence.
- Input: archive, `nowcast/config/splits.yaml`, forecasts generated on the fly.
- Output: `data/results/results.parquet` (one row per model x issue time x lead x region x category x metric).
- Methods/tools: hourly issue times over test weeks (~1,000 runs x 16 leads per model), forecasts scored in memory and not stored; MAE, bias, CSI/POD/FAR, FSS, Brier, reliability, skill vs persistence, change categories (persist-cloud, persist-clear, formation, dissipation), SAL, spectra; pysteps.verification, xskillscore; Streamlit + matplotlib + cartopy.
- Visible in: Streamlit dashboard, ten views (see ARCHITECTURE.md 4.4).
- Exit: ranking table per lead time with LK vs VET vs ANVIL vs persistence; formation/dissipation panel populated for every model.

## Phase 4 — NWP blend and pretrained CloudCast (1 week) — Opus 5.5
- Purpose: extend useful skill toward 4 h.
- Input: GFS cloud fields (run available at issue time only), best extrapolation from Phase 3, FMI CloudCast weights.
- Output: blended forecast; `nowcast/config/blend_weights.yaml` (16 weights, fitted on val weeks); verdict on CloudCast zero-shot.
- Methods/tools: pysteps STEPS blending; CloudCast U-Net inference on GTX 1650.
- Visible in: dashboard skill curves (blend vs components).
- Exit: blend beats every component on test weeks at most lead times, or the reason it does not is documented.

## Phase 5 — Operations and map (1 week) — Sonnet 5.5, Opus 5.5 for the live flow
- Purpose: live forecast every 15 min, shown on the map, verified nightly. Goal 1 complete.
- Input: live MOSDAC feed, latest available GFS run.
- Output per run: `forecast.zarr` (archive, 7-day rolling), `lead_015.png` … `lead_240.png` (transparent palette overlays), `manifest.json` (issue time, bounds, leads, model, yesterday's skill), `lead_XXX.tif` Cloud-Optimised GeoTIFF for API clients; nightly rows in results.parquet.
- Methods/tools: Prefect live + nightly_verify flows; FastAPI (`/forecast/latest`, `/forecast/point?lat=&lon=`); Next.js route serving manifest and PNGs; Leaflet ImageOverlay with lead slider.
- Visible in: Next.js map (forecast layer, slider 15–240 min, issue time, skill badge); Streamlit operational panel (latency, missing frames).
- Exit: 7 consecutive days live with latency < 20 min from scan to map and no unhandled gaps.

## Phase 6 — Solar generation (3–4 weeks) — Fable 5.1 for the physics chain, Opus 5.5 for the site model
- Purpose: GHI and PV power forecasts per site. Goal 2.
- Input: cloud forecast, VIS cloud index, plant SCADA/pyranometer data, plant specification.
- Output: `data/sites/<site_id>/forecast_<issue>.parquet` (GHI, POA, power per lead), site metrics in results.parquet.
- Methods/tools: Heliosat clear-sky index, pvlib clear-sky + ModelChain, LightGBM residual model, Yang 2020 metrics.
- Visible in: Streamlit "Solar" tab; API `/sites/{id}/power`; site markers on the map.
- Exit: skill vs clear-sky-index persistence positive at all leads on test weeks.

## Gate — go/no-go for training
Train only if: formation POD near zero in pre-monsoon weeks, or skill vs persistence negative before 4 h in monsoon weeks, or Goal 2 error dominated by the 2–4 h window.

## Phase 7 — Training (conditional) — Fable 5.1
- Purpose: learn formation and dissipation.
- Input: 3+ years at 8 km (external drive or cloud), nwp.zarr, static.
- Output: `data/models/<run>/best.ckpt`, learned blender, MLflow runs.
- Methods/models: CloudCast-style U-Net (PyTorch Lightning), then HyPhAICC hybrid with motion from VET or a learned flow head; rented A100 or office GPU.
- Visible in: MLflow UI; same Streamlit views comparing against the Phase 4 blend; new entry in the map model selector.
