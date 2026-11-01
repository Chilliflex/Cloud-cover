"""Phase 0: query the MOSDAC catalogue and record what our account can use.

Writes nowcast/config/products.yaml (machine-readable) and docs/products_report.md.
Anonymous; no credentials required.

    python -m nowcast.phase0.catalogue
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

import requests
import yaml

from nowcast.ingest.mosdac import MosdacClient
from nowcast.settings import CONFIG_DIR, DOCS_DIR, free_gb

SATELLITES = {"3S": "INSAT-3DS", "3R": "INSAT-3DR"}
# Products relevant to Goal 1 (cloud nowcast) and Goal 2 (solar).
PRODUCTS = {
    "L1B_STD": "Level 1B full disk, 6 channels, satellite projection",
    "L1C_ASIA_MER": "Level 1C Asia sector, Mercator projection",
    "L2B_CMK": "Level 2 cloud mask (label)",
    "L2B_CTP": "Level 2 cloud top pressure / temperature",
    "L2C_FOG": "Level 2 fog flag (winter IGP check)",
    "L2C_INS": "Level 2 surface insolation (Goal 2)",
    "L2P_AMV": "Level 2 atmospheric motion vectors (motion cross-check)",
}
WINDOW_START = date(2026, 5, 1)
SAMPLE_DAY = date(2026, 10, 27)
SLOTS_PER_DAY = 48  # per satellite, half-hourly


def describe(client: MosdacClient, dataset_id: str, window_end: date) -> dict:
    try:
        all_ = client.search(dataset_id)
    except requests.HTTPError as exc:
        return {"available": False, "error": str(exc)[:120]}
    if not all_.total:
        return {"available": False}
    newest = all_.granules[0] if all_.granules else None
    oldest = client.oldest(dataset_id)
    window = client.search(dataset_id, WINDOW_START, window_end)
    day = client.search(dataset_id, SAMPLE_DAY, SAMPLE_DAY, count=50)
    minutes = sorted(Counter(g.start.minute for g in day.granules if g.start))
    n_days = (window_end - WINDOW_START).days + 1
    return {
        "available": True,
        "archive_files": all_.total,
        "archive_gb": round(all_.total_mb / 1000, 1),
        "mean_file_mb": round(all_.mean_mb, 1),
        "oldest": oldest.start.isoformat() if oldest and oldest.start else None,
        "newest": newest.start.isoformat() if newest and newest.start else None,
        "filename_example": newest.filename if newest else None,
        "slot_minutes_utc": minutes,
        "window": {
            "start": WINDOW_START.isoformat(),
            "end": window_end.isoformat(),
            "files": window.total,
            "gb": round(window.total_mb / 1000, 1),
            "completeness": round(window.total / (n_days * SLOTS_PER_DAY), 3),
        },
    }


def build() -> dict:
    client = MosdacClient()
    window_end = datetime.now(timezone.utc).date() - timedelta(days=1)
    out: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": WINDOW_START.isoformat(), "end": window_end.isoformat()},
        "satellites": {},
    }
    for prefix, name in SATELLITES.items():
        out["satellites"][name] = {
            "collections": client.collections(name),
            "products": {},
        }
        for suffix, desc in PRODUCTS.items():
            ds = f"{prefix}IMG_{suffix}"
            info = describe(client, ds, window_end)
            info["description"] = desc
            out["satellites"][name]["products"][ds] = info
            print(f"{ds:24s} {'ok' if info['available'] else 'missing'}")
    return out


def _fmt(v, suffix=""):
    return "n/a" if v is None else f"{v}{suffix}"


def report(cat: dict) -> str:
    w = cat["window"]
    lines = [
        "# MOSDAC Products Report (Phase 0)",
        "",
        f"Generated {cat['generated_utc']} from the anonymous MOSDAC catalogue "
        "(`https://mosdac.gov.in/apios/datasets.json`). Machine-readable copy: `nowcast/config/products.yaml`.",
        "",
        f"Backfill window: {w['start']} to {w['end']}. Completeness = files found / (days x 48 half-hourly slots).",
        "",
        "| Dataset ID | Description | Mean file | Slots (UTC min) | Archive since | Window files | Window GB | Completeness |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for sat in cat["satellites"].values():
        for ds, p in sat["products"].items():
            if not p["available"]:
                lines.append(f"| `{ds}` | {p['description']} | not available | | | | | |")
                continue
            lines.append(
                f"| `{ds}` | {p['description']} | {p['mean_file_mb']} MB | "
                f"{', '.join(f':{m:02d}' for m in p['slot_minutes_utc'])} | {_fmt(p['oldest'], '')[:10]} | "
                f"{p['window']['files']} | {p['window']['gb']} | {p['window']['completeness']:.0%} |"
            )
    lines += ["", "## Filename examples", ""]
    for sat in cat["satellites"].values():
        for ds, p in sat["products"].items():
            if p["available"]:
                lines.append(f"- `{p['filename_example']}`")

    # Backfill budget for the two candidate input routes.
    def window_gb(ids):
        return sum(
            cat["satellites"][s]["products"][i]["window"]["gb"]
            for s in cat["satellites"]
            for i in ids
            if cat["satellites"][s]["products"].get(i, {}).get("available")
        )

    l1b = window_gb(["3SIMG_L1B_STD", "3RIMG_L1B_STD"])
    mer = window_gb(["3SIMG_L1C_ASIA_MER", "3RIMG_L1C_ASIA_MER"])
    cmk = window_gb(["3SIMG_L2B_CMK", "3RIMG_L2B_CMK"])
    lines += [
        "",
        "## Download volume for the backfill window (streamed, then deleted)",
        "",
        "| Route | Inputs GB | Cloud mask GB | Total GB to download |",
        "|---|---|---|---|",
        f"| Full disk L1B_STD + CMK | {l1b:.0f} | {cmk:.0f} | {l1b + cmk:.0f} |",
        f"| Asia sector L1C_ASIA_MER + CMK | {mer:.0f} | {cmk:.0f} | {mer + cmk:.0f} |",
        "",
        f"Free disk at report time: {free_gb():.0f} GB.",
        "",
        "Open items, resolved by `python -m nowcast.phase0.inspect_h5` once credentials are set:",
        "channels and resolution inside L1C_ASIA_MER, cloud-mask class codes, lat/lon layout of L1B.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    cat = build()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "products.yaml").write_text(yaml.safe_dump(cat, sort_keys=False), encoding="utf-8")
    (DOCS_DIR / "products_report.md").write_text(report(cat), encoding="utf-8")
    print("wrote", CONFIG_DIR / "products.yaml", "and", DOCS_DIR / "products_report.md")


if __name__ == "__main__":
    main()
