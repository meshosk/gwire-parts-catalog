# The Gwire parts catalog'

The catalog JSON files are maintained separately from the app.

Run `make -C docker indexes` after adding, editing, or removing parts or schemes. This
requires Docker with Compose, a running daemon, and Make; Python runs inside the container.
The first build downloads the Python image. Subsequent builds reuse Docker's cache.

The task uses `docker/compose.yaml` and `docker/Dockerfile` to build the image and mount this checkout at
`/catalog`, and writes the generated indexes directly into the checkout. The
container runs with your user ID to preserve file ownership, has networking
disabled during generation, and is removed when finished.

Without Make, run these commands from the repository root:

```sh
LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" \
  docker compose -f docker/compose.yaml run --build --rm indexes
```

All build tooling lives in `docker/`, including the Makefile and indexing script.

For local development, `python3 docker/build_indexes.py` remains available
(requires Python 3.9+).

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
