# traktor-mcp

<!-- mcp-name: io.github.alchimestre/traktor-mcp -->

Inspect and reconcile your Traktor collection from an [MCP](https://modelcontextprotocol.io/) client.
Uses [traktor-nml](https://github.com/alchimestre/traktor-nml) to update `collection.nml` when audio files are replaced or added, without editing XML by hand.

| Requirement or limit | Detail |
|---|---|
| Runtime | Python 3.13+, [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Client | Local MCP server support over stdio |
| Files | Access to the Traktor collection and music directories on the same machine |
| Scope | Collection maintenance, not playback or live deck control |
| Status | Early version: 0.1.0 |
| Licence | [MIT](https://github.com/alchimestre/traktor-mcp/blob/main/LICENSE) |

## Setup

1. Install from PyPI:

   ```sh
   uv tool install traktor-mcp
   ```

2. Check that the executable is on your PATH:

   ```sh
   traktor-mcp --help
   ```

   If the command is not found, add the directory printed by `uv tool dir --bin` to your PATH.

3. Create `traktor.toml`. The default collection is in `Documents/Native Instruments/Traktor <version>/collection.nml`; replace the paths below with your actual locations:

   ```toml
   [paths]
   collection = "/path/to/Traktor/collection.nml"
   lossless = "/path/to/music/lossless"
   lossy = "/path/to/music/lossy"
   ```

   `lossless` and `lossy` are the music directories to import from. Relative paths resolve against the configuration file's directory.
   Add `state` only if a local pipeline tracks file replacements there: its `<run>/tracks.jsonl` records with `replaces` and `local_path` identify replacement files. Without that data, replacement matching uses filenames.
   Check the reported collection path before approving a write.

4. Add the server to your MCP client's configuration. For clients using `mcpServers`, merge this entry into the existing object:

   ```json
   {
     "mcpServers": {
       "traktor": {
         "command": "traktor-mcp",
         "args": ["--config", "/path/to/traktor.toml"]
       }
     }
   }
   ```

   Replace the config path with an absolute path. If the client cannot find `traktor-mcp`, use the executable's absolute path from step 2.
   Other clients may use a different configuration wrapper; the command and arguments stay the same.

5. Restart or reload the client, then ask: “Call Traktor's `status` and `plan`. Show the proposed changes without writing anything.”

   `plan` reports entries to repoint, files to add, and missing files. Check the reported collection path before approving a write.

## Tools

| Tool | Writes to collection | Effect |
|---|---|---|
| `status` | No | Summarise the collection and configured music directories |
| `plan` | No | List proposed replacements, additions and missing files |
| `apply` | Yes | Repoint replaced files and add new files; remove no entries |
| `purge` | Only with `apply: true` | Remove entries whose files are missing; preview by default |

Files in `lossless` and `lossy` are candidates for import. Files elsewhere are reported rather than moved.
For shell use without an MCP client, use [traktor-nml](https://github.com/alchimestre/traktor-nml) directly.

## Before writing

1. Close Traktor. It rewrites the collection on exit and can overwrite external changes. Both write operations refuse while Traktor is running.
2. Call `plan` and inspect its output. `apply` writes immediately when called; it has no separate confirmation argument.
3. Call `apply` only after reviewing replacements and additions. It backs up the collection beside the original before writing; untouched entries retain their original XML.
4. Preview `purge` separately before calling it with `apply: true`. Removed entries lose their history, cues and play counts. Playlist references are reassigned to a retained entry or dropped. A backup is taken before writing.
5. Open Traktor and run **Check Consistency → Analyze** for replaced tracks. Their old fingerprint, tempo, loudness, key and beatgrid measurements must be regenerated.

## Development

1. Install the project and development dependencies:

   ```sh
   uv sync
   ```

2. Run the tests:

   ```sh
   uv run pytest
   ```

To work on the library alongside the server, override it with a sibling checkout:

```sh
uv pip install -e ../traktor-nml
```

## Publishing

1. Configure a PyPI Trusted Publisher for this GitHub repository, workflow `publish.yml`, environment `pypi`.
2. Dispatch the workflow from `main` with the release tag or commit SHA as `ref`:

   ```sh
   gh workflow run publish.yml --repo alchimestre/traktor-mcp --ref main -f ref=v0.1.0
   ```

3. Check the workflow result before announcing the release. Published PyPI versions cannot be overwritten.
