#!/usr/bin/env python3
"""Build and archive a native Book My Date release with PyInstaller."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from book_my_date.config import VERSION  # noqa: E402

PACKAGING = ROOT / "packaging"
DIST = PACKAGING / "dist"
WORK = PACKAGING / "build"
RELEASE = ROOT / "release"
SPEC = PACKAGING / "book_my_date.spec"


def artifact_name() -> str:
    system = platform.system().lower() or "unknown"
    machine = platform.machine().lower() or "unknown"
    return f"book-my-date-{VERSION}-{system}-{machine}"


def payload(dist: Path) -> tuple[Path, Path]:
    app = dist / "Book My Date.app"
    if app.exists():
        return dist, app
    folder = dist / "BookMyDate"
    if folder.exists():
        return dist, folder
    raise SystemExit(f"PyInstaller did not produce the expected output in {dist}")


def build(clean_only: bool = False) -> int:
    if clean_only:
        shutil.rmtree(DIST, ignore_errors=True)
        shutil.rmtree(WORK, ignore_errors=True)
        print("Removed packaging build folders.")
        return 0

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Run:")
        print("  python -m pip install -r requirements-dev.txt")
        return 1

    for folder in (DIST, WORK, RELEASE):
        shutil.rmtree(folder, ignore_errors=True)
    DIST.mkdir(parents=True)
    RELEASE.mkdir(parents=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        str(SPEC),
    ]
    print("Running:", " ".join(command))
    result = subprocess.run(command, cwd=str(ROOT))
    if result.returncode != 0:
        print("PyInstaller failed.")
        return result.returncode

    dist_root, built = payload(DIST)
    archive_base = RELEASE / artifact_name()
    archive = shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=str(dist_root),
        base_dir=built.name,
    )
    print(f"Built {built}")
    print(f"Archive {archive}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a native Book My Date release")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove packaging build folders and exit",
    )
    args = parser.parse_args(argv)
    return build(clean_only=args.clean)


if __name__ == "__main__":
    raise SystemExit(main())
