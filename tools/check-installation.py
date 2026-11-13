#!/usr/bin/env python3
"""Read-only drift check for a trusted, private creation-deployment/1 manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            result.update(chunk)
    return result.hexdigest()


def check(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema") != "creation-deployment/1":
        raise ValueError("unsupported deployment manifest")
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    results = []
    for record in records:
        if not isinstance(record, dict) or not all(isinstance(record.get(k), str) for k in ("source", "installed", "sha256")):
            raise ValueError("invalid deployment record")
        status = {"source": record["source"], "installed": record["installed"]}
        try:
            source = digest(record["source"])
            installed = digest(record["installed"])
        except OSError:
            status["status"] = "missing-or-unreadable"
        else:
            if source != installed:
                status["status"] = "out-of-sync"
            elif source != record["sha256"]:
                status["status"] = "manifest-stale"
            else:
                status["status"] = "ok"
        results.append(status)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path.home() / ".local/state/creation-publication/deployed.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        results = check(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        print("Cannot read a valid deployment manifest; no changes made.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            print(f"{result['status']}: {result['installed']}")
        print(f"Checked {len(results)} deployment records; no files changed.")
    return int(any(result["status"] != "ok" for result in results))


if __name__ == "__main__":
    sys.exit(main())
