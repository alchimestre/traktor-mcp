"""MCP tools over a Traktor collection: `plan`, `status`, `purge` and `apply`.

The work is the `traktor-nml` library's; this module is the MCP surface over it. Every tool returns the text
the command line prints, so a session and a shell are looking at the same thing.

Written against the SDK's v2 names (`mcp.server.mcpserver.MCPServer`, which v1 called `FastMCP`), which is why
the dependency is pinned below 3.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from traktor_nml import config as config_module
from traktor_nml import nml, sync

INSTRUCTIONS = """Working on a Traktor collection.

Traktor has no API: its collection is one XML file, `collection.nml`, which the app reads whole at startup and
rewrites whole as it exits. This server reconciles that file against the directories the collection is meant to
hold, through the `traktor-nml` library and the same configuration file it reads.

Three rules before anything is written:

1. **Traktor must be closed.** It rewrites the collection on exit, over anything written while it was up.
   `apply` refuses while it is running; report that rather than retrying.
2. **`plan` and `status` write nothing.** Read them first, and show the report to the user whenever it is
   anything other than `0 repointed · 0 added`.
3. **`apply` writes to a live DJ library.** It takes one backup beside the collection first, and what follows
   is the user's to do in the app: **Check Consistency → Analyze** for the tracks whose audio was replaced,
   which are the ones the plan leaves unanalyzed.
"""


def build(config: config_module.Config | None = None) -> MCPServer:
    """The server, over the config given or the one `traktor-nml` reads."""
    settings = config if config is not None else config_module.load()
    server = MCPServer("traktor-mcp", instructions=INSTRUCTIONS)

    @server.tool()
    def status() -> str:
        """Where the Traktor collection and the two lanes stand: how many entries, how many files are in the
        lanes, and how many of each thing a run would do. Reads the whole collection and both lanes, writes
        nothing."""
        return sync.status(settings)

    @server.tool()
    def plan() -> str:
        """What a run would change, writing nothing: every entry to repoint onto the file that replaced it,
        every lane file to add, and every entry whose file is gone — either a duplicate the collection holds
        elsewhere, or a file that is not there and was not replaced."""
        found = sync.plan(settings)
        header = (f"the collection at {found.where}\n"
                  f"{found.total} entries · {found.kept} whose file is there · "
                  f"{len(found.repoints)} to repoint · {len(found.additions)} to add")
        return "\n".join([header, *found.lines(), "", found.report()])

    @server.tool()
    def purge(apply: bool = False) -> str:
        """Take out every entry in the collection whose file is gone — residue, since a collection is an index
        of files that exist. A playlist reference to a removed entry is moved to the entry that keeps the track,
        or dropped when nothing does; history, cues and play counts go with the entry and are reported. **Dry
        run unless apply is true.** Refuses while Traktor is running, and takes one backup beside the collection
        before it writes."""
        removed, written = sync.purge(settings, apply=apply)
        if not removed:
            return "nothing to purge: every entry points at a file that is there"
        lines = [removal.line() for removal in removed]
        if written is None:
            return "\n".join([*lines, "",
                              (f"{len(removed)} to remove — nothing has been written yet; "
                               "call again with apply=true to take them out")])
        return "\n".join([*lines, "",
                          f"{len(removed)} removed · backed up to {written.name} in {written.parent}"])

    @server.tool()
    def apply() -> str:
        """Write the plan into the collection: one backup beside it, then one edit that leaves every entry
        nobody is repointing byte for byte as Traktor wrote it. Refuses while Traktor is running. Returns what
        was written and what to do in the app afterwards."""
        found, written = sync.run(settings, apply=True)
        if not found.writes():
            return f"nothing to write: {found.report()}"
        return "\n".join([
            f"backed up to {written.name}" if written is not None else "written with no backup",
            f"under {found.where.parent}",
            found.report(),
            "",
            "open Traktor and run Check Consistency → Analyze for the tracks it lists as unanalyzed",
        ])

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="traktor-mcp",
        description="MCP tools for a Traktor collection, on stdio.",
    )
    parser.add_argument("--config", type=Path, default=None,
                        help="the config.toml to read (default: the one beside the traktor-nml checkout)")
    args = parser.parse_args(argv)
    try:
        build(config_module.load(args.config)).run()
    except nml.CollectionMissing as error:
        raise SystemExit(f"traktor-mcp: {error}")


if __name__ == "__main__":
    main()
