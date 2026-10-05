"""Approved documentation Maple may read (ADR-0029).

Shipped inside the release (root-owned and read-only on paolo-core) and loaded
with `importlib.resources` from this fixed manifest, by catalog id only: there
is no path argument, listing, or globbing. Changing the library is a release.
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
from types import MappingProxyType

MAX_LIBRARY_CHARS = 20_000

FILES: Mapping[str, str] = MappingProxyType(
    {
        "library:about_maple": "about_maple.md",
        "library:the_room": "the_room.md",
        "library:paolo_core": "paolo_core.md",
        "library:caring_for_a_server": "caring_for_a_server.md",
        "library:keeping_notes": "keeping_notes.md",
    }
)


class UnknownLibrarySource(KeyError):
    pass


def library_text(source_id: str) -> str:
    """The text of one approved document, by catalog id."""
    name = FILES.get(source_id)
    if name is None:
        raise UnknownLibrarySource(source_id)
    text = files(__name__).joinpath(name).read_text(encoding="utf-8")
    return text[:MAX_LIBRARY_CHARS]
