# Tag manager

Run from the project root:

```sh
LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose -f docker-tag/docker-compose.yml up --build -d
```

Open http://localhost:8080. The app uses only the Python standard library and local HTML/CSS/JavaScript. No npm or pip installation is required.

The catalog root is mounted at `/catalog` so the app can replace the original `tags.json` and create `tags.json.bak` next to it. Mount the directory rather than the individual file: atomic writes rename a temporary file in the same directory. The container user needs write access to the directory and files.

On loading, tags are lowercased, trimmed, and deduplicated in their original order. Empty tags or structures other than an array of strings are rejected without overwriting the file. Adding and editing reject empty or duplicate values. Search supports substrings and similar words using Levenshtein distance.

Use **Search or add a tag** to filter results as you type. If the normalized value does not already exist, click **Add tag** or press Enter to add it. Similar results do not block adding a distinct tag. The edit form appears when you click **Edit** on an existing tag.

Adding, applying an edit, and deleting update the working list in the browser. Only **Save** writes the JSON array to the original file. Before each write, the exact previous contents, including formatting, are backed up to `.bak`. If backup creation fails, the original file is left untouched. If the file has changed since loading (for example, in another browser), saving is rejected. Reload the page and repeat your edits against the latest version. Loading never writes to disk.

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
