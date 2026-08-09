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


# --- Card translations -------------------------------------------------
#
# Card labels cannot live in strings.json: Home Assistant only loads a
# fixed set of translation categories into the frontend, and card text
# fits none of them. They sit in a table in hamster-fitness-shared.js
# instead, which means nothing type-checks the keys - a typo silently
# renders the key itself, or silently falls back to English forever.

SHARED_PATH = FRONTEND_DIR / SHARED_MODULE
# Only these namespaces are translation keys; anything else with a dot in
# it (file names, CSS, entity ids) must not be mistaken for one.
KEY_NAMESPACES = "common|dayNight|health|pillar|ranking|chronicle|breed|weight|coatColor"
# Dots are allowed beyond the namespace too - some keys nest a second
# level, e.g. weight.status.overweight.
KEY_LITERAL = re.compile(rf'"(({KEY_NAMESPACES})\.[A-Za-z0-9_.]+)"')
TABLE_ENTRY = re.compile(rf'"(({KEY_NAMESPACES})\.[A-Za-z0-9_.]+)":')


def _translation_tables() -> dict[str, set[str]]:
    """Return {language: keys} from the STRINGS table in the shared module."""
    source = SHARED_PATH.read_text(encoding="utf-8")
    start = source.index("const STRINGS = {")
    end = source.index("\n};", start)
    body = source[start:end]

    tables: dict[str, set[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped in ("en: {", "de: {"):
            current = stripped[:2]
            tables[current] = set()
            continue
        match = TABLE_ENTRY.match(stripped)
        if match and current:
            tables[current].add(match.group(1))
    return tables


def test_translation_tables_were_parsed() -> None:
    """Guards the guard: a changed table layout must not silently pass."""
    tables = _translation_tables()
    assert set(tables) == {"en", "de"}
    assert len(tables["en"]) > 50
    assert len(tables["de"]) > 30


def test_every_key_the_cards_use_exists_in_english() -> None:
    """English is the fallback, so a key missing there renders raw."""
    english = _translation_tables()["en"]
    for path in _card_files():
        used = {m.group(1) for m in KEY_LITERAL.finditer(path.read_text(encoding="utf-8"))}
        missing = sorted(used - english)
        assert not missing, f"{path.name} uses keys absent from the English table: {missing}"


def test_german_table_has_no_orphans() -> None:
    """A German key with no English counterpart is a typo, not a translation.

    German deliberately omits keys whose text is identical to English
    (proper names, "Online", ...) and falls back - so the reverse
    direction is not an error. A key that exists *only* in German,
    though, can never be reached.
    """
    tables = _translation_tables()
    orphans = sorted(tables["de"] - tables["en"])
    assert not orphans, f"German-only keys, likely typos: {orphans}"


def test_style_blocks_contain_no_stray_backtick() -> None:
    """A backtick inside the CSS ends the template literal early.

    Each card keeps its stylesheet in a `styles = ` template literal, so
    one backtick in a comment - writing `meet` for emphasis, say -
    terminates the string mid-CSS and turns the rest into JavaScript.
    The file then fails to parse, which means the card never registers
    and, because the shared module is imported first, it can take its
    siblings down with it.

    Cheap to typo, invisible on review, fatal at runtime.
    """
    for path in _card_files():
        source = path.read_text(encoding="utf-8")
        marker = ".styles = `"
        start = source.find(marker)
        if start == -1:
            continue
        body = source[start + len(marker) :]
        end = body.find("`")
        assert end != -1, f"{path.name}: unterminated styles template literal"
        # Everything up to the first backtick is the stylesheet; a stray
        # one would make that block end before the CSS actually does.
        css = body[:end]
        assert "{" in css and "}" in css, (
            f"{path.name}: the styles literal ends after {len(css)} chars, "
            "before any CSS rule - there is a stray backtick inside it"
        )


def test_no_card_stretches_an_svg_non_uniformly() -> None:
    """`preserveAspectRatio="none"` turns circles into eggs.

    The Day & Night sky decoration used it on a 300x120 viewBox inside a
    box whose real ratio is `card width : 130px`. Only at exactly 325px
    wide did the two agree; at any other width the sun disc and the moon
    crescent were squashed or stretched - at 900px the sun rendered 2.8x
    wider than tall.

    Nothing about the value looks wrong when reading the code, and it
    only misbehaves at sizes a developer may not happen to try, so it is
    pinned here instead.
    """
    for path in _card_files():
        source = path.read_text(encoding="utf-8")
        assert 'preserveAspectRatio="none"' not in source, (
            f"{path.name} scales an SVG non-uniformly; circles in it will "
            "render as ellipses at most card widths"
        )


def test_cards_do_not_hardcode_german_text() -> None:
    """Umlauts outside the translation table mean a missed string."""
    for path in _card_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("*", "//")):
                continue  # comments may be in any language
            assert not re.search(r'"[^"]*[äöüßÄÖÜ][^"]*"', line), (
                f"{path.name}:{number} looks like hardcoded German: {line.strip()}"
            )
