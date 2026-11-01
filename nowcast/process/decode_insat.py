"""Decode INSAT-3DS / 3DR HDF5 granules into physical arrays.

Layouts verified against real files (docs/h5_structure/):
  *_L1C_ASIA_MER: 6 channels as 10-bit counts, shape (1, 1616, 1737), Mercator grid with
                  X/Y coordinates in metres; lookup tables map counts to physical values.
  *_L2B_CMK:      cloud mask int8 (0 clear, 1 cloudy, 2 probably clear, 3 probably cloudy,
                  fill 9) on the full-disk grid, with Latitude/Longitude int16 x 0.01.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import h5py
import numpy as np

# archive variable -> (count dataset, lookup table, scale applied to LUT values)
SECTOR_CHANNELS = {
    "vis": ("IMG_VIS", "IMG_VIS_ALBEDO", 0.01),        # albedo % -> fraction 0..1
    "swir": ("IMG_SWIR", "IMG_SWIR_RADIANCE", 1.0),    # radiance (3DR has no SWIR albedo LUT)
    "mir": ("IMG_MIR", "IMG_MIR_TEMP", 1.0),           # brightness temperature K
    "wv": ("IMG_WV", "IMG_WV_TEMP", 1.0),
    "tir1": ("IMG_TIR1", "IMG_TIR1_TEMP", 1.0),
    "tir2": ("IMG_TIR2", "IMG_TIR2_TEMP", 1.0),
}
CMK_FILL = 9
_NAME_RE = re.compile(r"^(3[SR])IMG_(\d{2}[A-Z]{3}\d{4})_(\d{4})_")
SATELLITE_CODE = {"3S": 1, "3R": 2}  # 0 = no data


def slot_from_filename(filename: str) -> tuple[str, datetime]:
    """'3RIMG_27OCT2026_0615_L1C...' -> ('3R', 2026-10-27 06:15 UTC)."""
    m = _NAME_RE.match(filename)
    if not m:
        raise ValueError(f"unexpected INSAT filename: {filename}")
    t = datetime.strptime(m.group(2) + m.group(3), "%d%b%Y%H%M").replace(tzinfo=timezone.utc)
    return m.group(1), t


@dataclass
class Sector:
    channels: dict[str, np.ndarray]  # float32, NaN where missing, shape (ny, nx)
    x: np.ndarray                    # metres, Mercator
    y: np.ndarray


def read_sector(path) -> Sector:
    out: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as f:
        for name, (count_ds, lut_ds, scale) in SECTOR_CHANNELS.items():
            counts = f[count_ds][0].astype(np.int32)
            fill = int(np.asarray(f[count_ds].attrs.get("_FillValue", [-1])).ravel()[0])
            lut = f[lut_ds][:].astype(np.float32) * scale
            lut_fill = f[lut_ds].attrs.get("_FillValue")
            if lut_fill is not None:
                lut[lut == np.float32(np.asarray(lut_fill).ravel()[0]) * scale] = np.nan
            counts = np.clip(counts, 0, lut.size - 1)
            arr = lut[counts]
            arr[f[count_ds][0] == fill] = np.nan
            out[name] = arr
        x = f["X"][:]
        y = f["Y"][:]
    return Sector(out, x, y)


@dataclass
class CloudMask:
    cmk: np.ndarray  # int8, CMK_FILL where missing
    lat: np.ndarray  # float32 degrees, NaN where missing
    lon: np.ndarray


def read_cmk(path) -> CloudMask:
    with h5py.File(path, "r") as f:
        cmk = f["CMK"][0].astype(np.int8)
        lat_raw = f["Latitude"][:]
        lon_raw = f["Longitude"][:]
        lat_scale = float(np.asarray(f["Latitude"].attrs.get("scale_factor", [0.01])).ravel()[0])
        lon_scale = float(np.asarray(f["Longitude"].attrs.get("scale_factor", [0.01])).ravel()[0])
    lat = lat_raw.astype(np.float32) * lat_scale
    lon = lon_raw.astype(np.float32) * lon_scale
    lat[lat_raw == 32767] = np.nan
    lon[lon_raw == 32767] = np.nan
    return CloudMask(cmk, lat, lon)
