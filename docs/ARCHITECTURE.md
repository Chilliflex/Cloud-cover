# Cloud Cover Nowcasting System for India — Architecture

Goal 1: cloud cover forecast, 0–4 h ahead, 15-minute steps (16 lead times), all of India, from INSAT via MOSDAC.
Goal 2: feed Goal 1 into solar irradiance and PV generation forecasts for solar farms.

Reference baseline: FMI CloudCast (Partio et al. 2025, repo cloned in ../cloudcast_fmidev):
4 input frames (1 h), sun elevation + lead time as predictors, 512x512 at ~5 km, BCE + L1 loss,
3 years of 15-min data, ~31 M params, trained ~2 days on one V100 32 GB. Usable skill to ~3 h,
then blended with NWP out to 5 h.

---

## 0. Target definition (decide first, everything depends on it)

| Item | Decision | Why |
|---|---|---|
| Domain | 6–38 N, 66–98 E | All of India plus margin for clouds advecting in |
| Grid | Regular lat/lon 0.04 deg (~4 km), 800 x 800. Train on 512x512 crops or 2x-downsampled 400x400 | Matches INSAT IR native 4 km; CloudCast-scale cost |
| Primary target | Per-pixel cloud probability p(cloud) in [0,1], 16 frames | Directly scoreable, blends naturally, needed for Goal 2 |
| Secondary target (Goal 2) | Effective cloud albedo / cloud index n (Heliosat) in daytime | Converts to clear-sky index and GHI |
| Label source | MOSDAC L2 cloud mask (CMK) when available; fallback own mask from ATBD ch. 2 thresholds | Official product, validated (Parihar 2024) |
| Input history | 8 frames = 2 h (ablate 4 vs 8) | CloudCast uses 4; convection benefits from longer history |
| Split | By time: train / val / test on whole seasons, test year never touched | 15-min frames are near-duplicates; random split leaks |
| Archive depth | Phase A minimum: 1 month backfill + live from day one (~12 GB/month). Optional: 6 months spanning two seasons for a cross-regime evaluation. Phase B: 3+ years | Goal 1 needs little data; the evaluation is provisional until the monsoon has been observed live; training archive builds itself meanwhile |

---

## 1. Data collection

| Data | Product / source | Format | Tool | Cadence |
|---|---|---|---|---|
| INSAT-3DS imager L1B | MOSDAC `3SIMG_L1B_STD` (already working in updater/download_latest_insat.py) | HDF5, counts + LUT | requests + MOSDAC download API | every 30 min; 3DR `3RIMG_L1B_STD` staggered gives 15 min |
| INSAT L2 cloud mask | MOSDAC `*_L2B_CMK` (confirm ID via datasets.json) | HDF5 | same | same |
| NWP cloud fields | ECMWF open data 0.25 deg: tcc, lcc, mcc, hcc; optional NCMRWF NCUM-R | GRIB2 | `ecmwf-opendata`, `cfgrib` | 4x daily, hourly steps |
| Station truth | NOAA ISD / METAR cloud layers (oktas) for Indian airports | CSV | `requests`, pandas | hourly |
| Solar truth (Goal 2) | Plant pyranometers / SCADA | CSV | pandas | 1–15 min |
| Static | Copernicus DEM, land-sea mask, lat/lon, solar zenith angle | GeoTIFF / computed | rasterio, pvlib.solarposition | once |

Orchestration: Prefect (flows with retries, scheduling, UI). Why not Airflow: heavier to run for a small team. Why not cron: no retries, no visibility of gaps. Backfill: bulk order from MOSDAC archive (3–5 years) as a one-off flow.

Secrets: MOSDAC credentials via environment only; rotate the password currently in git history.

---

## 2. Processing

Pipeline per frame (Prefect task, idempotent, keyed by timestamp):

