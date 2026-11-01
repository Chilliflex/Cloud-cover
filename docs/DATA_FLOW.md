# Data Flow — sources, conversion, final stores, retention

> Phase 0 update (2026-10-29, measured, see products_report.md): the input route is the Asia sector product `*_L1C_ASIA_MER` at ~23 MB/file instead of full-disk `*_L1B_STD` at ~410 MB/file. Cloud mask `*_L2B_CMK` is ~9 MB/file. Six-month download is 516 GB (not 1.7 TB) and the raw cache needs under 2 GB. Free disk measured at 80 GB. The tables below still show the original full-disk estimates for reference.

Companion to ARCHITECTURE.md (section 9) and PLAN.md (Phase 1). Per-file MOSDAC sizes are estimates until the Phase 0 products query records real values.

## 1. Sources (raw)

| Source | What arrives | Cadence | Raw size |
|---|---|---|---|
| MOSDAC `3SIMG_L1B_STD` (INSAT-3DS) | HDF5 per scan, full disk, 6 imager channels as integer counts + calibration LUTs, lat/lon arrays, satellite projection | :00 and :30, 48/day | ~100 MB/file, ~4.8 GB/day |
| MOSDAC `3RIMG_L1B_STD` (INSAT-3DR) | same layout | :15 and :45, 48/day | same |
| MOSDAC L2 cloud mask (both satellites, ID from Phase 0) | HDF5 per scan, integer class per pixel | 96/day combined | 2–5 MB/file, ~0.4 GB/day |
| NOAA AWS `noaa-gfs-bdp-pds` GFS 0.25 deg | GRIB2, only tcc/lcc/mcc/hcc, only India box, byte-range via .idx | 4 runs/day, steps 0–9 h | ~10 MB/day |
| NOAA ISD | hourly station records, ~100 Indian airports | daily batch | < 1 MB/day |
| ETOPO 2022 / GEBCO 30 arc-sec | NetCDF tile for the India box | once | ~30 MB |

Combined satellite input: 96 frames/day at 15-min spacing, ~290 GB raw HDF5/month. If `*_L1C_ASIA_MER` sector products are available, raw volume drops to roughly a quarter and the regrid step becomes a reprojection from Mercator.

Time alignment: 3DS at :00/:30 and 3DR at :15/:45 (verify in Phase 0) interleave to one 15-min series. Each slot carries a `satellite` coordinate and a `valid` flag. Missing slots are not filled in the archive.

## 2. Conversion (in memory, nothing intermediate on disk)

1. **Decode**: counts -> LUT -> brightness temperature (K) for MIR 3.9, WV 6.7, TIR1 10.8, TIR2 12.0; counts -> reflectance for VIS 0.65, SWIR 1.6. VIS/SWIR divided by cos(SZA), masked at SZA > 85 deg. Reason: counts are satellite-specific; physical units are comparable across 3DS/3DR.
2. **Crop + regrid**: full disk -> India box 6–38 N, 66–98 E -> fixed 0.04 deg grid, 800 x 800, via pyresample (kd-tree; nearest for mask, bilinear for continuous). Resampler index precomputed once per satellite. Reason: optical flow, metrics and tiles need pixel-aligned frames across time and satellites.
3. **QC**: flags for partial scan, LUT out of range, sun-glint, eclipse; frame-level `qc_ok`.
4. **Encode**: BT as uint16 with scale 0.01 K + offset 150 K; reflectance as uint16 with scale 1e-4. Same 2 bytes/pixel as float16 but 0.01 K precision (float16 gives 0.25 K at 300 K) and better compression. xarray decodes via `scale_factor`/`add_offset`.
5. **Append** to Zarr with region writes; chunks (time=16, channel=1, y=256, x=256), zstd level 3.

Stored channels: 6 physical (VIS, SWIR, MIR, WV, TIR1, TIR2). Derived on the fly: BTD TIR1−TIR2 (cirrus), BTD MIR−TIR1 (fog/low cloud), cloud probability from the mask.

