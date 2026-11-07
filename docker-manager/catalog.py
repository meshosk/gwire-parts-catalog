"""Catalog data access and validation, independent of HTTP."""

import json
from pathlib import Path
import threading

from build_indexes import build_indexes, catalog_files, local_path, read_json
from storage import atomic_write, json_bytes, revision


def metadata_object(document, kind):
    if not isinstance(document, dict):
        raise ValueError("Catalog file must contain a JSON object.")
    metadata = document.get("circuit", document) if kind == "schemes" else document
    if not isinstance(metadata, dict):
        raise ValueError("Circuit must contain a JSON object.")
    return metadata


def metadata_fields(metadata):
    fields = {key: metadata.get(key, "") for key in ("name", "description")}
    tags = metadata.get("tags", [])
    fields["tags"] = tags.get("$values") if isinstance(tags, dict) else tags
    if any(not isinstance(fields[key], str) for key in ("name", "description")):
        raise ValueError("Name and description must be strings.")
    if not isinstance(fields["tags"], list) or any(not isinstance(tag, str) for tag in fields["tags"]):
        raise ValueError("Tags must be an array of strings or a $values wrapper.")
    return fields


def normalize_tags(value):
    if not isinstance(value, list) or any(not isinstance(tag, str) for tag in value):
        raise ValueError("tags.json must contain an array of strings.")
    tags = []
    seen = set()
    for tag in value:
        tag = tag.strip().lower()
        if not tag:
            raise ValueError("A tag cannot be empty.")
        if tag not in seen:
            tags.append(tag)
            seen.add(tag)
    return tags


class ConflictError(ValueError):
    """The source changed or another catalog operation is already running."""


STALE_FILE = "The file has changed since it was loaded. Reload the page before making further edits."


class Catalog:
    def __init__(self, tags_path):
        self.tags_path = Path(tags_path).resolve()
        self.root = self.tags_path.parent
        self.tags_lock = threading.Lock()
        # Metadata reads/writes share a lock with rebuilds, which rename files.
        self.index_lock = threading.Lock()

    def load_tags(self):
        with self.tags_lock:
            raw = self.tags_path.read_bytes()
            original = json.loads(raw)
            tags = normalize_tags(original)
        return {"tags": tags, "revision": revision(raw), "normalized": tags != original}

    def save_tags(self, data):
        if not isinstance(data, dict) or "tags" not in data or "revision" not in data:
            raise ValueError("Missing tags or file revision.")
        tags = normalize_tags(data["tags"])
        if len(tags) != len(data["tags"]):
            raise ValueError("Tags contain duplicates after normalization.")
        tags.sort()
        with self.tags_lock:
            old_raw = self.tags_path.read_bytes()
            normalize_tags(json.loads(old_raw))
            if data["revision"] != revision(old_raw):
                raise ConflictError(STALE_FILE)
            raw = json_bytes(tags)
            atomic_write(self.tags_path, raw)
        return {"tags": tags, "revision": revision(raw), "normalized": False}

    def directory(self, kind):
        if kind not in ("parts", "schemes"):
            raise ValueError("Unknown catalog type.")
        return local_path(self.root, read_json(self.root / "index.json"), kind + "Dir")

    def list_items(self, kind):
        with self.index_lock:
            directory = self.directory(kind)
            items = []
            for path in catalog_files(directory):
                if not path.resolve().is_relative_to(directory):
                    raise ValueError("Catalog files must stay inside their directory.")
                fields = metadata_fields(metadata_object(read_json(path), kind))
                items.append({"file": path.relative_to(directory).as_posix(), **fields})
            return {"items": items}

    def item_path(self, kind, filename):
        directory = self.directory(kind)
        path = (directory / filename).resolve()
        if not filename or not path.is_relative_to(directory) or path.suffix.lower() != ".json":
            raise ValueError("Invalid catalog filename.")
        return path

    def load_item(self, kind, filename):
        with self.index_lock:
            path = self.item_path(kind, filename)
            raw = path.read_bytes()
            fields = metadata_fields(metadata_object(json.loads(raw.decode("utf-8-sig")), kind))
            return {"file": filename, **fields, "revision": revision(raw)}

    def save_item(self, kind, filename, data):
        if filename is None:
            raise ValueError("Missing catalog filename.")
        if not isinstance(data, dict) or set(data) != {"name", "description", "tags", "revision"}:
            raise ValueError("Expected name, description, tags and revision only.")
        fields = metadata_fields(data)
        if not fields["name"].strip():
            raise ValueError("Name cannot be empty.")
        if any(not tag.strip() for tag in fields["tags"]):
            raise ValueError("A tag cannot be empty.")
        with self.index_lock, self.tags_lock:
            path = self.item_path(kind, filename)
            old_raw = path.read_bytes()
            document = json.loads(old_raw.decode("utf-8-sig"))
            metadata = metadata_object(document, kind)
            metadata_fields(metadata)
            if data["revision"] != revision(old_raw):
                raise ConflictError(STALE_FILE)
            allowed_tags = normalize_tags(json.loads(self.tags_path.read_bytes()))
            if any(tag not in allowed_tags for tag in fields["tags"]):
                raise ValueError("Choose tags from the shared Tags list only. Remove tags that are no longer available.")
            if len(fields["tags"]) != len(set(fields["tags"])):
                raise ValueError("A tag can only be selected once.")
            metadata.update({key: fields[key] for key in ("name", "description")})
            if isinstance(metadata.get("tags"), dict):
                metadata["tags"]["$values"] = fields["tags"]
            else:
                metadata["tags"] = fields["tags"]
            raw = json_bytes(document)
            atomic_write(path, raw)
            return {"file": filename, **fields, "revision": revision(raw)}

    def rebuild_indexes(self):
        if not self.index_lock.acquire(blocking=False):
            raise ConflictError("Index generation is already running. Try again shortly.")
        try:
            return build_indexes(self.root)
        finally:
            self.index_lock.release()
