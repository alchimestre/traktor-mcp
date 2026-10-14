# traktor-mcp

MCP tools for a Traktor collection, over the [`traktor-nml`](https://github.com/alchimestre/traktor-nml)
library.

Traktor has no API: its collection is one XML file, `collection.nml`, which the app reads whole at startup and
rewrites whole as it exits. This server exposes that reconciliation as four tools, each returning the text the
`traktor-nml` command line prints.

| tool | what it does | writes |
|---|---|---|
| `status` | where the collection and the lanes stand, in one paragraph | no |
| `plan` | what a run would change, entry by entry | no |
| `purge` | take out the entries whose file is gone | only when `apply` is true |
| `apply` | repoint and add, one backup first | yes |

## Run it

```sh
uv run traktor-mcp                            # speaks MCP on stdio
uv run traktor-mcp --config path/to/config.toml   # another config
```

An MCP client mounts it by command:

```json
"traktor": {
  "type": "stdio",
  "command": "uv",
  "args": ["run", "traktor-mcp"],
  "cwd": "path/to/traktor-mcp"
}
```

## Before it writes

- **Traktor must be closed.** It rewrites the collection on exit, over anything written while it was up;
  `apply` refuses while it is running.
- **`plan` and `status` write nothing**, and are cheap enough to run whenever.
- **`apply` backs the collection up first** (`collection.nml.<stamp>.backup`, beside it), then makes one edit
  that leaves every entry nobody is repointing byte for byte as Traktor wrote it.
- **Nothing is deleted by `apply`.** `purge` is the one verb that removes entries, it says what each removal
  costs before it writes, and it is a dry run until it is asked.
- A repointed entry gives up what was measured from the audio that is gone (fingerprint, tempo, loudness, key,
  the auto grid), so the app's **Check Consistency → Analyze** is the step after a write.

## Configuration

It reads the same `config.toml` the `traktor-nml` command does — the collection as a pattern, the two lanes,
and where a pipeline's job state lives — so one file configures both. `--config` reads another one. Nothing in
it is a secret.

## Development

`traktor-mcp` depends on a `traktor-nml` checkout beside it (`../traktor-nml` in `pyproject.toml`), so clone
both into the same parent directory:

```sh
uv run pytest
```

The server is written against the MCP SDK's v2 names (`mcp.server.mcpserver.MCPServer`, which v1 called
`FastMCP`), which is why the dependency is pinned below 3.

MIT licensed.
