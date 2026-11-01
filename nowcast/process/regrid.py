"""Map INSAT grids onto the fixed India grid (nowcast/config/grid.yaml).

Nearest-neighbour throughout: source pixels are ~4 km and the target is 0.04 deg (~4.4 km),
so nearest keeps true observed values and fill semantics (no smearing across cloud edges
or into missing areas).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial import cKDTree

from nowcast.settings import CONFIG_DIR

# Mercator parameters of *_L1C_ASIA_MER (Projection_Information); verified against the
# file's corner coordinates to < 1 mm.
_A, _B = 6378137.0, 6356752.3142
_E = np.sqrt(1 - (_B / _A) ** 2)
_LAT_TS = np.radians(17.75)
_LON0 = 77.25
_K0 = np.cos(_LAT_TS) / np.sqrt(1 - _E**2 * np.sin(_LAT_TS) ** 2)


@dataclass(frozen=True)
class Grid:
    lat: np.ndarray  # (ny,) north to south, cell centres
    lon: np.ndarray  # (nx,) west to east

    @property
    def shape(self) -> tuple[int, int]:
        return self.lat.size, self.lon.size


@lru_cache(maxsize=1)
def target_grid() -> Grid:
    g = yaml.safe_load((CONFIG_DIR / "grid.yaml").read_text(encoding="utf-8"))
    r = g["resolution_deg"]
    lat = np.round(g["lat_max"] - r / 2 - r * np.arange(g["ny"]), 4)
    lon = np.round(g["lon_min"] + r / 2 + r * np.arange(g["nx"]), 4)
    return Grid(lat, lon)


def mercator_xy(lat_deg: np.ndarray, lon_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    phi = np.radians(lat_deg)
    x = _A * _K0 * np.radians(lon_deg - _LON0)
    es = _E * np.sin(phi)
    y = _A * _K0 * np.log(np.tan(np.pi / 4 + phi / 2) * ((1 - es) / (1 + es)) ** (_E / 2))
    return x, y


class SectorRegridder:
    """Index from the Mercator sector grid to the India grid, built once per X/Y layout."""

    def __init__(self, x: np.ndarray, y: np.ndarray, grid: Grid | None = None):
        grid = grid or target_grid()
        lon2, lat2 = np.meshgrid(grid.lon, grid.lat)
        tx, ty = mercator_xy(lat2, lon2)
        col = np.rint((tx - x[0]) / (x[1] - x[0])).astype(np.int64)
        row = np.rint((ty - y[0]) / (y[1] - y[0])).astype(np.int64)
        self.valid = (col >= 0) & (col < x.size) & (row >= 0) & (row < y.size)
        self.row = np.where(self.valid, row, 0)
        self.col = np.where(self.valid, col, 0)
        self.key = (x.size, y.size, float(x[0]), float(y[0]))

    def __call__(self, arr: np.ndarray) -> np.ndarray:
        out = arr[self.row, self.col].astype(np.float32)
        out[~self.valid] = np.nan
        return out


class SwathRegridder:
    """Index from a full-disk lat/lon swath (cloud mask) to the India grid.

    Build is a KD-tree over ~1.5 M pixels (~10 s); the result is cached on disk per
    satellite and reused while the lat/lon arrays are unchanged (checked by hash).
    """

    MAX_DIST_DEG = 0.06  # farther than this from any source pixel -> missing

    def __init__(self, lat: np.ndarray, lon: np.ndarray, cache: Path, grid: Grid | None = None):
        grid = grid or target_grid()
        digest = hashlib.sha1(np.ascontiguousarray(lat[::7, ::7]).tobytes()
                              + np.ascontiguousarray(lon[::7, ::7]).tobytes()).hexdigest()
        if cache.exists():
            z = np.load(cache)
            if str(z["digest"]) == digest:
                self.flat, self.valid = z["flat"], z["valid"]
                return
        m = (np.isfinite(lat) & np.isfinite(lon)
             & (lat > grid.lat.min() - 1) & (lat < grid.lat.max() + 1)
             & (lon > grid.lon.min() - 1) & (lon < grid.lon.max() + 1))
        src_flat = np.flatnonzero(m)
        tree = cKDTree(np.column_stack([lat.ravel()[src_flat], lon.ravel()[src_flat]]))
        lon2, lat2 = np.meshgrid(grid.lon, grid.lat)
        dist, idx = tree.query(np.column_stack([lat2.ravel(), lon2.ravel()]), workers=-1)
        self.valid = (dist <= self.MAX_DIST_DEG).reshape(grid.shape)
        self.flat = src_flat[np.where(np.isfinite(dist), idx, 0)].reshape(grid.shape)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, flat=self.flat, valid=self.valid, digest=digest)

    def __call__(self, arr: np.ndarray, fill) -> np.ndarray:
        out = arr.ravel()[self.flat]
        out[~self.valid] = fill
        return out
