"""The MCP surface: the four tools, in process and over a real stdio transport.

The in-process tests call each tool directly — the path a client's call takes, without a transport. The last
one starts the console script as a subprocess, which is the only way to know the entry point and the stdio
wiring work.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import struct
from dataclasses import replace
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from traktor_nml import config as config_module
from traktor_nml import nml

from traktor_mcp import server as server_module

VOLUME = "Macintosh HD"

# What Traktor writes for one file: every element paired, and the INFO carrying the numbers a file has rather
# than the ones only the analyzer can measure.
ENTRY = """<ENTRY MODIFIED_DATE="2026/8/17" MODIFIED_TIME="60723" TITLE="{title}" ARTIST="{artist}">\
<LOCATION DIR="{directory}" FILE="{name}" VOLUME="{volume}" VOLUMEID="{volume}"></LOCATION>
<MODIFICATION_INFO AUTHOR_TYPE="user"></MODIFICATION_INFO>
<INFO BITRATE="320000" FILESIZE="1" PLAYTIME="128" FLAGS="12"></INFO>
</ENTRY>"""

VERBS = {"status", "plan", "purge", "apply"}


def aiff(path: Path, frames: int = 44100) -> Path:
    """A real AIFF: FORM/AIFF with a COMM chunk and some silence in SSND."""
    channels, bits = 2, 16
    data = b"\x00\x00" * frames * channels
    comm = struct.pack(">hLh", channels, frames, bits) + b"\x40\x0e\xac\x44" + b"\x00" * 6
    chunks = b"COMM" + struct.pack(">L", len(comm)) + comm
    body = struct.pack(">LL", 0, 0) + data
    chunks += b"SSND" + struct.pack(">L", len(body)) + body
    path.write_bytes(b"FORM" + struct.pack(">L", 4 + len(chunks)) + b"AIFF" + chunks)
    return path


def entry_for(where: Path, *, title: str = "Old Song", artist: str = "Someone") -> str:
    """One entry, describing the file at `where` — which the caller may or may not have written."""
    directory, name = nml.split(where)
    return ENTRY.format(directory=directory, name=name, title=title, artist=artist, volume=VOLUME)


def collection_at(where: Path, entries: str) -> Path:
    where.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        f'<NML VERSION="20"><HEAD></HEAD>'
        f'<COLLECTION ENTRIES="{entries.count("<ENTRY")}">{entries}</COLLECTION>'
        '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="0"></SUBNODES></NODE></PLAYLISTS></NML>',
        encoding="utf-8",
    )
    return where


def settings_for(tmp_path: Path, entries: str, *, run: tuple[Path, Path] | None = None):
    """A whole configuration over throwaway directories, and optionally one pipeline record."""
    for name in ("lossless", "lossy", "state"):
        (tmp_path / name).mkdir(exist_ok=True)
    if run is not None:
        job = tmp_path / "state" / "20260101T000000Z-run"
        job.mkdir()
        (job / "tracks.jsonl").write_text(
            json.dumps({"replaces": str(run[0]), "local_path": str(run[1])}) + "\n", encoding="utf-8")
    return replace(config_module.DEFAULTS, collection=collection_at(tmp_path / "collection.nml", entries),
                   lossless=tmp_path / "lossless", lossy=tmp_path / "lossy", state=tmp_path / "state")


def lane(tmp_path: Path, name: str, where: str = "lossless") -> Path:
    """Where a file would sit, without writing it — for an entry whose file is gone."""
    return tmp_path / where / name


def call(server, name: str, arguments: dict | None = None) -> str:
    """One tool call, as text: the path a client's call takes, without a transport."""
    result = asyncio.run(server.call_tool(name, arguments or {}))
    return "".join(getattr(block, "text", "") for block in result.content)


def names(server) -> set[str]:
    return {tool.name for tool in asyncio.run(server.list_tools())}


def test_the_server_offers_the_four_verbs(tmp_path):
    server = server_module.build(settings_for(tmp_path, ""))
    assert names(server) == VERBS


def test_plan_reads_and_apply_writes_through_the_server(tmp_path):
    """The whole point, end to end: `plan` names the repoint and writes nothing, `apply` writes it and backs
    the collection up first. The replacement is established by the name it carries, since no run here made it."""
    was = lane(tmp_path, "Someone - Old Song.mp3", where="lossy")
    settings = settings_for(tmp_path, entry_for(was))
    aiff(lane(tmp_path, "Someone - Old Song.aiff"))
    before = settings.collection.read_bytes()
    server = server_module.build(settings)

    assert "1 to repoint" in call(server, "plan")
    assert settings.collection.read_bytes() == before, "plan must not write"

    written = call(server, "apply")
    assert "backed up to" in written
    assert "1 repointed" in written
    assert settings.collection.read_bytes() != before
    assert "0 to repoint" in call(server, "plan")
    assert "entries" in call(server, "status")


def test_apply_on_a_settled_collection_says_there_is_nothing_to_write(tmp_path):
    server = server_module.build(settings_for(tmp_path, ""))
    assert "nothing to write" in call(server, "apply")


def test_purge_is_a_dry_run_until_it_is_asked(tmp_path):
    """`purge` is the one verb that takes an entry out, and it takes nothing out until `apply` is true."""
    settings = settings_for(tmp_path, entry_for(lane(tmp_path, "Nobody - Nothing.mp3", where="lossy")))
    server = server_module.build(settings)

    dry = call(server, "purge")
    assert "1 to remove" in dry and "nothing has been written" in dry
    assert '<COLLECTION ENTRIES="1">' in settings.collection.read_text(encoding="utf-8")

    assert "1 removed" in call(server, "purge", {"apply": True})
    assert '<COLLECTION ENTRIES="0">' in settings.collection.read_text(encoding="utf-8")
    assert "nothing to purge" in call(server, "purge")


def test_the_server_speaks_stdio_from_the_console_script(tmp_path):
    """The entry point itself: a client starts it, lists the tools and calls one."""
    script = shutil.which("traktor-mcp")
    if script is None:
        pytest.skip("the console script is not on PATH — run the tests through `uv run`")

    settings = settings_for(tmp_path, "")
    where = tmp_path / "config.toml"
    where.write_text(
        "[paths]\n"
        f'collection = "{settings.collection}"\n'
        f'lossless = "{settings.lossless}"\n'
        f'lossy = "{settings.lossy}"\n'
        f'state = "{settings.state}"\n',
        encoding="utf-8",
    )

    async def drive() -> tuple[list[str], str]:
        params = StdioServerParameters(command=script, args=["--config", str(where)])
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool("status", {})
            text = "".join(getattr(block, "text", "") for block in result.content)
            return [tool.name for tool in listed.tools], text

    listed, status = asyncio.run(drive())
    assert set(listed) == VERBS
    assert "entries" in status


def test_a_path_traktor_cannot_write_back_is_reported_not_fought_over(tmp_path):
    """A name carrying U+FEFF cannot survive a Traktor rewrite, so nothing is written for it; the tool says
    which character and what to do, and the collection is left exactly as it was."""
    settings = settings_for(tmp_path, "")
    aiff(lane(tmp_path, "Artist - \ufeffTitle.aiff"))
    server = server_module.build(settings)
    before = settings.collection.read_bytes()

    plan = call(server, "plan")
    assert "U+FEFF" in plan and "rename the file" in plan
    assert settings.collection.read_bytes() == before
    assert "nothing to write" in call(server, "apply")