1. **Decode** HDF5 with h5py: counts -> LUT -> brightness temperature (K) for TIR1 10.8, TIR2 12.0, MIR 3.9, WV 6.7; counts -> reflectance for VIS 0.65 and SWIR 1.6; divide VIS by cos(SZA), mask SZA > 85 deg.
2. **Derived channels**: BTD 10.8–12.0 (thin cirrus), BTD 3.9–10.8 (low cloud / fog, night), cloud mask label.
3. **Regrid** satellite-projection lat/lon arrays to the fixed 0.04 deg grid with `pyresample` (kd-tree nearest for mask, bilinear for continuous). Precompute the resampler once per satellite.
4. **Time-align** to 15-min boundaries; store a validity mask; never gap-fill the archive (gap-fill only at inference, with the optical-flow extrapolation of the last good frame).
5. **QC flags**: missing/partial scans, calibration out-of-range, sun-glint, eclipse periods; frame-level `qc_ok` boolean used to filter training samples.
6. **Store** as Zarr: dims (time, channel, y, x), chunks (16, 1, 256, 256), uint16 scaled (BT 0.01 K, reflectance 1e-4) + zstd. 6 physical channels stored; BTDs derived on the fly. Full detail in DATA_FLOW.md. One store for inputs, one for labels, one for NWP interpolated to the grid and 15-min cadence.

Why Zarr + xarray + dask: random window reads in parallel for training; append-only for the live feed; NetCDF/HDF5 cannot do concurrent chunked reads well. Better alternative to consider later: Icechunk (versioned Zarr) if multiple people rewrite the archive.

Why pyresample not satpy: satpy has no maintained INSAT-3D reader; the HDF5 layout is simple enough to read directly (the current updater already does this). Keep satpy only for Meteosat IODC if it is added as a second source.

The ad-hoc temperature-threshold cloud fraction in updater/convert_h5_to_png.py is replaced by the official L2 mask or the ATBD algorithm; it is not a defensible label.

---

## 3. Models (tiered; every tier is kept as a permanent baseline for the next)

### Phase A — no training (build first; this is the first operational product)
- **Persistence**: last frame repeated. The floor every model must beat.
- **Optical flow extrapolation**: `pysteps` motion field, Lucas–Kanade and VET (Variational Echo Tracking, smoother on large stratiform decks, run at 400x400), + semi-Lagrangian advection of the cloud probability field. Strong to ~60 min. Better alternative: RAFT deep optical flow (torchvision, pretrained, inference only) if LK motion is noisy over textureless cloud decks.
- **Growth/decay without training**: `pysteps` ANVIL (autoregressive nowcast with intensity growth and decay along the flow) and LINDA (cell growth/decay). Closest no-training answer to formation/dissipation; cannot create convection from clear sky — the change-category diagnostic (4.2a) measures how much is missed.
- **NWP only**: ECMWF tcc interpolated to 15 min. Weak below 2 h, the anchor for 3–4 h.
- **NWP blending**: `pysteps.blending` STEPS blending of extrapolation with ECMWF cloud fields; lead-time weights fixed from a short validation period (a handful of numbers, not model training).
- **Pretrained CloudCast weights, inference only**: FMI publishes the trained U-Net. Run zero-shot on the INSAT cloud mask (regrid to its expected input). Trained on European NWCSAF cloudiness, so expect degraded skill, but if it beats optical flow at 2–3 h it is a free DL tier.
- Phase A product = blend of [optical flow / ANVIL, NWP, optionally pretrained CloudCast] with fixed per-lead weights.

**Go/no-go for Phase B (training)** — any of:
- formation-category POD stays near zero while clouds form daily (pre-monsoon afternoons);
- skill vs persistence turns negative before 4 h in monsoon;
- Goal 2 irradiance error is dominated by the 2–4 h window.

### Phase B — trained models (only if Phase A hits its ceiling; everything below is unchanged)

