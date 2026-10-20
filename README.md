# Gwire parts catalog

Catalog data and SVG artwork for Gwire guitar wiring diagrams, maintained separately
from the main application. The repository contains component definitions, saved
wiring schemes, shared tags, and a local tag manager with an index builder.

## Repository layout

| Path | Contents |
| --- | --- |
| `index.json` | Catalog entry point: URLs for tags, part and scheme directories, and their indexes. Currently points to raw files on this repository’s `main` branch. |
| `parts/` | Exported component definitions (`*.part.json`), including embedded SVG markup, connection points, dimensions, tags, and state data. |
| `schemes/` | Saved wiring diagrams (`*.scheme.json`), including metadata and component data. |
| `source/svg/` | Editable standalone SVG artwork for components. |
| `parts-index.json` | Generated list of part filenames relative to `parts/`. |
| `schemes-index.json` | Generated list of scheme filenames and metadata relative to `schemes/`. |
| `tags.json` | Shared tag vocabulary as a JSON array of strings. |
| `docker-tag/` | Tag manager, index builder, Docker configuration, and tests. |

## Updating the catalog

1. Add or edit artwork in `source/svg/` as needed.
2. Add or update the corresponding definition in `parts/`, including embedded SVG,
   connection points, dimensions, and metadata. Preserve the exported JSON format,
   including reference fields such as `$id`, `$ref`, and `$values`.
3. Save wiring schemes in `schemes/`. Scheme metadata must include `name` and
   `description` strings and `tags` as an array of strings or a `$values` wrapper.
4. Update the shared vocabulary in `tags.json` if needed, directly or through the
   tag manager. Saving tags does not rewrite tags embedded in parts or schemes.
5. Rebuild the indexes after adding, removing, renaming, or editing parts or schemes.
   Include the updated index files with the catalog changes.

The index builder only regenerates index files. It does not convert SVG artwork
into parts or modify component definitions.

## Tag manager

Run these commands from the repository root. Docker requires Compose and a running
daemon. The image builds from `python:3.13-slim`; the app uses Python’s standard
library and local HTML/CSS/JavaScript, without npm or pip dependencies.

```sh
LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" \
  docker compose -f docker-tag/docker-compose.yml up --build -d
```

Open [localhost:8080](http://localhost:8080). The repository is mounted at `/catalog`
and the container runs with your user and group IDs so saved changes are written
directly to this checkout.

Search supports substrings and similar spellings. **Add tag** or Enter adds a new
tag; **Edit** and **Delete** change the working list. Tags are trimmed and
lowercased, and empty or duplicate values are rejected. Only **Save** writes the
list to `tags.json`, sorted alphabetically. If the file changed since loading,
saving is rejected; reload before repeating the edits.

**Rebuild indexes** regenerates both catalog indexes and displays counts or an
error. It is independent of pending tag edits.

Stop the container with:

```sh
docker compose -f docker-tag/docker-compose.yml down
```

Alternatively, run locally with Python 3.9+:

```sh
python3 docker-tag/server.py --host 127.0.0.1 --port 8080
```

The server defaults to `tags.json` in the repository root. Use `--tags` to select
another file. Without `--host`, it listens on `0.0.0.0`; the Docker configuration
publishes port 8080. The app has no authentication and is intended for trusted
local use. See [the tag manager README](docker-tag/README.md) for details.

## Rebuilding indexes

Run locally with Python 3.9+, without starting the tag manager:

```sh
python3 docker-tag/build_indexes.py
```

Or use the running Docker service:

```sh
docker compose -f docker-tag/docker-compose.yml exec tags python /app/build_indexes.py --root /catalog
```

The builder reads `index.json` and uses local files; it does not fetch the configured
URLs. URL paths map to their final path component in the checkout, while relative
paths resolve inside the catalog root. It recursively scans all `*.json` files in
the configured part and scheme directories, sorts their relative paths, and
replaces both indexes, removing stale entries. Standalone SVG files are not indexed.

`parts-index.json` is an array of filenames, for example:

```json
[
  "5-way-strat-switch.part.json",
  "mono-jack-socket.part.json",
  "pot.part.json",
  "singlecoil pickup.part.json"
]
```

`schemes-index.json` is an array of objects, for example:

```json
[
  {
    "file": "Testovacka 01.scheme.json",
    "name": "Testovacka 01",
    "description": "Test test testtest",
    "tags": ["humbucker", "resistor", "p90"]
  }
]
```

Scheme metadata comes from the top-level `name`, `description`, and `tags` fields.
Exported tags wrapped in `$values` are flattened into an array in the index.
Invalid scheme metadata is rejected before either index is written. Part files
are indexed by filename; the builder does not validate their JSON contents.

## Tests

The tag manager tests use temporary catalog data:

```sh
python3 -m unittest discover -s docker-tag -p 'test_*.py' -v
node --test docker-tag/test_search.cjs docker-tag/test_ui.cjs
```

The JavaScript tests use Node.js’s built-in test runner and require no npm install.