| Store | Encoding | Per frame (uncompressed) | Per month (2,880 frames) |
|---|---|---|---|
| `inputs.zarr` (6 ch, 800x800) | uint16 scaled, zstd | 7.7 MB | 22 GB raw, ~10 GB compressed |
| `labels.zarr` (cloud mask) | uint8, zstd | 0.64 MB | 1.8 GB raw, ~0.4 GB compressed |
| `nwp.zarr` (4 fields, 0.25 deg, 129x129) | float16 | 0.27 MB per forecast hour | ~150 MB |
| `stations.parquet` | parquet | — | ~1 MB |
| `static/static.nc` (DEM, land mask, lat, lon, pixel area) | float32, 800x800 | — | ~10 MB total |

Ratio raw -> kept: ~25 : 1.

Why Zarr, not NetCDF/HDF5: parallel chunked reads of (time, y, x) windows; safe concurrent appends from multiple workers; cloud-copyable directory layout. Why not keep raw: 25x larger, regenerable from MOSDAC.

## 3. Consumers (what reads what)

| Consumer | Reads | Writes |
|---|---|---|
| optical flow / ANVIL / blend | last 8 frames of inputs.zarr + labels.zarr, latest nwp.zarr | `forecasts/<run>/` Zarr (16 x 800x800 uint16 prob) + COG per lead |
| evaluation | labels.zarr window, stations.parquet, forecasts | `results/results.parquet` |
| map (Next.js) | COG tiles of latest run | — |
| training (Phase 7) | inputs/labels/nwp Zarr via windowed loader | checkpoints, MLflow |

No consumer ever reopens a raw HDF5.

## 4. Retention — no-training phase (1 month backfill + live, ~2.5 months by week 6)

| Kept | Size |
|---|---|
| inputs.zarr | ~25–30 GB |
| labels.zarr | ~1 GB |
| nwp.zarr + stations + static | < 1 GB |
| results.parquet | < 0.5 GB |
| forecasts, rolling 7 days (Zarr + tiles, ~3 GB/day) | ~20 GB constant |
| raw cache, last 1–2 days HDF5 | 10–20 GB constant |
| **Total** | **~60–70 GB, +12 GB/month** |

Deleted / never written: ~720 GB raw HDF5 streamed through; ~30 GB raw cloud-mask HDF5; DEM download after downsampling; forecasts older than 7 days (except case-study dates); ~180 GB of evaluation forecasts scored in memory and never stored.

Optional 6-month backfill adds ~50 GB to inputs.zarr and streams ~1.4 TB more raw.

## 5. Retention — training phase (3 years, both satellites, ~105k frames)

| Kept | Size | Note |
|---|---|---|
| `train8km/inputs.zarr` (400x400, 6 ch) | ~100 GB compressed | 2x2 mean pooling of the 4 km frames; built during the historical stream |
| `train8km/labels.zarr` | ~4 GB | majority / fraction pooling |
| nwp.zarr, 3 years | ~5 GB | |
| 4 km live archive | 12 GB/month (150–220 GB after 12–18 months) | keep last 6 months on main disk; older months to external drive |
| checkpoints (best + last per run, ~10 runs) | ~2.5 GB | 124 MB each for 31 M params fp32 |
| MLflow DB + results | < 2 GB | |
| **Total** | **~300–350 GB** | external drive for old 4 km months is part of the plan |

Deleted: ~10 TB raw HDF5 streamed once; 4 km frames for years kept only at 8 km; all checkpoints except best + last; validation prediction dumps; training sample caches.

Why 8 km for training: 3 years at 4 km is ~400 GB compressed and does not fit beside the live archive on 512 GB. CloudCast trained at ~5 km. If 4 km training is later justified, stream the raw data again (bandwidth cost, not disk cost).

## 6. Directory layout under `data/` (gitignored)

```
data/
  raw_cache/            last 1–2 days of HDF5 (auto-pruned)
  inputs.zarr/          4 km archive, 6 channels
  labels.zarr/          4 km cloud mask
  nwp.zarr/             GFS cloud fields
  stations/stations.parquet
  static/static.nc
  forecasts/<YYYYMMDDTHHMM>/   forecast.zarr, lead_###.tif, quicklook.png  (7-day rolling)
  results/results.parquet
  cases/                hand-picked forecast runs kept permanently
  train8km/             Phase 7 only
  models/<run>/         Phase 7 only
```
