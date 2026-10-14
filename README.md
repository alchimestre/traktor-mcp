# traktor-mcp

MCP tools for a Traktor collection, over the [`traktor-nml`](https://github.com/alchimestre/traktor-nml)
library.

Traktor has no API: its collection is one XML file, `collection.nml`. This server exposes the `traktor-nml`
reconciliation over stdio.

| tool | writes | what it does |
|---|---|---|
| `status` | no | the collection and the lanes, in one paragraph |
| `plan` | no | what a run would change, entry by entry |
| `purge` | with `apply: true` | take out the entries whose file is gone |
| `apply` | yes | repoint the entries a run replaced, and add the files no entry has |

## Install

```sh
uv tool install git+https://github.com/alchimestre/traktor-mcp
```

## Run

```sh
traktor-mcp --config ~/traktor.toml
```

Mounted in an MCP client:

```json
"traktor": {
  "type": "stdio",
  "command": "traktor-mcp",
  "args": ["--config", "/home/you/traktor.toml"]
}
```

## Configuration

`config.toml`, from `--config <path>` if given, else from beside the `traktor-nml` checkout, else the values
below.

```toml
[paths]
collection = "~/Documents/Native Instruments/Traktor */collection.nml"
lossless   = "~/Music/music-agent/lossless"
lossy      = "~/Music/music-agent/lossy"
state      = "~/Music/music-agent/state"    # optional: a pipeline's job state, read as data
```

`collection` is a pattern: a Traktor upgrade changes the directory it lives in. `lossless` and `lossy` are the
directories the collection is meant to hold; a file in either is a candidate, a file elsewhere is the app's own
business and is reported rather than moved. Relative paths resolve against the config file's own directory. No
secrets in it.

## Before it writes

1. Close Traktor. It rewrites the collection on exit, over anything written while it was up; `apply` refuses
   while it is running.
2. Run `plan` first. It writes nothing and takes no time.
3. `apply` copies the collection to `collection.nml.<stamp>.backup` beside it, then repoints and adds in one
   edit. Every entry nobody is repointing stays byte for byte as Traktor wrote it.
4. `apply` removes nothing. `purge` is the only verb that removes, and only when it is called with
   `apply: true`.
5. Run Check Consistency → Analyze in Traktor after a write. A repointed entry gives up the fingerprint, tempo,
   loudness, key and grid measured from the audio that is gone, and the app has to measure them again.

## Development

```sh
uv sync
uv pip install -e ../traktor-nml    # to edit the library at the same time
uv run pytest
```

MIT licensed.