#### Tier 1 — DL core (reproduce CloudCast on INSAT)
- U-Net, multi-frame output (16 channels) or autoregressive with lead-time conditioning as in CloudCast.
- Inputs: 8 frames x [TIR1, TIR2, WV, MIR, BTD1, BTD2, VIS(masked), cloud prob] + static [DEM, land-sea, lat, lon] + dynamic [SZA, hour sin/cos, doy sin/cos] + NWP [tcc, lcc, mcc, hcc at target lead].
- Loss: BCE + L1 (as CloudCast). Add FSS loss or SSIM term if blur dominates.
- Framework: PyTorch + Lightning (CloudCast code is TF2; port it — PyTorch has the nowcasting ecosystem: Earthformer, DGMR, NowcastNet reference code). Config: Hydra. Tracking: MLflow (self-hosted) or Weights & Biases. Data loading: xbatcher over Zarr, or a custom Dataset reading chunks.
- Upgrade path: SmaAt-UNet (cheap attention) -> Earthformer (space-time transformer).

#### Tier 2 — hybrid physics + AI (HyPhAICC pattern; targets formation/dissipation)
- Decompose the forecast: `p(t+k) = Advect(p(t), motion) + S_theta(x, t, k)`.
- Motion field: optical flow (pysteps) or a learned flow head; advection by differentiable semi-Lagrangian warping (grid_sample) so the network trains end-to-end.
- Source/sink network S_theta learns formation and dissipation only, conditioned on IR tendencies, WV, SZA, NWP instability fields (CAPE, RH700, low-level convergence from ECMWF).
- Why: advection error and formation error are separated by construction, which is exactly what the diagnostics in section 4 measure. The pure U-Net blurs cloud edges to hedge; the hybrid keeps sharp advected structure.

#### Tier 3 — only if 3–4 h fields are too blurry
- Generative: NowcastNet-style (physics-conditioned) or latent diffusion. Produces ensembles -> CRPS, probabilistic products. Cost: 5–10x training time.

#### ML tier (point/site level, both goals)
- LightGBM per site: inputs = the gridded forecast at the site + neighbourhood stats + NWP + diurnal features; target = station okta or plant clear-sky index. Cheap, calibrated, handles site bias. Not a replacement for the spatial model.

#### Blender (Phase B version)
- Per-lead-time, per-pixel weights over [optical flow, DL, NWP], learned with logistic regression or a small MLP on the validation year. Replaces the fixed-weight Phase A blend. Output stays a probability. This is the operational product.

---

## 4. Evaluation framework (the part that tells us what to fix)

Library: `pysteps.verification` (FSS, SAL, spatial scores), `xskillscore` (CRPS, Brier, RPS on xarray), `scores` (BoM) as alternative. All metrics computed as xarray along dims (lead, season, region, daynight) and saved to a results Zarr/Parquet so plots are cheap.

### 4.1 Core scores (per lead time, vs every baseline)
| Metric | Reads as |
|---|---|
| MAE, bias of cloud probability | continuous accuracy, systematic over/under |
| CSI, POD, FAR at p>0.5 | hit/miss behaviour on the mask |
| FSS at 1, 3, 10, 25 pixels | credit for near-misses; the scale where FSS > 0.5 is the "useful scale" |
| Brier score, reliability diagram | calibration of probabilities |
| CRPS (Tier 3 ensembles) | probabilistic accuracy |
| Skill vs persistence = 1 - MAE_model / MAE_persist | the headline. Must be > 0 at all 16 leads |
| Skill vs optical flow | must be > 0 from ~45 min on, else DL is not earning its cost |
| MAE in oktas vs METAR | independent truth |

### 4.2 Diagnostic decomposition — where the model fails
**(a) Change-category scores.** For each (t0, lead), classify every truth pixel by comparing truth(t0) and truth(t0+lead):
`persist-cloud`, `persist-clear`, `formation` (clear -> cloud), `dissipation` (cloud -> clear).
Compute POD/FAR/MAE separately in each category. A model good at advection but blind to convection shows high scores on persist-cloud and near-zero POD on formation. Plot: 4 lines vs lead time.

