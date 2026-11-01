"""Client for the MOSDAC OpenSearch catalogue and download API.

Catalogue endpoints (anonymous):
  https://mosdac.gov.in/apios/datasets.json     granules of one dataset, newest first
  https://mosdac.gov.in/apios/collections.json  dataset IDs per satellite
Download endpoints (login required):
  https://mosdac.gov.in/download_api/gettoken   POST {username, password} -> access_token
  https://mosdac.gov.in/download_api/download   GET ?id=<granule id>, Bearer token
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import h5py
import requests

from nowcast.settings import MIN_FREE_GB, free_gb, mosdac_credentials

BASE = "https://mosdac.gov.in"
DATASETS_URL = f"{BASE}/apios/datasets.json"
COLLECTIONS_URL = f"{BASE}/apios/collections.json"
TOKEN_URL = f"{BASE}/download_api/gettoken"
DOWNLOAD_URL = f"{BASE}/download_api/download"
MAX_COUNT = 50  # server limit per page
TIMEOUT = 120
RATE_LIMIT_FIRST_WAIT = 60   # seconds after the first HTTP 429, doubling each time
RATE_LIMIT_MAX_WAIT = 600    # cap per pause
RATE_LIMIT_GIVE_UP = 3600    # total seconds of 429 waiting per granule before raising
# Account quota: 5000 downloads/day. The reset time is not documented; the log suggests
# about midnight IST, so wake just after it and otherwise re-check once an hour.
QUOTA_PROBE_WAIT = 3600
IST = timezone(timedelta(hours=5, minutes=30))

log = logging.getLogger("backfill.mosdac")  # child of the runner's logger, so it reaches backfill.log


@dataclass(frozen=True)
class Granule:
    id: str
    filename: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class SearchResult:
    total: int
    total_mb: float
    granules: list[Granule]

    @property
    def mean_mb(self) -> float:
        return self.total_mb / self.total if self.total else 0.0


def _parse_granule(entry: dict) -> Granule:
    start_s, _, end_s = (entry.get("dcDate") or "/").partition("/")
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None  # noqa: E731
    return Granule(entry["id"], entry["identifier"], parse(start_s), parse(end_s))


class MosdacClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self._token: str | None = None
        self._lock = threading.Lock()
        # Shared across download threads: when one thread sees HTTP 429, every thread
        # waits until this time before its next request, and the pause doubles per hit.
        self._pause_until = 0.0
        self._pause_len = RATE_LIMIT_FIRST_WAIT

    def _wait_if_rate_limited(self) -> None:
        delay = self._pause_until - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def _rate_limited(self, retry_after: str | None) -> float:
        """Register a 429; return the pause length that was applied (seconds)."""
        with self._lock:
            if time.monotonic() < self._pause_until:  # another thread already set a pause
                return self._pause_until - time.monotonic()
            wait = self._pause_len
            if retry_after and retry_after.isdigit():
                wait = max(wait, int(retry_after))
            wait = min(wait, RATE_LIMIT_MAX_WAIT)
            self._pause_until = time.monotonic() + wait
            self._pause_len = min(self._pause_len * 2, RATE_LIMIT_MAX_WAIT)
            log.info("MOSDAC rate limit (HTTP 429): all downloads paused %d s", wait)
            return wait

    def _quota_exhausted(self) -> None:
        """Pause all threads until the quota should be back; this never fails a granule."""
        with self._lock:
            if time.monotonic() < self._pause_until:
                return
            wait = min(_seconds_to_quota_reset(), QUOTA_PROBE_WAIT)
            self._pause_until = time.monotonic() + wait
            log.warning("MOSDAC daily download quota reached: all downloads paused %d min", wait // 60)

    def _rate_limit_ok(self) -> None:
        with self._lock:
            self._pause_len = RATE_LIMIT_FIRST_WAIT

    def _get_json(self, url: str, params: dict, retries: int = 3) -> dict:
        for attempt in range(retries):
            try:
                r = self.session.get(url, params=params, timeout=TIMEOUT)
                # MOSDAC answers 500 when a product simply has no granules for the query.
                if r.status_code == 500 and "Data unavailable" in r.text:
                    return {}
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError):
                if attempt == retries - 1:
                    raise
                time.sleep(2 * (attempt + 1))
        raise AssertionError("unreachable")

    # ---- catalogue ---------------------------------------------------------
    def collections(self, satellite: str) -> list[str]:
        d = self._get_json(COLLECTIONS_URL, {"satellite": satellite})
        return sorted(e["identifier"] for e in d.get("entries", []))

    def search(
        self,
        dataset_id: str,
        start: date | None = None,
        end: date | None = None,
        count: int = 1,
        start_index: int = 1,
    ) -> SearchResult:
        params: dict = {"datasetId": dataset_id, "count": min(count, MAX_COUNT), "startIndex": start_index}
        if start:
            params["startTime"] = start.isoformat()
        if end:
            params["endTime"] = end.isoformat()
        d = self._get_json(DATASETS_URL, params)
        return SearchResult(
            total=int(d.get("totalResults") or 0),
            total_mb=float(d.get("totalSizeMB") or 0),
            granules=[_parse_granule(e) for e in d.get("entries", [])],
        )

    def list_all(self, dataset_id: str, start: date, end: date) -> list[Granule]:
        """Every granule in [start, end], paging through the 50-per-page limit."""
        first = self.search(dataset_id, start, end, count=MAX_COUNT)
        out = list(first.granules)
        index = 1 + MAX_COUNT
        while index <= first.total:
            out += self.search(dataset_id, start, end, count=MAX_COUNT, start_index=index).granules
            index += MAX_COUNT
        return out

    def oldest(self, dataset_id: str) -> Granule | None:
        """Results are newest-first, so the last index is the oldest granule."""
        total = self.search(dataset_id).total
        if not total:
            return None
        res = self.search(dataset_id, count=1, start_index=total)
        return res.granules[0] if res.granules else None

    # ---- download ----------------------------------------------------------
    def token(self, refresh: bool = False) -> str:
        with self._lock:
            if self._token is None or refresh:
                user, password = mosdac_credentials()
                r = self.session.post(TOKEN_URL, json={"username": user, "password": password}, timeout=TIMEOUT)
                r.raise_for_status()
                self._token = r.json()["access_token"]
            return self._token

    def download(self, granule: Granule, dest_dir: Path, retries: int = 4) -> Path:
        """Download one granule atomically (.part then rename), with retries.

        Thread-safe: each thread uses its own HTTP session; the login token is shared and
        refreshed once on HTTP 401. An existing file that opens as HDF5 is reused.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / granule.filename
        if out.exists() and _is_hdf5(out):
            return out
        if free_gb(dest_dir) < MIN_FREE_GB:
            raise DiskFullError(f"Less than {MIN_FREE_GB} GB free; refusing to download {granule.filename}")
        part = out.with_suffix(out.suffix + ".part")
        session = _thread_session()
        last_exc: Exception | None = None
        attempt = 0
        waited_429 = 0.0
        while attempt < retries:
            self._wait_if_rate_limited()
            try:
                with session.get(
                    DOWNLOAD_URL,
                    headers={"Authorization": f"Bearer {self.token()}"},
                    params={"id": granule.id},
                    stream=True,
                    timeout=TIMEOUT,
                ) as r:
                    if r.status_code == 401:
                        self.token(refresh=True)
                        raise requests.HTTPError("401 token expired", response=r)
                    if r.status_code == 429 and _is_daily_quota(r):
                        self._quota_exhausted()
                        continue
                    if r.status_code == 429:
                        # Server rate limit: pause all threads, do not count as an attempt.
                        waited_429 += self._rate_limited(r.headers.get("Retry-After"))
                        if waited_429 > RATE_LIMIT_GIVE_UP:
                            raise RateLimitError(f"rate-limited for over {RATE_LIMIT_GIVE_UP // 60} min: {granule.filename}")
                        continue
                    r.raise_for_status()
                    with part.open("wb") as fh:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            fh.write(chunk)
                if not _is_hdf5(part):
                    raise OSError(f"downloaded file is not valid HDF5: {granule.filename}")
                part.replace(out)
                self._rate_limit_ok()
                return out
            except (requests.RequestException, OSError) as exc:
                last_exc = exc
                part.unlink(missing_ok=True)
                attempt += 1
                time.sleep(min(60, 5 * 2**attempt))
        raise RuntimeError(f"giving up on {granule.filename}: {last_exc}")


class DiskFullError(RuntimeError):
    pass


class RateLimitError(RuntimeError):
    """MOSDAC kept answering HTTP 429 for too long; the whole day should be retried later."""


_local = threading.local()


def _thread_session() -> requests.Session:
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _is_daily_quota(response: requests.Response) -> bool:
    try:
        return response.json().get("type") == "daily_limit"
    except ValueError:
        return False


def _seconds_to_quota_reset(now: datetime | None = None) -> int:
    """Seconds until 00:05 IST next occurs."""
    now = now or datetime.now(IST)
    reset = now.replace(hour=0, minute=5, second=0, microsecond=0)
    if reset <= now:
        reset += timedelta(days=1)
    return int((reset - now).total_seconds())


def _is_hdf5(path: Path) -> bool:
    try:
        with h5py.File(path, "r"):
            return True
    except OSError:
        return False
