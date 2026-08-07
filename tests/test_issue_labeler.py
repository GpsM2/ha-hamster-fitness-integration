"""Guards the automatic issue labelling config.

`.github/issue-labeler.yml` is never exercised by anything until a real
issue is filed, and a mistake there fails silently: the issue simply
lands unlabelled and gets lost. Two traps in particular are easy to walk
into and impossible to notice by reading:

- Several array entries under one label are ANDed by the action, not
  ORed. A label written as a keyword list matches almost nothing.
- The keywords are bilingual, so an English-only pattern quietly skips
  every German issue (and vice versa).

These tests are plain regex checks - no Home Assistant involved.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

CONFIG_PATH = Path(__file__).parent.parent / ".github" / "issue-labeler.yml"
PATTERN_LITERAL = re.compile(r"/(.*)/([a-z]*)", re.DOTALL)


def _config() -> dict[str, list[str]]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _compiled() -> dict[str, re.Pattern[str]]:
    compiled: dict[str, re.Pattern[str]] = {}
    for label, patterns in _config().items():
        body = PATTERN_LITERAL.fullmatch(patterns[0]).group(1)
        compiled[label] = re.compile(body, re.IGNORECASE)
    return compiled


def _labels_for(text: str) -> set[str]:
    return {label for label, rx in _compiled().items() if rx.search(text)}


def test_every_label_uses_exactly_one_pattern() -> None:
    """Multiple entries are ANDed by the action - almost never intended.

    A label written as a list of keywords would require *all* of them to
    appear in the same issue, which effectively disables it.
    """
    for label, patterns in _config().items():
        assert len(patterns) == 1, (
            f"{label!r} has {len(patterns)} patterns; the action requires ALL "
            "of them to match. Use one regex with | alternation instead."
        )


def test_every_pattern_is_a_valid_case_insensitive_regex() -> None:
    """A malformed regex disables its label without any error anywhere."""
    for label, patterns in _config().items():
        match = PATTERN_LITERAL.fullmatch(patterns[0])
        assert match, f"{label!r} is not a /pattern/flags literal: {patterns[0]!r}"
        assert "i" in match.group(2), (
            f"{label!r} lacks the `i` flag - it would miss any issue whose "
            "capitalisation differs from the pattern"
        )
        re.compile(match.group(1))  # raises if malformed


def test_integration_label_is_no_longer_assigned() -> None:
    """This is the integration repo, so the label carried no information.

    It matched nearly every issue filed here. Hardware reports are moved
    to the hardware repo automatically, so the distinction the label used
    to draw is made by the repo boundary itself now.
    """
    assert "integration" not in _config()


def test_every_bundled_card_has_a_label_rule() -> None:
    """A card without a rule collects unlabelled issues forever.

    Cross-checked against JS_MODULES so adding a card without its
    labelling rule fails here rather than being noticed months later.
    """
    from custom_components.hamster_fitness.const import JS_MODULES

    # hamster-fitness-card.js registers both the health-score and the
    # ranking card, so file count and label count differ by one.
    rules = {label for label in _config() if label.startswith("card: ")}
    assert len(rules) >= len(JS_MODULES), (
        f"{len(JS_MODULES)} card files but only {len(rules)} `card:` rules"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Bug reports, both languages, phrased as a user would.
        ("The card is broken and throws an exception", "bug"),
        ("Die Tastatur blendet sich aus, geht nicht auf dem Handy", "bug"),
        ("Weight resets after a few seconds - does not work", "bug"),
        # Feature requests.
        ("Feature request: support for a light sensor", "enhancement"),
        ("Wäre schön, wenn Regenwolken durchziehen", "enhancement"),
        ("Könnte man das nachträglich hinzufügen?", "enhancement"),
        # Documentation.
        ("The README is missing a card overview", "documentation"),
        ("Tippfehler in der Anleitung", "documentation"),
        # Subject areas.
        ("ESPHome D1 Mini TCRT5000 wiring", "hardware"),
        ("Der Health Score fällt jeden Morgen ab", "health-score"),
        ("Use the weather forecast for heat warnings", "weather"),
        ("Wettervorhersage für heiße Tage einbeziehen", "weather"),
        # One per card, in the words a user would actually reach for.
        ("Die Bestenliste zeigt falsche Werte", "card: ranking"),
        ("Chronicle card is empty", "card: chronicle"),
        ("Weight card input loses focus", "card: weighing"),
        ("Wiege-Karte zeigt nichts an", "card: weighing"),
        ("Day & Night card: the wheel animation stutters", "card: day-night"),
        ("Tag & Nacht Karte friert ein", "card: day-night"),
        ("Die Säulen im Health Score sind nicht antippbar", "card: health-score"),
    ],
)
def test_representative_issues_get_their_label(text: str, expected: str) -> None:
    """Each phrasing must reach the label a human would have picked."""
    assert expected in _labels_for(text), (
        f"{text!r} did not match {expected!r}; matched {sorted(_labels_for(text))}"
    )


@pytest.mark.parametrize(
    ("text", "forbidden"),
    [
        # The generic word "sensor" must not pull in `hardware` - it appears
        # in ordinary integration reports constantly.
        ("The temperature sensor cannot be selected", "hardware"),
        ("Der Türsensor ist unavailable", "hardware"),
        # A card-specific report must not collect every other card's label.
        ("Day & Night card: the wheel animation stutters", "card: ranking"),
        ("Die Bestenliste zeigt falsche Werte", "card: chronicle"),
        # A pure bug report shouldn't be dressed up as a feature request.
        ("The card is broken and throws an exception", "enhancement"),
    ],
)
def test_patterns_do_not_over_match(text: str, forbidden: str) -> None:
    """Wrong labels are worse than none - they hide the real grouping."""
    assert forbidden not in _labels_for(text), (
        f"{text!r} wrongly matched {forbidden!r}"
    )