**(b) Advection-explained vs residual error.** Error_model minus Error_opticalflow per pixel. Where DL < OF: DL adds value (formation/dissipation). Where DL > OF: DL is degrading motion. Map it, aggregate by region and season.

**(c) SAL (Structure–Amplitude–Location), Wernli et al. 2008.** One point per forecast in a 3-axis plot. L > 0: clouds in the wrong place (advection error). S < 0: forecast too smooth/small (blur). A > 0: too much cloud (over-forecast). This separates the three failure modes in one figure.

**(d) Spectral / sharpness.** Radially averaged power spectrum of forecast vs truth per lead. Loss of high-frequency power = blurring. Also effective resolution = scale where forecast spectrum drops below half of truth.

**(e) Object-based (optional).** Identify cloud objects (scipy.ndimage.label / MODE-style). Match forecast vs truth objects; score centroid displacement (advection), area ratio (growth/decay), unmatched truth objects (missed initiation).

### 4.3 Stratification (every score above is also cut by)
- Lead time: 15 … 240 min (always on the x-axis)
- Season: winter (DJF, fog in Indo-Gangetic plain), pre-monsoon (MAM, afternoon convection), monsoon (JJAS), post-monsoon (ON)
- Day / night / twilight (VIS availability)
- Region tiles: NW arid, IGP, Central, Western Ghats/coast, East coast, NE hills, Peninsular interior, Himalaya, ocean margin
- Cloud type proxy from BT: high (BT<240 K), mid, low/warm cloud

### 4.4 Visualisations (eval dashboard)
1. **Skill-vs-lead curves**: MAE/CSI/FSS for persistence, OF, NWP, DL, hybrid, blend. One panel per season.
2. **FSS heatmap**: scale x lead time, one per model. Shows the useful-scale frontier.
3. **Change-category panel**: POD on formation / dissipation / persistence vs lead. The "convection blindness" chart.
4. **Spatial skill maps** over India: mean CSI or skill-vs-persistence per pixel per season; plus the DL-minus-OF error map (where DL helps / hurts).
5. **Diurnal x lead heatmap**: skill by hour-of-day and lead; exposes afternoon convection and dawn/dusk VIS transitions.
6. **SAL scatter** per model and lead.
7. **Reliability diagram + sharpness histogram** per lead.
8. **Power spectrum overlay** truth vs forecast at 1, 2, 3, 4 h.
9. **Case-study strips**: rows = truth, persistence, OF, DL, hybrid; columns = +1, +2, +3, +4 h; for hand-picked events (monsoon burst, pre-monsoon storm, IGP fog, clear sky).
10. **Operational panel**: data latency, missing frames, inference time per run.

Tools: matplotlib + cartopy for publication-grade static plots; Streamlit app (Python, reads the results Zarr) for the interactive internal dashboard; the existing Next.js/Leaflet map for the customer-facing forecast product. Alternative: Panel/HoloViews with Datashader if the spatial maps get heavy; Grafana only for the operational panel.

### 4.5 Acceptance criteria (Goal 1)
- Skill vs persistence > 0 at all leads; > 0.2 at 1 h, > 0.3 at 2–4 h (set after baseline run)
- Beats optical flow from 45 min onward in all seasons
- Formation-category POD at 1 h at least 2x optical flow (OF is ~0 by construction)
- Reliability: calibration curve within +/-0.05 of diagonal
- End-to-end latency scan time -> product < 20 min

---

## 5. Serving

- Trigger: Prefect flow on new MOSDAC frame (poll datasets.json every 2 min, as `/api/mosdac-latest` already does).
- Inference: PyTorch model exported to TorchScript/ONNX, run on GPU or CPU; 1 forecast = 16 frames 800x800.
- Products: Zarr (archive), Cloud-Optimised GeoTIFF per lead (map tiles), JSON point extracts for sites. Served by FastAPI; tiles via TiTiler or the existing Next.js `/api` routes.
- Monitoring: Prometheus/Grafana (latency, gaps), plus nightly automatic verification of yesterday's forecasts feeding the same results Zarr as the eval dashboard, so the Streamlit plots are live.

