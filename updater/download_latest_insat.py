import os
import requests
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_FOLDER = ROOT_DIR / "h5-data"
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file without overriding existing env vars."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Credentials come from the environment (GitHub Secrets in CI) or from the
# git-ignored .env file at the repo root for local runs.
load_dotenv(ROOT_DIR / ".env")
USERNAME = os.environ.get("MOSDAC_USERNAME", "")
PASSWORD = os.environ.get("MOSDAC_PASSWORD", "")
DATASET_ID = "3SIMG_L1B_STD"
DOWNLOAD_TOKEN_URL = "https://mosdac.gov.in/download_api/gettoken"
DATASETS_URL = "https://mosdac.gov.in/apios/datasets.json"
DOWNLOAD_URL = "https://mosdac.gov.in/download_api/download"
CHUNK_SIZE = 1024 * 1024


def fetch_access_token(username: str, password: str) -> str:
    response = requests.post(
        DOWNLOAD_TOKEN_URL,
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def find_latest_dataset(session: requests.Session) -> tuple[str, str]:
    response = session.get(
        DATASETS_URL,
        params={"datasetId": DATASET_ID, "count": 1},
    )
    response.raise_for_status()

    data = response.json()
    entries = data.get("entries") or []

    if not entries:
        raise RuntimeError("No files found")

    latest = entries[0]
    return latest["id"], latest["identifier"]


def download_file(session: requests.Session, access_token: str, file_id: str, filename: str) -> Path:
    response = session.get(
        DOWNLOAD_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"id": file_id},
        stream=True,
    )
    response.raise_for_status()

    output_file = DOWNLOAD_FOLDER / filename
    with output_file.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                handle.write(chunk)

    return output_file


def main() -> None:
    if not USERNAME or not PASSWORD:
        raise SystemExit("Set MOSDAC_USERNAME and MOSDAC_PASSWORD in .env or the environment.")
    print("Logging in...")
    access_token = fetch_access_token(USERNAME, PASSWORD)
    print("Login successful")

    print("Searching latest file...")
    with requests.Session() as session:
        file_id, filename = find_latest_dataset(session)
        print("Latest:", filename)
        print("Downloading...")
        output_path = download_file(session, access_token, file_id, filename)

    print("Saved:", output_path)


if __name__ == "__main__":
    main()
