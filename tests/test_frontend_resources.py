"""Guards against the frontend resources going stale in a browser.

The cards are registered as Lovelace resources with a `?v=` query, so a
version bump forces browsers to re-fetch them. `hamster-fitness-shared.js`
is not a resource - the cards import it by relative URL - so it gets no
such treatment automatically, and a browser will happily keep serving its
old copy.

That is exactly what broke 0.3.0-beta.1: the shared module gained new
exports, browsers kept the pre-0.3.0 copy, the import failed, and because
a failed ES module import aborts the whole file, *not one* card ever
reached its `customElements.define()` - including the two that had not
changed at all. Every card silently vanished from the "add card" dialog.

These tests make that failure mode impossible to reintroduce quietly.
"""

from __future__ import annotations

import re
from pathlib import Path

from custom_components.hamster_fitness.const import (
    JS_MODULES,
    SHARED_MODULE_VERSION,
)

FRONTEND_DIR = (
    Path(__file__).parent.parent / "custom_components" / "hamster_fitness" / "frontend"
)
SHARED_MODULE = "hamster-fitness-shared.js"

# Matches the import specifier, with or without a version query, so a
# missing one is a test failure rather than an unmatched regex.
IMPORT_PATTERN = re.compile(rf'from "\./{re.escape(SHARED_MODULE)}(\?v=(\d+))?"')


def _card_files() -> list[Path]:
    return [FRONTEND_DIR / module["filename"] for module in JS_MODULES]


def test_every_registered_card_file_exists() -> None:
    """A JS_MODULES entry pointing at a missing file registers a 404."""
    for path in _card_files():
        assert path.is_file(), path.name


def test_shared_module_imports_carry_the_current_version() -> None:
    """Every import of the shared module must be cache-busted, and agree.

    Without the query a browser keeps its cached copy; with a stale one
    it keeps whichever copy that version fetched. Both leave the cards
    importing exports that may not exist yet.
    """
    importers = 0
    for path in _card_files():
        source = path.read_text(encoding="utf-8")
        for match in IMPORT_PATTERN.finditer(source):
            importers += 1
            version = match.group(2)
            assert version is not None, (
                f"{path.name} imports {SHARED_MODULE} without a ?v= query - "
                "browsers will keep serving their cached copy"
            )
            assert version == SHARED_MODULE_VERSION, (
                f"{path.name} imports {SHARED_MODULE}?v={version}, but "
                f"const.py says SHARED_MODULE_VERSION={SHARED_MODULE_VERSION}"
            )

    # Guards the guard: if the import style ever changes, this test must
    # not quietly pass by matching nothing.
    assert importers >= 3, f"expected every card to import {SHARED_MODULE}"


def test_shared_module_is_not_registered_as_a_resource() -> None:
    """It's a dependency of the cards, not a card - it must stay out.

    Registering it would make Home Assistant load it as a standalone
    Lovelace resource, which defines no card and only clutters the
    resource list.
    """
    assert SHARED_MODULE not in {module["filename"] for module in JS_MODULES}


def test_every_card_registers_itself() -> None:
    """Each card file must define its element and announce it to the picker.

    Cheap textual check, but it is what the "add card" dialog depends on:
    no `window.customCards.push`, no entry in the list.
    """
    for path in _card_files():
        source = path.read_text(encoding="utf-8")
        assert "customElements.define(" in source, path.name
        assert "window.customCards.push(" in source, path.name


def test_card_versions_are_unique_per_file() -> None:
    """Two entries pointing at one file would fight over its version."""
    filenames = [module["filename"] for module in JS_MODULES]
    assert len(filenames) == len(set(filenames))
