# Phase 1 Runbook — unattended backfill

Downloads INSAT-3DS/3DR Asia-sector imagery and cloud masks from MOSDAC for the window in
`nowcast/config/archive.yaml` (2026-05-01 .. 2026-10-28), converts them onto the 0.04 deg
India grid, writes `data/inputs.zarr` and `data/labels.zarr`, and deletes the raw files.
No Claude session is needed while it runs.

## Start
Double-click `run_backfill.bat` in the project folder, or from a terminal in the project folder:

    run_backfill.bat

It restarts automatically after crashes or network loss (every 5 minutes, up to 50 times),
stops when complete or when free disk falls below 18.5 GB, and keeps Windows from sleeping
while it runs. Closing the window stops it; running it again resumes at the first unfinished day.

Before leaving it: plug in the laptop/PC and set Windows Update "pause updates" for 3 days,
since a forced restart stops the run (it resumes when you start it again).

## Check progress (any time, in a second terminal)

    python -m nowcast.flows.backfill status
    python -m nowcast.flows.backfill quicklook --time 2026-08-15T06:00

Log file: `data/logs/backfill.log`. Per-day record: `data/backfill_state.json`.
Quicklook PNGs: `data/quicklook/`.

## Measured on the first two days (2026-10-26, 2026-10-27)

| Item | Value |
|---|---|
| Raw download per day | ~2.95 GB (deleted after conversion) |
| Archive per day | ~0.30 GB (inputs 0.295, labels 0.005) |
| Projected archive, 181 days | ~54 GB |
| Time per day | ~8.5 min at 4 parallel downloads |
| Projected total time | ~25–26 h |
| Frames found | inputs ~87/96 per day, cloud masks ~85/96 |

## What is in the archive

- `inputs.zarr`: tir1, tir2, mir, wv (brightness temperature, K), vis (albedo 0..1),
  swir (radiance); `satellite` per slot (0 none, 1 3DS, 2 3DR); `valid_fraction`.
- `labels.zarr`: `cmk` cloud mask (0 clear, 1 cloudy, 2 probably clear, 3 probably cloudy;
  NaN = missing); `satellite`.
- Missing or not-yet-processed slots read as NaN.

Open with:

    import xarray as xr
    inp = xr.open_zarr("data/inputs.zarr"); lab = xr.open_zarr("data/labels.zarr")

## If something goes wrong

| Symptom | Action |
|---|---|
| "not enough free disk" | Free space, run `run_backfill.bat` again |
| Same day fails repeatedly in the log | Note the date; continue; report it in the next session |
| MOSDAC login error (401 after refresh) | Check `.env` credentials, run again |
| Want to start over | Delete `data\inputs.zarr`, `data\labels.zarr`, `data\backfill_state.json` |

## Known data notes for Phase 3
- Cloud mask flags parts of snow-covered Himalaya/Tibet as cloudy; evaluate that region separately.
- MOSDAC daily quota: 5000 downloads per account per day (HTTP 429, `"type":"daily_limit"`). A full data day is about 190 files, so expect about 26 data days per calendar day. On this response all downloads pause until 00:05 IST (re-checking at least hourly) and the same day continues, reusing finished files. The reset time is inferred from the log, not documented.
- Other 429s pause all threads (60 s doubling to 10 min). If a day is still limited after an hour it is not written; the runner waits 10 min and redoes it (up to 6 times).
- MOSDAC answers HTTP 500 `Data unavailable for given parameters` when a product has no granules for a query. This is treated as "no files": that day is built from the other satellite, so `inputs`/`labels` are lower. INSAT-3DS has such gaps from about 2026-07-25 to 2026-08-18.
- Occasional `IncompleteRead` failures (a broken connection) still leave single slots missing after 4 attempts; that is expected and harmless.
- Nightly gap around 17:15–20:15 UTC on sampled days (both satellites); check across the window.
