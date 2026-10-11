#!/usr/bin/env python3
"""Rebuild catalog indexes using local files and index.json configuration."""

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


def local_path(root, config, key):
    """Map a catalog URL (or relative path) to this checkout."""
    value = config[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"index.json: {key} must be a non-empty string")
    url = urlsplit(value)
    path = Path(unquote(url.path.rstrip("/")))
    if url.scheme or url.netloc:
        path = Path(path.name)
    result = (root / path).resolve()
    if not result.is_relative_to(root) or result == root:
        raise ValueError(f"index.json: {key} must point inside the catalog")
    return result


def read_json(path):
    with path.open(encoding="utf-8-sig") as source:
        return json.load(source)


def catalog_files(directory):
    if not directory.is_dir():
        raise ValueError(f"Missing catalog directory: {directory}")
    return sorted(
        (path for path in directory.rglob("*.json") if path.is_file()),
        key=lambda path: path.relative_to(directory).as_posix(),
    )


def scheme_entry(path, directory):
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: scheme must be a JSON object")
    for key in ("name", "description"):
        if not isinstance(data.get(key), str):
            raise ValueError(f"{path}: {key} must be a string")
    tags = data.get("tags")
    if isinstance(tags, dict):
        tags = tags.get("$values")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError(f"{path}: tags must be an array of strings or a $values wrapper")
    return {
        "file": path.relative_to(directory).as_posix(),
        "name": data["name"],
        "description": data["description"],
        "tags": tags,
    }


def build_indexes(root):
    root = root.resolve()
    config = read_json(root / "index.json")
    parts_dir = local_path(root, config, "partsDir")
    schemes_dir = local_path(root, config, "schemesDir")
    parts_index = local_path(root, config, "partsIndex")
    schemes_index = local_path(root, config, "schemesIndex")
    if parts_index == schemes_index:
        raise ValueError("Parts and schemes indexes must have different paths")
    parts = [
        path.relative_to(parts_dir).as_posix()
        for path in catalog_files(parts_dir)
    ]
    schemes = [
        scheme_entry(path, schemes_dir)
        for path in catalog_files(schemes_dir)
    ]
    # Validate all input before touching either output.
    for destination, entries in ((parts_index, parts), (schemes_index, schemes)):
        destination.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{destination.name}: {len(entries)} entries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent,
        help="Catalog directory (defaults to the checkout containing this script)",
    )
    args = parser.parse_args()
    try:
        build_indexes(args.root)
    except (OSError, ValueError, KeyError) as error:
        print(f"Cannot build indexes: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
