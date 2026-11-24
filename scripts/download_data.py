#!/usr/bin/env python3
"""
Download the Kaggle datasets / competition files / notebook outputs that the
course notebooks read from `../input/...`.

Everything is saved to  courses/input/<name>/  which is exactly where the
notebooks (living in courses/<course>/) expect it, just like /kaggle/input on Kaggle.

Requires a Kaggle API token. See README.md ("Kaggle API token").

Examples:
    python scripts/download_data.py --list              # show courses and what they need
    python scripts/download_data.py 04-pandas           # one course
    python scripts/download_data.py pandas python       # partial names work too
    python scripts/download_data.py --all               # every course (many GB!)
    python scripts/download_data.py 03 --skip new-york-city-taxi-fare-prediction
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COURSES = ROOT / "courses"
INPUT = COURSES / "input"
MARKER = ".download-complete"


def load_manifest():
    return json.loads((COURSES / "manifest.json").read_text())


def pick_courses(manifest, names, use_all):
    courses = manifest["courses"]
    if use_all:
        return courses
    picked = []
    for name in names:
        hits = [c for c in courses if c["dir"] == name or c["dir"].startswith(name)
                or name.lower() in c["dir"].lower() or name == c["upstream_track"]]
        if not hits:
            sys.exit(f"No course matches {name!r}. Use --list to see course names.")
        if len(hits) > 1:
            exact = [c for c in hits if c["dir"] == name]
            if exact:
                hits = exact
            else:
                sys.exit(f"{name!r} matches several courses: {', '.join(c['dir'] for c in hits)}")
        picked += [h for h in hits if h not in picked]
    return picked


def get_api():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        sys.exit("The `kaggle` package is missing. Run:  pip install -r requirements.txt")
    except (OSError, SystemExit) as e:  # old kaggle versions authenticate on import
        sys.exit(f"Kaggle API credentials not found ({e}).\n"
                 "Create a token at https://www.kaggle.com/settings -> API -> 'Create New Token' "
                 "and see README.md for where to put it.")
    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as e:
        sys.exit(f"Kaggle authentication failed: {e}\nSee README.md section 'Kaggle API token'.")
    return api


def unzip_all(dest: Path):
    for z in list(dest.glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for member in zf.namelist():
                target = (dest / member).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise RuntimeError(f"Unsafe path in {z.name}: {member}")
            zf.extractall(dest)
        z.unlink()


def fetch(api, kind, ref, force=False):
    name = ref.split("/")[-1]
    dest = INPUT / name
    if (dest / MARKER).exists() and not force:
        print(f"  ✓ {name} (already downloaded)")
        return True
    dest.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ {kind:11s} {ref} -> courses/input/{name}")
    try:
        if kind == "dataset":
            api.dataset_download_files(ref, path=str(dest), unzip=True, quiet=False)
        elif kind == "competition":
            api.competition_download_files(ref, path=str(dest), quiet=False)
        elif kind == "kernel":
            api.kernels_output(ref, path=str(dest))
        unzip_all(dest)
    except Exception as e:
        msg = str(e)
        print(f"    ✗ failed: {msg.splitlines()[0] if msg else type(e).__name__}")
        if kind == "competition" and ("403" in msg or "Forbidden" in msg or "rules" in msg.lower()):
            print(f"      -> Open https://www.kaggle.com/competitions/{ref}/rules , click 'I Understand and "
                  f"Accept' (or 'Join Competition'), then run this again.")
        elif "404" in msg:
            print("      -> Not found. It may have been removed from Kaggle or made private.")
        return False
    (dest / MARKER).write_text(f"{kind} {ref}\n")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("courses", nargs="*", help="course folder names (or a unique part of one)")
    ap.add_argument("--all", action="store_true", help="download data for every course")
    ap.add_argument("--list", action="store_true", help="list courses and their data sources, then exit")
    ap.add_argument("--skip", nargs="*", default=[], help="source names to skip (e.g. a huge competition)")
    ap.add_argument("--force", action="store_true", help="re-download even if already present")
    ap.add_argument("--dry-run", action="store_true", help="only print what would be downloaded")
    args = ap.parse_args()

    manifest = load_manifest()
    if args.list:
        for c in manifest["courses"]:
            tag = "  (legacy)" if c["legacy"] else ""
            print(f"{c['dir']}{tag}")
            for kind, key in (("dataset", "datasets"), ("competition", "competitions"), ("kernel", "kernels")):
                for ref in c[key]:
                    print(f"    {kind:11s} {ref}")
            if not (c["datasets"] or c["competitions"] or c["kernels"]):
                print("    (no Kaggle data needed)")
        return
    if not args.courses and not args.all:
        ap.error("give one or more course names, or --all (see --list)")

    courses = pick_courses(manifest, args.courses, args.all)
    jobs = []
    for c in courses:
        for kind, key in (("dataset", "datasets"), ("competition", "competitions"), ("kernel", "kernels")):
            for ref in c[key]:
                name = ref.split("/")[-1]
                if name in args.skip or ref in args.skip:
                    continue
                if name not in [j[1].split("/")[-1] for j in jobs]:
                    jobs.append((kind, ref))
    if not jobs:
        print("Nothing to download for: " + ", ".join(c["dir"] for c in courses))
        return
    print(f"{len(jobs)} source(s) for: " + ", ".join(c["dir"] for c in courses))
    if args.dry_run:
        for kind, ref in jobs:
            print(f"  {kind:11s} {ref}")
        return

    api = get_api()
    INPUT.mkdir(parents=True, exist_ok=True)
    failed = [ref for kind, ref in jobs if not fetch(api, kind, ref, args.force)]
    print()
    if failed:
        print(f"Done with {len(failed)} failure(s): {', '.join(failed)}")
        sys.exit(1)
    print("All data downloaded to courses/input/")


if __name__ == "__main__":
    main()
