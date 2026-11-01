"""Zarr archive layout: data/inputs.zarr and data/labels.zarr.

Both share one time axis (15-min UTC slots) and the India grid. The full time axis is
created up front as a lazy template; each processed day is then written into its own
region. A day is 96 slots = 6 chunks of 16; each 16-slot block is written as whole chunks, so
writes never touch a neighbouring block and re-running a day is idempotent.

Encoding: physical values as uint16 with CF scale_factor/add_offset; 65535 = missing.
  tir1, tir2, mir, wv  K         scale 0.01, offset 150   (0.01 K precision)
  vis                  albedo    scale 1e-4               (fraction 0..1)
  swir                 radiance  scale 1e-3               (mW cm-2 sr-1 um-1)
  cmk (labels)         uint8 class 0..3, 255 = missing (decoded as NaN by xarray)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import dask.array as da
import numpy as np
import pandas as pd
import xarray as xr

from nowcast.process.regrid import target_grid

SLOTS_PER_DAY = 96
T_CHUNK = 16
XY_CHUNK = 200
U16_FILL = 65535
CMK_MISSING = 255

INPUT_ENCODING = {
    "tir1": {"scale_factor": 0.01, "add_offset": 150.0},
    "tir2": {"scale_factor": 0.01, "add_offset": 150.0},
    "mir": {"scale_factor": 0.01, "add_offset": 150.0},
    "wv": {"scale_factor": 0.01, "add_offset": 150.0},
    "vis": {"scale_factor": 1e-4, "add_offset": 0.0},
    "swir": {"scale_factor": 1e-3, "add_offset": 0.0},
}
UNITS = {"tir1": "K", "tir2": "K", "mir": "K", "wv": "K", "vis": "1", "swir": "mW cm-2 sr-1 um-1"}


def time_axis(start: date, end: date) -> pd.DatetimeIndex:
    return pd.date_range(datetime(start.year, start.month, start.day),
                         datetime(end.year, end.month, end.day) + timedelta(minutes=15 * (SLOTS_PER_DAY - 1)),
                         freq="15min")


def _encoding_inputs() -> dict:
    enc = {}
    for v, e in INPUT_ENCODING.items():
        enc[v] = {**e, "dtype": "uint16", "_FillValue": U16_FILL, "chunks": (T_CHUNK, XY_CHUNK, XY_CHUNK)}
    enc["satellite"] = {"chunks": (T_CHUNK,)}
    enc["valid_fraction"] = {"chunks": (T_CHUNK,)}
    return enc


def create_stores(inputs: Path, labels: Path, start: date, end: date) -> None:
    """Write empty templates covering [start, end] (metadata only, no pixel data)."""
    grid = target_grid()
    times = time_axis(start, end)
    nt, (ny, nx) = times.size, grid.shape
    coords = {"time": times, "lat": grid.lat, "lon": grid.lon}
    big = lambda dtype: da.zeros((nt, ny, nx), dtype=dtype, chunks=(T_CHUNK, XY_CHUNK, XY_CHUNK))  # noqa: E731
    small = lambda dtype: da.zeros((nt,), dtype=dtype, chunks=(T_CHUNK,))  # noqa: E731

    ds = xr.Dataset(
        {v: (("time", "lat", "lon"), big(np.float32), {"units": UNITS[v]}) for v in INPUT_ENCODING}
        | {
            "satellite": (("time",), small(np.uint8), {"flag_values": [0, 1, 2], "flag_meanings": "none INSAT-3DS INSAT-3DR"}),
            "valid_fraction": (("time",), small(np.float32), {"long_name": "fraction of India grid with valid TIR1"}),
        },
        coords=coords,
        attrs={"title": "INSAT-3DS/3DR L1C_ASIA_MER on 0.04 deg India grid", "source": "MOSDAC", "time_zone": "UTC"},
    )
    ds.to_zarr(inputs, mode="w", compute=False, encoding=_encoding_inputs())

    lab = xr.Dataset(
        {
            "cmk": (("time", "lat", "lon"), big(np.uint8),
                    {"flag_values": [0, 1, 2, 3], "flag_meanings": "clear cloudy probably_clear probably_cloudy"}),
            "satellite": (("time",), small(np.uint8), {"flag_values": [0, 1, 2], "flag_meanings": "none INSAT-3DS INSAT-3DR"}),
        },
        coords=coords,
        attrs={"title": "INSAT-3DS/3DR L2B_CMK cloud mask on 0.04 deg India grid", "source": "MOSDAC", "time_zone": "UTC"},
    )
    lab.to_zarr(labels, mode="w", compute=False, encoding={
        # Fill 255 = missing, so unwritten or absent slots can never read as 0 = clear.
        "cmk": {"dtype": "uint8", "chunks": (T_CHUNK, XY_CHUNK, XY_CHUNK), "_FillValue": CMK_MISSING},
        "satellite": {"chunks": (T_CHUNK,)},
    })
    # xarray stores the CF _FillValue only as an attribute and leaves the Zarr array
    # fill_value at 0, so chunks never written would read back as 150 K / "clear".
    # Make the store-level fill equal the missing marker.
    for var in INPUT_ENCODING:
        _set_zarr_fill(inputs / var, U16_FILL)
    _set_zarr_fill(labels / "cmk", CMK_MISSING)


def _set_zarr_fill(array_dir: Path, value: int) -> None:
    """Set fill_value in the array's zarr.json and in the root's consolidated copy."""
    for meta_path, key in ((array_dir / "zarr.json", None), (array_dir.parent / "zarr.json", array_dir.name)):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if key is None:
            meta["fill_value"] = value
        elif meta.get("consolidated_metadata"):
            meta["consolidated_metadata"]["metadata"][key]["fill_value"] = value
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def write_block(inputs: Path, labels: Path, start: int, times: pd.DatetimeIndex,
                chans: dict[str, np.ndarray], sat_in: np.ndarray, valid_fraction: np.ndarray,
                cmk: np.ndarray, sat_lab: np.ndarray) -> None:
    """Write one chunk-aligned block of T_CHUNK slots starting at time index `start`."""
    if start % T_CHUNK or len(times) != T_CHUNK:
        raise ValueError("blocks must be chunk-aligned and exactly T_CHUNK long")
    region = {"time": slice(start, start + T_CHUNK)}
    ds = xr.Dataset(
        {v: (("time", "lat", "lon"), chans[v]) for v in INPUT_ENCODING}
        | {"satellite": (("time",), sat_in), "valid_fraction": (("time",), valid_fraction)},
        coords={"time": times},
    )
    ds.to_zarr(inputs, region=region)
    lab = xr.Dataset({"cmk": (("time", "lat", "lon"), cmk), "satellite": (("time",), sat_lab)},
                     coords={"time": times})
    lab.to_zarr(labels, region=region)
