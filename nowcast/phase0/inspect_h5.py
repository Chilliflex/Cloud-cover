"""Phase 0: download one real granule per key product and record its HDF5 structure.

Requires MOSDAC_USERNAME / MOSDAC_PASSWORD in .env. Writes one text dump per file to
docs/h5_structure/ and deletes the raw file afterwards unless --keep is given.

    python -m nowcast.phase0.inspect_h5                 # Asia sector + cloud mask (~33 MB)
    python -m nowcast.phase0.inspect_h5 --with-l1b      # also one full-disk L1B (~410 MB)
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import h5py
import numpy as np

from nowcast.ingest.mosdac import MosdacClient
from nowcast.settings import DOCS_DIR, RAW_CACHE_DIR

# Same slot for both products so label and input can be compared directly.
SAMPLE_DAY = date(2026, 10, 27)
BASE_PRODUCTS = ["3RIMG_L1C_ASIA_MER", "3RIMG_L2B_CMK", "3SIMG_L1C_ASIA_MER", "3SIMG_L2B_CMK"]
L1B_PRODUCTS = ["3RIMG_L1B_STD"]
MAX_ATTR_LEN = 200


def _attr(v) -> str:
    if isinstance(v, bytes):
        v = v.decode(errors="replace")
    if isinstance(v, np.ndarray) and v.size > 8:
        return f"array{v.shape} {v.dtype}"
    s = str(v.tolist() if isinstance(v, np.ndarray) else v)
    return s if len(s) <= MAX_ATTR_LEN else s[:MAX_ATTR_LEN] + "..."


def _stats(ds: h5py.Dataset) -> str:
    """Min/max/fill summary for numeric datasets, read on a strided sample to stay fast."""
    if ds.dtype.kind not in "iuf" or ds.size == 0:
        return ""
    step = max(1, int((ds.size / 2e6) ** (1 / max(ds.ndim, 1))))
    sample = ds[tuple(slice(None, None, step) for _ in range(ds.ndim))]
    fill = ds.attrs.get("_FillValue")
    arr = np.asarray(sample).astype("float64").ravel()
    if fill is not None:
        arr = arr[arr != np.asarray(fill).ravel()[0]]
    arr = arr[np.isfinite(arr)]
    if not arr.size:
        return "  all fill"
    uniq = np.unique(arr)
    extra = f" values={uniq.astype(int).tolist()}" if uniq.size <= 12 else ""
    return f"  min={arr.min():.4g} max={arr.max():.4g}{extra}"


def dump(path: Path) -> str:
    lines = [f"# {path.name}", f"size: {path.stat().st_size / 1e6:.1f} MB", ""]
    with h5py.File(path, "r") as f:
        lines.append("## root attributes")
        lines += [f"  {k} = {_attr(v)}" for k, v in f.attrs.items()]
        lines += ["", "## datasets"]

        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                lines.append(f"{name}  shape={obj.shape} dtype={obj.dtype}{_stats(obj)}")
                for k, v in obj.attrs.items():
                    lines.append(f"    @{k} = {_attr(v)}")

        f.visititems(visit)
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-l1b", action="store_true", help="also fetch one ~410 MB full-disk L1B file")
    ap.add_argument("--keep", action="store_true", help="keep the downloaded raw files")
    args = ap.parse_args()

    client = MosdacClient()
    out_dir = DOCS_DIR / "h5_structure"
    out_dir.mkdir(parents=True, exist_ok=True)
    products = BASE_PRODUCTS + (L1B_PRODUCTS if args.with_l1b else [])

    for ds_id in products:
        res = client.search(ds_id, SAMPLE_DAY, SAMPLE_DAY, count=50)
        # Prefer a daytime slot near 06:00 UTC so the visible channels hold data.
        granule = min(res.granules, key=lambda g: abs(g.start.hour * 60 + g.start.minute - 360))
        print(f"{ds_id}: downloading {granule.filename}")
        path = client.download(granule, RAW_CACHE_DIR)
        text = dump(path)
        (out_dir / f"{path.stem}.txt").write_text(text, encoding="utf-8")
        print(f"  wrote {out_dir / (path.stem + '.txt')}")
        if not args.keep:
            path.unlink()


if __name__ == "__main__":
    main()
