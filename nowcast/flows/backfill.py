"""Phase 1 backfill: MOSDAC -> data/inputs.zarr + data/labels.zarr, unattended and resumable.

Per day: list granules -> download in parallel -> decode + regrid -> write 6 blocks of
16 slots -> delete raw files -> mark day done in data/backfill_state.json.
Stop any time (Ctrl+C, reboot, network loss); re-running the same command resumes at
the first unfinished day. Re-processing a day is safe (same archive region is rewritten).

    python -m nowcast.flows.backfill run                      # whole window in archive.yaml
    python -m nowcast.flows.backfill run --start 2026-10-27 --end 2026-10-27   # a subset
    python -m nowcast.flows.backfill status
    python -m nowcast.flows.backfill quicklook --time 2026-10-27T06:15
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

from nowcast.ingest.mosdac import DiskFullError, Granule, MosdacClient, RateLimitError
from nowcast.process import archive
from nowcast.process.decode_insat import CMK_FILL, SATELLITE_CODE, read_cmk, read_sector, slot_from_filename
from nowcast.process.regrid import SectorRegridder, SwathRegridder, target_grid
from nowcast.settings import CONFIG_DIR, DATA_DIR, MIN_FREE_GB, RAW_CACHE_DIR, free_gb

INPUTS = DATA_DIR / "inputs.zarr"
LABELS = DATA_DIR / "labels.zarr"
STATE = DATA_DIR / "backfill_state.json"
LOG_DIR = DATA_DIR / "logs"
STATIC = DATA_DIR / "static"
QUICKLOOK = DATA_DIR / "quicklook"

SECTOR_PRODUCTS = ["3SIMG_L1C_ASIA_MER", "3RIMG_L1C_ASIA_MER"]
CMK_PRODUCTS = ["3SIMG_L2B_CMK", "3RIMG_L2B_CMK"]
DAY_RAW_GB = 3.5  # upper bound of one day's raw download (measured ~2.9 GB)
RATE_LIMIT_DAY_PAUSE = 600  # seconds to wait before retrying a day that hit MOSDAC's rate limit
RATE_LIMIT_DAY_TRIES = 6    # retries of one day before moving on (it stays unfinished in the state)

log = logging.getLogger("backfill")
warnings.filterwarnings("ignore", message="Consolidated metadata", category=UserWarning)


# ---------------------------------------------------------------------------- state
def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"days": {}}


def save_state(state: dict) -> None:
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE)


def dir_size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9


# ---------------------------------------------------------------------------- one day
def list_day(client: MosdacClient, day: date) -> tuple[dict[int, Granule], dict[int, Granule]]:
    """Map slot index within the day (0..95) -> granule, for sector inputs and cloud masks."""
    def collect(products: list[str]) -> dict[int, Granule]:
        out: dict[int, Granule] = {}
        for ds in products:
            for g in client.list_all(ds, day, day):
                try:
                    _, t = slot_from_filename(g.filename)
                except ValueError:
                    continue
                if t.date() != day or t.minute % 15:
                    continue
                out.setdefault((t.hour * 60 + t.minute) // 15, g)
        return out
    return collect(SECTOR_PRODUCTS), collect(CMK_PRODUCTS)


def download_all(client: MosdacClient, granules: list[Granule], dest: Path, workers: int) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(client.download, g, dest): g for g in granules}
        for fut in as_completed(futures):
            g = futures[fut]
            try:
                paths[g.filename] = fut.result()
            except (DiskFullError, RateLimitError):
                # Let the remaining downloads finish (they are reused on retry), then fail the day.
                for other in futures:
                    other.cancel()
                raise
            except Exception as exc:  # one bad granule must not stop the day
                log.warning("download failed, slot left missing: %s (%s)", g.filename, exc)
    return paths


class DayProcessor:
    def __init__(self) -> None:
        self.grid = target_grid()
        self._sector: dict[tuple, SectorRegridder] = {}
        self._swath: dict[str, SwathRegridder] = {}

    def sector(self, path: Path) -> dict[str, np.ndarray]:
        sec = read_sector(path)
        key = (sec.x.size, sec.y.size, float(sec.x[0]), float(sec.y[0]))
        if key not in self._sector:
            self._sector[key] = SectorRegridder(sec.x, sec.y, self.grid)
        rg = self._sector[key]
        return {name: rg(arr) for name, arr in sec.channels.items()}

    def cmk(self, path: Path, sat: str) -> np.ndarray:
        cm = read_cmk(path)
        rg = SwathRegridder(cm.lat, cm.lon, STATIC / f"cmk_index_{sat}.npz", self.grid)
        out = rg(cm.cmk, CMK_FILL).astype(np.int16)
        out[(out < 0) | (out > 3)] = archive.CMK_MISSING
        return out.astype(np.uint8)


def process_day(day: date, client: MosdacClient, proc: DayProcessor, times: pd.DatetimeIndex,
                workers: int, keep_raw: bool) -> dict:
    t0 = time.time()
    sectors, masks = list_day(client, day)
    cache = RAW_CACHE_DIR / day.strftime("%Y%m%d")
    paths = download_all(client, list(sectors.values()) + list(masks.values()), cache, workers)
    t_dl = time.time() - t0
    raw_mb = sum(p.stat().st_size for p in paths.values()) / 1e6

    day_start = int(np.searchsorted(times.values, np.datetime64(datetime(day.year, day.month, day.day))))
    ny, nx = proc.grid.shape
    n_in = n_lab = 0
    for block in range(archive.SLOTS_PER_DAY // archive.T_CHUNK):
        slots = range(block * archive.T_CHUNK, (block + 1) * archive.T_CHUNK)
        chans = {v: np.full((archive.T_CHUNK, ny, nx), np.nan, np.float32) for v in archive.INPUT_ENCODING}
        sat_in = np.zeros(archive.T_CHUNK, np.uint8)
        vfrac = np.zeros(archive.T_CHUNK, np.float32)
        cmk = np.full((archive.T_CHUNK, ny, nx), archive.CMK_MISSING, np.uint8)
        sat_lab = np.zeros(archive.T_CHUNK, np.uint8)
        for i, slot in enumerate(slots):
            g = sectors.get(slot)
            if g and g.filename in paths:
                try:
                    data = proc.sector(paths[g.filename])
                    for v in chans:
                        chans[v][i] = data[v]
                    sat_in[i] = SATELLITE_CODE[slot_from_filename(g.filename)[0]]
                    vfrac[i] = float(np.isfinite(data["tir1"]).mean())
                    n_in += 1
                except Exception as exc:
                    log.warning("decode failed, slot left missing: %s (%s)", g.filename, exc)
            g = masks.get(slot)
            if g and g.filename in paths:
                try:
                    sat = slot_from_filename(g.filename)[0]
                    cmk[i] = proc.cmk(paths[g.filename], sat)
                    sat_lab[i] = SATELLITE_CODE[sat]
                    n_lab += 1
                except Exception as exc:
                    log.warning("decode failed, slot left missing: %s (%s)", g.filename, exc)
        start = day_start + block * archive.T_CHUNK
        archive.write_block(INPUTS, LABELS, start, times[start:start + archive.T_CHUNK],
                            chans, sat_in, vfrac, cmk, sat_lab)

    if not keep_raw:
        shutil.rmtree(cache, ignore_errors=True)
    return {"inputs": n_in, "labels": n_lab, "listed_inputs": len(sectors), "listed_labels": len(masks),
            "raw_mb": round(raw_mb), "download_s": round(t_dl), "total_s": round(time.time() - t0),
            "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")[:19]}


# ---------------------------------------------------------------------------- commands
def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_DIR / "backfill.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def archive_window() -> tuple[date, date]:
    cfg = yaml.safe_load((CONFIG_DIR / "archive.yaml").read_text(encoding="utf-8"))
    return date.fromisoformat(str(cfg["start"])), date.fromisoformat(str(cfg["end"]))


def ensure_stores(start: date, end: date) -> pd.DatetimeIndex:
    if not INPUTS.exists() or not LABELS.exists():
        a_start, a_end = archive_window()
        log.info("creating archive templates for %s .. %s (nowcast/config/archive.yaml)", a_start, a_end)
        archive.create_stores(INPUTS, LABELS, a_start, a_end)
    times = pd.DatetimeIndex(xr.open_zarr(INPUTS, consolidated=None)["time"].values)
    if times[0].date() > start or times[-1].date() < end:
        raise SystemExit(f"archive covers {times[0].date()}..{times[-1].date()}; requested {start}..{end}. "
                         "Use a range inside it, or move data/*.zarr away to start a new archive.")
    return times


def keep_awake() -> None:
    """Stop Windows from sleeping while this process runs (screen may still turn off)."""
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


# Exit codes, used by run_backfill.bat: 0 complete, 2 disk full (stop), 3 some days failed (retry).
EXIT_DONE, EXIT_DISK, EXIT_RETRY = 0, 2, 3


def cmd_run(args) -> None:
    setup_logging()
    keep_awake()
    a_start, a_end = archive_window()
    start = date.fromisoformat(args.start) if args.start else a_start
    end = date.fromisoformat(args.end) if args.end else a_end
    times = ensure_stores(start, end)
    state = load_state()
    days = [start + timedelta(d) for d in range((end - start).days + 1)]
    todo = [d for d in days if d.isoformat() not in state["days"]]
    log.info("backfill %s .. %s: %d days, %d done, %d to do, workers=%d",
             start, end, len(days), len(days) - len(todo), len(todo), args.workers)
    client, proc = MosdacClient(), DayProcessor()
    durations: list[float] = []
    failed: list[date] = []
    for n, day in enumerate(todo, 1):
        if free_gb(DATA_DIR) < MIN_FREE_GB + DAY_RAW_GB:
            log.error("stopping: %.1f GB free, need %.1f GB. Free space, then re-run to resume.",
                      free_gb(DATA_DIR), MIN_FREE_GB + DAY_RAW_GB)
            sys.exit(EXIT_DISK)
        info = None
        for rate_try in range(1, RATE_LIMIT_DAY_TRIES + 1):
            try:
                info = process_day(day, client, proc, times, args.workers, args.keep_raw)
                break
            except DiskFullError as exc:
                log.error("stopping: %s", exc)
                sys.exit(EXIT_DISK)
            except RateLimitError as exc:
                # Never write a day with slots lost to the rate limit; wait and redo the same day.
                log.warning("day %s hit MOSDAC rate limit (%s); pausing %d min, retry %d/%d",
                            day, exc, RATE_LIMIT_DAY_PAUSE // 60, rate_try, RATE_LIMIT_DAY_TRIES)
                time.sleep(RATE_LIMIT_DAY_PAUSE)
            except Exception as exc:
                log.exception("day %s failed (%s); it will be retried on the next run", day, exc)
                time.sleep(30)
                break
        if info is None:
            failed.append(day)
            continue
        state["days"][day.isoformat()] = info
        save_state(state)
        durations.append(info["total_s"])
        eta_h = np.mean(durations[-10:]) * (len(todo) - n) / 3600
        log.info("day %s done (%d/%d): inputs %d/96, labels %d/96, %d MB raw, %ds; free %.1f GB; ETA %.1f h",
                 day, n, len(todo), info["inputs"], info["labels"], info["raw_mb"], info["total_s"],
                 free_gb(DATA_DIR), eta_h)
    if failed:
        log.warning("%d day(s) failed and will be retried: %s", len(failed), ", ".join(map(str, failed)))
        sys.exit(EXIT_RETRY)
    log.info("backfill complete")


def cmd_status(_args) -> None:
    state = load_state()
    done = state["days"]
    if not INPUTS.exists():
        print("no archive yet; run: python -m nowcast.flows.backfill run --start ... --end ...")
        return
    times = pd.DatetimeIndex(xr.open_zarr(INPUTS, consolidated=None)["time"].values)
    total_days = (times[-1].date() - times[0].date()).days + 1
    gb_in, gb_lab = dir_size_gb(INPUTS), dir_size_gb(LABELS)
    n_in = sum(d["inputs"] for d in done.values())
    n_lab = sum(d["labels"] for d in done.values())
    per_day = (gb_in + gb_lab) / len(done) if done else 0
    print(f"window        {times[0].date()} .. {times[-1].date()} ({total_days} days)")
    print(f"days done     {len(done)} / {total_days}")
    if done:
        print(f"frames        inputs {n_in} ({n_in / (96 * len(done)):.0%}), labels {n_lab} ({n_lab / (96 * len(done)):.0%})")
        print(f"archive       inputs {gb_in:.2f} GB, labels {gb_lab:.3f} GB, {per_day:.3f} GB/day")
        print(f"projected     {per_day * total_days:.1f} GB for the full window")
        avg = np.mean([d["total_s"] for d in done.values()])
        print(f"speed         {avg / 60:.1f} min/day, remaining ~{avg * (total_days - len(done)) / 3600:.1f} h")
        print(f"last day      {max(done)} finished {done[max(done)]['finished_utc']} UTC")
    print(f"free disk     {free_gb(DATA_DIR):.1f} GB (stops below {MIN_FREE_GB + DAY_RAW_GB:.1f})")


def cmd_quicklook(args) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = np.datetime64(args.time)
    inp = xr.open_zarr(INPUTS, consolidated=None).sel(time=t)
    lab = xr.open_zarr(LABELS, consolidated=None).sel(time=t)
    fig, ax = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    ext = [float(inp.lon[0]), float(inp.lon[-1]), float(inp.lat[-1]), float(inp.lat[0])]
    im = ax[0].imshow(inp["tir1"], cmap="gray_r", vmin=190, vmax=310, extent=ext)
    fig.colorbar(im, ax=ax[0], label="TIR1 brightness temperature (K)")
    im = ax[1].imshow(inp["vis"], cmap="gray", vmin=0, vmax=1, extent=ext)
    fig.colorbar(im, ax=ax[1], label="VIS albedo")
    cm = lab["cmk"].values.astype(float)  # missing already NaN
    im = ax[2].imshow(cm, cmap=matplotlib.colors.ListedColormap(["#2b6cb0", "white", "#90cdf4", "#cbd5e0"]),
                      vmin=-0.5, vmax=3.5, extent=ext)
    cb = fig.colorbar(im, ax=ax[2], ticks=[0, 1, 2, 3])
    cb.ax.set_yticklabels(["clear", "cloudy", "prob. clear", "prob. cloudy"])
    sat = {0: "none", 1: "3DS", 2: "3DR"}
    ax[0].set_title(f"TIR1  {args.time} UTC  ({sat[int(inp['satellite'])]})")
    ax[1].set_title("VIS albedo")
    ax[2].set_title(f"Cloud mask ({sat[int(lab['satellite'])]})")
    QUICKLOOK.mkdir(parents=True, exist_ok=True)
    out = QUICKLOOK / f"{args.time.replace(':', '')}.png"
    fig.savefig(out, dpi=80)
    print("wrote", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="download and convert a date range (resumable)")
    r.add_argument("--start", help="first day, YYYY-MM-DD (UTC); default: archive.yaml start")
    r.add_argument("--end", help="last day, YYYY-MM-DD (UTC); default: archive.yaml end")
    r.add_argument("--workers", type=int, default=2,
                   help="parallel downloads (default 2)")
    r.add_argument("--keep-raw", action="store_true", help="do not delete raw HDF5 after conversion")
    r.set_defaults(func=cmd_run)
    s = sub.add_parser("status", help="progress, archive size and projection")
    s.set_defaults(func=cmd_status)
    q = sub.add_parser("quicklook", help="PNG of TIR1, VIS and cloud mask for one slot")
    q.add_argument("--time", required=True, help="slot time, e.g. 2026-10-27T06:15")
    q.set_defaults(func=cmd_quicklook)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