---

## 6. Goal 2 chain (solar)

1. From forecast cloud probability and VIS-derived cloud index n -> clear-sky index k_c = 1 - n (Heliosat / SARAH, Mueller 2015).
2. Clear-sky GHI from pvlib (Ineichen–Perez with Linke turbidity, or REST2 if aerosol data available; India needs aerosol care — MOSDAC AOD product can feed this).
3. GHI = k_c x GHI_clear; decompose to DNI/DHI (Erbs/DISC), transpose to plane of array, PV power via pvlib ModelChain with the plant's module/inverter/tracker spec.
4. Site correction: LightGBM on plant SCADA residuals (soiling, curtailment, temperature).
5. Metrics (Yang et al. 2020): nMAE, nRMSE normalised by capacity, skill vs smart persistence (clear-sky-index persistence), per lead and per hour of day; ramp detection scores for the grid operator use case; reliability for probabilistic generation.
6. Visualisations: same skill-vs-lead curves, plus GHI scatter forecast vs measured per lead, diurnal error profile, ramp-event case strips.

---

## 7. Tool summary and the "is there anything better" column

| Stage | Chosen | Why | Better/alternative, and when |
|---|---|---|---|
| Download | requests + MOSDAC download API | already works in this repo | add EUMETSAT Data Store (eumdac) for Meteosat IODC as redundancy |
| Orchestration | Prefect | light, retries, UI | Airflow/Dagster at larger team scale |
| Decode/regrid | h5py + pyresample | no INSAT reader in satpy | satpy if Meteosat added |
| Storage | Zarr + xarray + dask | parallel chunked windows | Icechunk for versioning |
| Baselines | pysteps | standard, has FSS/SAL | RAFT optical flow (torchvision) if LK is noisy |
| DL | PyTorch + Lightning, U-Net -> SmaAt-UNet -> Earthformer | ecosystem of nowcasting code | JAX if scaling to many GPUs |
| Hybrid | HyPhAICC pattern, grid_sample advection | separates motion from formation | NowcastNet-style generative evolution network |
| Point ML | LightGBM | fast, calibrated | CatBoost similar |
| Experiment tracking | MLflow | self-hosted, free | W&B for nicer dashboards |
| Config | Hydra | sweeps, reproducibility | — |
| Metrics | pysteps.verification + xskillscore | spatial + probabilistic, xarray-native | BoM `scores` |
| Eval dashboard | Streamlit + matplotlib/cartopy | fastest to build in Python | Panel/HoloViews for big rasters |
| Serving | FastAPI + ONNX/TorchScript, COG tiles via TiTiler | simple, stateless | Triton Inference Server at high QPS |
| Product map | existing Next.js + Leaflet | already built | — |
| Solar | pvlib | reference implementation | — |

---

## 8. Build order

Phase A (no training):
1. Confirm MOSDAC product IDs and archive depth (datasets.json query). Start continuous collection of L1B + CMK now; backfill 3–6 months covering two seasons.
2. Processing pipeline -> Zarr archive. Validate against the updater's current decoding.
3. Persistence + optical flow + ANVIL + NWP + STEPS blending, and the full evaluation framework + dashboard. This is the measuring stick and the first product.
4. Try pretrained CloudCast weights zero-shot; keep it in the blend only if it beats optical flow at 2–3 h.
5. Fixed-weight blender + serving + nightly verification. Goal 1 delivered.
6. Goal 2 chain on top, starting with one plant with SCADA data.

Phase B (only on a go decision from the diagnostics in 4.2):
7. Tier 1 U-Net reproduction of CloudCast on INSAT (needs 3+ years archived by then).
8. If formation POD is still poor, Tier 2 hybrid. Tier 3 only for blur.
9. Learned blender replaces the fixed weights.

---

## 9. Data and storage plan

