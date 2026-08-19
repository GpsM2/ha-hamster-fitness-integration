"""Tests for the "restart pending after a HACS update" repair.

After HACS downloads a new version the files on disk change, but Python
keeps the modules it already imported - so Home Assistant goes on running
the old code until it restarts. update_check.py compares the two and
raises a Repairs entry when they diverge.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)
from custom_components.hamster_fitness.update_check import (
    ISSUE_RESTART_REQUIRED,
    _read_manifest_version,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"

MANIFEST = (
    Path(__file__).parent.parent
    / "custom_components"
    / "hamster_fitness"
    / "manifest.json"
)


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _has_repair(hass: HomeAssistant) -> bool:
    registry = ir.async_get(hass)
    return registry.async_get_issue(DOMAIN, ISSUE_RESTART_REQUIRED) is not None


# --- _read_manifest_version ---------------------------------------------


def test_reads_the_real_manifest_version() -> None:
    """The version this repo actually ships, straight off disk."""
    version = _read_manifest_version(MANIFEST)
    assert version == json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def test_missing_manifest_reads_as_none(tmp_path: Path) -> None:
    """Mid-update the file can be absent, half-written or briefly locked.

    None means "no answer", not "no update" - the caller leaves any
    existing repair alone rather than acting on a bad read.
    """
    assert _read_manifest_version(tmp_path / "nope.json") is None


def test_unparsable_manifest_reads_as_none(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"version": "0.6.0"', encoding="utf-8")  # truncated
    assert _read_manifest_version(manifest) is None


# --- The repair itself ----------------------------------------------------


async def test_no_repair_when_versions_match(hass: HomeAssistant) -> None:
    """The normal case: what's loaded is what's on disk."""
    await _setup_entry(hass)
    assert not _has_repair(hass)


async def test_repair_raised_when_disk_version_is_newer(
    hass: HomeAssistant,
) -> None:
    """HACS has written the new files; Home Assistant hasn't restarted."""
    with patch(
        "custom_components.hamster_fitness.update_check._read_manifest_version",
        return_value="99.0.0",
    ):
        await _setup_entry(hass)

    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, ISSUE_RESTART_REQUIRED)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    # Both versions are named, so the notice says what is actually
    # pending rather than just "restart".
    assert issue.translation_placeholders["installed_version"] == "99.0.0"
    assert issue.translation_placeholders["running_version"] != "99.0.0"


async def test_unreadable_manifest_raises_nothing(hass: HomeAssistant) -> None:
    """A failed read must not be mistaken for an update being available."""
    with patch(
        "custom_components.hamster_fitness.update_check._read_manifest_version",
        return_value=None,
    ):
        await _setup_entry(hass)


# --- The fix flow (repairs.py) --------------------------------------------


async def test_repair_is_fixable(hass: HomeAssistant) -> None:
    """The repair now offers a direct restart action, not just text."""
    with patch(
        "custom_components.hamster_fitness.update_check._read_manifest_version",
        return_value="99.0.0",
    ):
        await _setup_entry(hass)

    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, ISSUE_RESTART_REQUIRED)
    assert issue is not None
    assert issue.is_fixable is True


async def test_fix_flow_restarts_home_assistant_and_clears_the_issue(
    hass: HomeAssistant,
) -> None:
    """Confirming the fix flow restarts HA and resolves the repair itself.

    Goes through the real repairs FlowManager (hass.data["repairs"]
    ["flow_manager"]) exactly as the frontend's POST to
    /api/repairs/issues/fix does - not by calling the flow class's
    methods directly, which would skip the flow/id/handler bookkeeping
    the base FlowHandler needs and the automatic issue deletion that
    only happens in RepairsFlowManager.async_finish_flow().
    """
    with patch(
        "custom_components.hamster_fitness.update_check._read_manifest_version",
        return_value="99.0.0",
    ):
        await _setup_entry(hass)
    assert _has_repair(hass)

    assert await async_setup_component(hass, "repairs", {})
    restart_calls = async_mock_service(hass, "homeassistant", "restart")

    manager = hass.data["repairs"]["flow_manager"]
    result = await manager.async_init(
        DOMAIN, data={"issue_id": ISSUE_RESTART_REQUIRED}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["installed_version"] == "99.0.0"
    assert not restart_calls  # not yet - only the form was requested so far

    result = await manager.async_configure(result["flow_id"], user_input={})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert len(restart_calls) == 1

    assert not _has_repair(hass)  # the manager clears it once the flow finishes

    assert not _has_repair(hass)
