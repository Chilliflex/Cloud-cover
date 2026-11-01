import json
from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path

import h5py
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
H5_FOLDER = ROOT_DIR / "h5-data"
PUBLIC_FOLDER = ROOT_DIR / "public"
PUBLIC_FOLDER.mkdir(parents=True, exist_ok=True)


def find_latest_h5_file() -> Path:
    files = sorted(H5_FOLDER.glob("*.h5"))
    if not files:
        raise FileNotFoundError("No H5 files found in h5-data")
    return files[-1]


def load_channel_temperature(h5: h5py.File, data_key: str, lut_key: str) -> np.ndarray:
    counts = np.array(h5[data_key])[0]
    lut = np.array(h5[lut_key])
    temp = lut[counts].astype(np.float32)
    temp[(temp < 180) | (temp > 330)] = np.nan
    return temp


def compute_background(temperature: np.ndarray) -> np.ndarray:
    try:
        from scipy.ndimage import gaussian_filter, maximum_filter

        background = maximum_filter(temperature.astype(np.float32), size=50)
        return np.clip(gaussian_filter(background, sigma=8).astype(np.float32), 285, 318)
    except ImportError:
        return np.full_like(temperature, 305.0, dtype=np.float32)


def compute_cloud_fraction(
    temperature: np.ndarray,
    btd_11_12: np.ndarray,
    bg_temp: np.ndarray,
    wv_temp: np.ndarray,
) -> np.ndarray:
    cf = np.zeros_like(temperature, dtype=np.float32)

    _mask = temperature < 230
    cf = np.where(_mask, np.clip(90 + (230 - temperature) * 0.5, 90, 100), cf)

    _mask = (temperature >= 230) & (temperature < 250)
    cf = np.where(_mask, np.clip(65 + (250 - temperature) * 1.25, 65, 90), cf)

    T_MID_REF = 245
    _mask = (temperature >= 250) & (temperature < 270)
    _raw = (bg_temp - temperature) / np.maximum(bg_temp - T_MID_REF, 1.0)
    cf = np.where(_mask, np.clip(_raw * 75, 15, 65), cf)

    T_LOW_REF = 260
    _mask = (temperature >= 270) & (temperature < 305)
    _raw = (bg_temp - temperature) / np.maximum(bg_temp - T_LOW_REF, 1.0)
    boost = np.where(btd_11_12 < 1.0, 1.3, 1.0)
    cf = np.where(_mask, np.clip(_raw * 45 * boost, 0, 35), cf)

    cirrus_mask = (btd_11_12 > 1.5) & (temperature < 260)
    cf = np.where(cirrus_mask, np.clip(cf + np.minimum(btd_11_12 * 6, 22), 0, 88), cf)

    wv_boost = np.clip(245 - wv_temp, 0, 20)
    cf += wv_boost

    clear_mask = (temperature > 300) & (btd_11_12 > 0.5) & (btd_11_12 < 2.5)
    cf = np.where(clear_mask, np.minimum(cf, 8), cf)

    try:
        from scipy.ndimage import gaussian_filter

        cf = gaussian_filter(cf, sigma=1.5)
    except ImportError:
        pass

    return np.clip(cf, 0, 100).astype(np.float32)


def build_alerts(lat: np.ndarray, lon: np.ndarray, temperature: np.ndarray, storm_mask: np.ndarray) -> list[dict]:
    rows, cols = np.where(storm_mask)
    alerts = []
    for r, c in zip(rows, cols):
        alerts.append(
            {
                "lat": float(lat[r, c]),
                "lon": float(lon[r, c]),
                "temp": float(temperature[r, c]),
            }
        )
    return alerts


def cluster_alerts(alerts: list[dict]) -> list[dict]:
    clusters = defaultdict(list)
    for alert in alerts:
        lat_key = round(alert["lat"] / 0.5) * 0.5
        lon_key = round(alert["lon"] / 0.5) * 0.5
        clusters[(lat_key, lon_key)].append(alert)

    storm_cells = []
    for group in clusters.values():
        if len(group) < 5:
            continue

        coldest = min(group, key=lambda x: x["temp"])
        severity = (
            "Severe"
            if coldest["temp"] < 190
            else "Strong"
            if coldest["temp"] < 195
            else "Moderate"
        )

        storm_cells.append(
            {
                "lat": coldest["lat"],
                "lon": coldest["lon"],
                "temp": coldest["temp"],
                "count": len(group),
                "severity": severity,
                "radius_km": round(np.sqrt(len(group)) * 2),
                "updated": datetime.now(UTC).strftime("%d-%b-%Y %H:%M UTC"),
            }
        )

    return storm_cells