### Phase A download list
| Data | Source / product ID | Period | Size |
|---|---|---|---|
| INSAT-3DS L1B imager | MOSDAC `3SIMG_L1B_STD` (existing script) | May–Oct 2026 backfill, then live | ~100 MB/file, 48/day |
| INSAT-3DR L1B imager | MOSDAC `3RIMG_L1B_STD` (staggered -> 15 min) | same | same |
| INSAT L2 cloud mask | MOSDAC CMK product for both satellites (confirm ID via datasets.json) | same | few MB/file |
| NWP cloud fields | GFS 0.25 deg from NOAA AWS archive (`noaa-gfs-bdp-pds`), cloud fields only via GRIB index byte ranges. ECMWF open data has no archive, use it only live and only if it verifies better | same | 1–2 MB per forecast hour |
| Station truth | NOAA ISD, ~100 Indian airports | same | < 100 MB |
| Static | Copernicus DEM, Natural Earth land mask | once | few MB after downsampling |

Check first: MOSDAC Asia Mercator sector products (`*_L1C_ASIA_MER`) are several times smaller and already projected. Prefer them if the account has them.

Download volume: both satellites, 1 month ~ 2.9k files ~ 290 GB streamed (download -> convert -> delete; ~12 GB Zarr kept). Optional 6 months ~ 17k files ~ 1.7 TB streamed (~70 GB kept). Disk holds at most one day of raw. MOSDAC bandwidth is the bottleneck (hours to days per month of data).

### Stores and sizes (6 months)
| Store | Format | Content | Size |
|---|---|---|---|
| inputs.zarr | uint16 scaled + zstd, chunks (16, 1, 256, 256) | 6 channels, 0.04 deg India grid, 15 min | ~60 GB (~10 GB/month) |
| labels.zarr | uint8 | cloud mask, same grid | ~2 GB |
| nwp.zarr | float16 | 4 cloud fields at native 0.25 deg, interpolated at use | < 1 GB |
| stations.parquet | parquet | hourly oktas | < 100 MB |
| results.parquet | parquet | metrics by model/lead/season/region/daynight | < 1 GB |
| forecasts/ | Zarr + COG per lead | 16 frames per run, 20 MB/run | 2 GB/day, rolling |

Growth: ~12 GB/month of archive; this becomes the Phase B training data.

### Delete rules (project still runs and forecasts are viewable)
- Raw HDF5: delete right after conversion; keep a 2-day cache for reprocessing.
- Forecast outputs: keep last 7 days + case-study dates; metrics already live in results.parquet. Never store forecasts for the whole evaluation period (~85 GB per model).
- PNG tiles / plots: regenerate from Zarr on demand.
- Keep: inputs.zarr, labels.zarr, nwp.zarr, stations, static, results, config.
- Live operation needs only: last 2 h of frames, latest NWP run, static fields, config (+ weights file in Phase B).

### Phase A timeline (one engineer)
| Week | Work |
|---|---|
| 1 | Confirm product IDs / archive depth, credentials to env, start backfill, download->Zarr conversion |
| 2–3 | Persistence, optical flow, ANVIL baselines; evaluation framework; first metrics |
| 3–4 | GFS blending, pretrained CloudCast zero-shot test, evaluation dashboard |
| 5–6 | Fixed-weight blend, live serving every 15 min, nightly verification, case studies |

Compute: backfill processing ~8 h on 6 cores; each full evaluation 1–2 h; live forecast 1–3 min.

### Phase B differences
- Data: 3+ years (3DR whole span; 3DS from 2024; 3D before). Full-disk download ~10 TB streamed and deleted, ~1 month continuous. Store older years at 8 km, 6 channels (~100 GB compressed for 3 years). Phase A archive keeps accumulating at 4 km.
- New keeps: checkpoints (~125 MB each; keep best + last per run), MLflow DB.
- New deletes: training sample caches, validation prediction dumps (regenerable).
- Inference needs Phase A inputs + one weights file.
