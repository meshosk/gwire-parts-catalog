# Tag manager

Run from the project root:

```sh
LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose -f docker-tag/docker-compose.yml up --build -d
```

Open http://localhost:8080. The app uses only the Python standard library and local HTML/CSS/JavaScript. No npm or pip installation is required.

The catalog root is mounted at `/catalog` so the app can update `tags.json` and the parts and schemes indexes. Mount the directory rather than the individual file: atomic tag writes rename a temporary file in the same directory. The container user needs write access to the directory and files.

On loading, tags are lowercased, trimmed, and deduplicated in their original order. Empty tags or structures other than an array of strings are rejected without overwriting the file. Adding and editing reject empty or duplicate values. Search supports substrings and similar words using Levenshtein distance.

Use **Search or add a tag** to filter results as you type. If the normalized value does not already exist, click **Add tag** or press Enter to add it. Similar results do not block adding a distinct tag. The edit form appears when you click **Edit** on an existing tag.

Adding, applying an edit, and deleting update the working list in the browser. Only **Save** writes the JSON array directly to the original file, with tags sorted alphabetically and without creating a backup. If the file has changed since loading (for example, in another browser), saving is rejected. Reload the page and repeat your edits against the latest version. Loading never writes to disk.

Click **Rebuild indexes** to regenerate the parts and schemes indexes from the local catalog, using the paths configured in `index.json` next to `tags.json`. The button shows progress, then entry counts or an error. Invalid source metadata is rejected before either index is updated. Only one rebuild can run at a time. This action does not save or discard pending tag edits.

Scheme metadata (`name`, `description`, `tags`) is read from the exported `circuit` object, or from the top level in older files. Tags support both plain arrays and `$values` wrappers.

Rebuilding also renames JSON files in the parts and schemes directories to lowercase
with spaces replaced by hyphens. Indexes use these new filenames; metadata stays
unchanged. Filename collisions stop the rebuild before files or indexes are changed.

The index builder is included in this same Docker image. To run it without the web interface:

```sh
docker compose -f docker-tag/docker-compose.yml exec tags python /app/build_indexes.py --root /catalog
```

Or run locally with `python3 docker-tag/build_indexes.py` (Python 3.9+).

Run locally without Docker (Python 3.9+):

```sh
python3 docker-tag/server.py
```

Optional arguments: `--tags /path/to/tags.json`, `--host 127.0.0.1`, `--port 8080`.

Tests use a temporary catalog and do not change the project’s `tags.json`:

```sh
python3 -m unittest discover -s docker-tag -p 'test_*.py' -v
node --test docker-tag/test_search.cjs
node --test docker-tag/test_ui.cjs
```

The app has no authentication and is intended for a trusted local network.
