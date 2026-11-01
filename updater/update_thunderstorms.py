import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = ROOT_DIR / "updater"


def run_script(script_path: Path) -> None:
    print(f"Running: {script_path.name}")
    subprocess.run([sys.executable, str(script_path)], check=True)


def main() -> None:
    print("Downloading latest INSAT...")
    run_script(SCRIPT_DIR / "download_latest_insat.py")

    print("Generating thunderstorm alerts...")
    run_script(SCRIPT_DIR / "convert_h5_to_png.py")

    print("Done")


if __name__ == "__main__":
    main()