def build_cloud_grid(lat: np.ndarray, lon: np.ndarray, cloud_cover_pct: np.ndarray, temperature: np.ndarray, earth_mask: np.ndarray, india_mask: np.ndarray) -> list[dict]:
    grid_size_km = 12
    grid_deg = grid_size_km / 111.0
    cloud_grids: dict[tuple[float, float], list[dict]] = defaultdict(list)

    for r in range(0, temperature.shape[0], 4):
        for c in range(0, temperature.shape[1], 4):
            if not earth_mask[r, c] or not india_mask[r, c]:
                continue

            grid_lat = round(lat[r, c] / grid_deg) * grid_deg
            grid_lon = round(lon[r, c] / grid_deg) * grid_deg
            cloud_grids[(round(grid_lat, 4), round(grid_lon, 4))].append(
                {"cc": float(cloud_cover_pct[r, c]), "temp": float(temperature[r, c])}
            )

    cloud_grid = []
    for (grid_lat, grid_lon), pixels in cloud_grids.items():
        avg_cc = np.mean([p["cc"] for p in pixels])
        avg_temp = np.mean([p["temp"] for p in pixels])
        cloud_grid.append(
            {
                "gridLat": round(grid_lat, 4),
                "gridLon": round(grid_lon, 4),
                "cloudCover": int(round(avg_cc)),
                "temp": int(round(avg_temp)),
            }
        )
    return cloud_grid


def save_json(data, path: Path, indent: int | None = None) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=indent)


def main() -> None:
    latest_file = find_latest_h5_file()
    print("\nUsing latest file:", latest_file.name)

    with h5py.File(latest_file, "r") as h5:
        temperature = load_channel_temperature(h5, "IMG_TIR1", "IMG_TIR1_TEMP")
        tir2_temp = load_channel_temperature(h5, "IMG_TIR2", "IMG_TIR2_TEMP")
        wv_temp = load_channel_temperature(h5, "IMG_WV", "IMG_WV_TEMP")

        btd_11_12 = temperature - tir2_temp
        bg_temp = compute_background(temperature)
        cloud_cover_pct = compute_cloud_fraction(temperature, btd_11_12, bg_temp, wv_temp)

        lat = np.array(h5["Latitude"]) * 0.01
        lon = np.array(h5["Longitude"]) * 0.01

        earth_mask = (
            (lat > -90) & (lat < 90) & (lon > 0) & (lon < 180)
        )
        india_mask = (
            (lat >= 5) & (lat <= 38) & (lon >= 65) & (lon <= 98)
        )

        storm_mask = (
            (temperature < 214)
            & (temperature > 180)
            & (wv_temp < 240)
            & earth_mask
            & india_mask
        )

        storm_pixels = np.sum(storm_mask)
        print("\nIndia Storm Pixels:", storm_pixels)

        alerts = build_alerts(lat, lon, temperature, storm_mask)
        print("\nTotal Alerts:", len(alerts))

        storm_cells = cluster_alerts(alerts)
        print("\nStorm Cells:", len(storm_cells))

        cloud_grid = build_cloud_grid(lat, lon, cloud_cover_pct, temperature, earth_mask, india_mask)
        print("Unique grids:", len(cloud_grid))
        print("Cloud grid records:", len(cloud_grid))

        save_json(cloud_grid, PUBLIC_FOLDER / "cloud-grid.json")
        print("Saved cloud-grid.json:", len(cloud_grid), "points")

        save_json(storm_cells, PUBLIC_FOLDER / "thunderstorm-cells.json", indent=2)
        print("\nSaved thunderstorm-cells.json")

        temperature = np.nan_to_num(temperature)
        print("Saved JSON:", len(storm_cells))


if __name__ == "__main__":
    main()
