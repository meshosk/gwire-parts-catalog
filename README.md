# The Gwire parts catalog

The catalog JSON files are maintained separately from the app.

## Tag manager (`docker-tag`)

The image builds locally on top of `python:3.13-slim`. It requires Docker with
Compose and a running daemon. Run the commands below from the repository root;
the catalog is mounted at `/catalog`, so changes are written directly to this checkout.
Your user and group IDs are passed to preserve file ownership.

Web app for searching (including fuzzy matches), adding, editing, and deleting
tags. Tags are lowercased and trimmed; duplicates are rejected. **Save** updates
the original `tags.json` directly, with tags sorted alphabetically.

```sh
LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" \
  docker compose -f docker-tag/docker-compose.yml up --build -d
```

Open [localhost:8080](http://localhost:8080). Search filters results as you type;
**Add tag** or Enter adds the search text only if that tag does not already exist.
Click **Rebuild indexes** after changing parts or schemes to regenerate
`parts-index.json` and `schemes-index.json`. The result shows entry counts or an
error. Index generation uses local catalog files and is separate from saving tags.
The app has no authentication; use it on a trusted local network.

Stop it with:

```sh
docker compose -f docker-tag/docker-compose.yml down
```

## Index format

The index builder can also run locally with `python3 docker-tag/build_indexes.py`
(Python 3.9+).

The script reads `index.json` to locate the catalog directories and index outputs.
Remote URLs map to the final path component in this checkout; relative local paths
are also supported. It recursively scans all `*.json` files in `parts/` and `schemes/`,
sorts paths, and rebuilds both indexes, removing stale entries. Paths in the indexes
are relative to their respective catalog directories and use `/` separators.

`parts-index.json` contains filenames. `schemes-index.json` contains objects:

```json
{
  "file": "Testovacka 01.scheme.json",
  "name": "Testovacka 01",
  "description": "Test test testtest",
  "tags": ["humbucker", "resistor", "p90"]
}
```

Scheme metadata comes from the top-level `name`, `description`, and `tags` fields.
Tags may be a plain array or the exported object containing `$values`. Invalid
scheme metadata stops the build before either index is updated. The app consuming
the schemes index needs to read this object format.
