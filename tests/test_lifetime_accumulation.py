"""Lifetime distance must belong to Home Assistant, not to the device.

Background: on 2026-08-19 the wheel sensor was re-flashed. Its counter
went from 148,148 back to zero and lifetime distance collapsed from
134.97 km to nothing. A reset guard existed, but it compared against a
value that was never persisted, so a reload in between defeated it - and
a re-flash reliably brings a reload with it.

Lifetime is now accumulated from deltas and persisted, so it never
depends on the device's absolute counter. See issue #136.
"""

from __future__ import annotations

import math

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    STORAGE_VERSION,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
DIAMETER = 28.0
ENTRY_ID = "tacoentry"


def _km(rotations: float) -> float:
    return round(rotations * (DIAMETER * math.pi) / 100_000, 3)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: DIAMETER,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _seed_sources(hass: HomeAssistant, rotations: str) -> None:
    hass.states.async_set(WHEEL_SENSOR, rotations)
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")


async def test_counter_reset_does_not_lose_the_lifetime_total(
    hass: HomeAssistant,
) -> None:
    """A device re-flash must cost the gap, not the whole history."""
    _seed_sources(hass, "0")
    entry = await _setup(hass, _entry())

    hass.states.async_set(WHEEL_SENSOR, "1000")
    await hass.async_block_till_done()
    assert entry.runtime_data.data.lifetime_distance_km == _km(1000)

    # Re-flashed: the counter starts over.
    hass.states.async_set(WHEEL_SENSOR, "5")
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == _km(1005)

    hass.states.async_set(WHEEL_SENSOR, "30")
    await hass.async_block_till_done()
    assert entry.runtime_data.data.lifetime_distance_km == _km(1030)


async def test_counter_reset_survives_a_reload_in_between(
    hass: HomeAssistant,
) -> None:
    """The case that actually broke on the live instance.

    The device went offline, was re-flashed, and the entry re-set-up
    before the new counter published anything. The old guard compared
    against an in-memory value that the reload had already cleared, so
    it never fired.
    """
    _seed_sources(hass, "0")
    entry = await _setup(hass, _entry())

    hass.states.async_set(WHEEL_SENSOR, "1000")
    await hass.async_block_till_done()
    before = entry.runtime_data.data.lifetime_distance_km
    assert before == _km(1000)

    # Device drops off while it is being flashed.
    hass.states.async_set(WHEEL_SENSOR, "unavailable")
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Total is intact even though nothing readable came back yet.
    assert entry.runtime_data.data.lifetime_distance_km == before

    # New firmware starts counting from scratch.
    hass.states.async_set(WHEEL_SENSOR, "7")
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == _km(1007)


async def test_migration_from_the_offset_model_keeps_the_total(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Upgrading must not change the number the user sees."""
    hass_storage[f"{DOMAIN}_{ENTRY_ID}_baseline"] = {
        "version": STORAGE_VERSION,
        "data": {
            "wheel_sensor": WHEEL_SENSOR,
            "lifetime_offset_count": 148_148.0,
            "baseline_count": 150_000.0,
            "night_baseline_count": 150_000.0,
        },
    }
    _seed_sources(hass, "150000")
    entry = await _setup(hass, _entry())

    # Old model: (offset + current) * circumference.
    assert entry.runtime_data.data.lifetime_distance_km == _km(148_148 + 150_000)

    # And it keeps accumulating from there.
    hass.states.async_set(WHEEL_SENSOR, "150100")
    await hass.async_block_till_done()
    assert entry.runtime_data.data.lifetime_distance_km == _km(148_148 + 150_100)


async def test_migration_waits_when_the_counter_is_unreadable(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Migrating against an unreadable counter must not assume zero.

    Assuming zero here would repeat the exact bug being fixed, and it is
    a likely moment for it: an upgrade means a restart, and a restart is
    when the device is most likely to still be connecting.
    """
    hass_storage[f"{DOMAIN}_{ENTRY_ID}_baseline"] = {
        "version": STORAGE_VERSION,
        "data": {
            "wheel_sensor": WHEEL_SENSOR,
            "lifetime_offset_count": 148_148.0,
        },
    }
    _seed_sources(hass, "unavailable")
    entry = await _setup(hass, _entry())

    hass.states.async_set(WHEEL_SENSOR, "150000")
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == _km(148_148 + 150_000)


async def test_configure_can_correct_the_total_once(hass: HomeAssistant) -> None:
    """The Configure field sets the total, and does not keep re-applying it.

    Re-applying on every reload would be worse than not having the field:
    opening Configure for an unrelated setting would silently throw away
    everything run since the correction.
    """
    _seed_sources(hass, "0")
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(WHEEL_SENSOR, "1000")
    await hass.async_block_till_done()
    assert entry.runtime_data.data.lifetime_distance_km == _km(1000)

    # User types the pre-flash total into Configure. In production
    # OptionsFlowWithReload reloads the entry for us; async_update_entry
    # on its own does not, so the reload is explicit here.
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "lifetime_distance_km": 134.97}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == 134.97

    # Running continues on top of the corrected total.
    hass.states.async_set(WHEEL_SENSOR, "1100")
    await hass.async_block_till_done()
    after_running = entry.runtime_data.data.lifetime_distance_km
    assert after_running == round(134.97 + _km(100), 3)

    # An unrelated reload must not snap it back to the typed value.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == after_running


async def test_upgrade_discards_a_poisoned_baseline(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """An old-format baseline of 0 must not be trusted on upgrade.

    The previous version wrote 0 whenever the counter was unreadable at
    save time, which then made the *entire* counter look like distance
    run in the current window. On the live instance that produced a daily
    distance of 5.356 km against 21 rotations actually run.

    A stored 0 cannot be told apart from a window that genuinely started
    at 0, so neither baseline is carried across the format change.
    """
    hass_storage[f"{DOMAIN}_{ENTRY_ID}_baseline"] = {
        "version": STORAGE_VERSION,
        "data": {
            "wheel_sensor": WHEEL_SENSOR,
            # No "lifetime_rotations" key: this is the old format.
            "lifetime_offset_count": 0.0,
            "baseline_count": 0.0,
            "night_baseline_count": 0.0,
            "baseline_window_start": "2026-08-20T06:00:00+00:00",
            "night_window_start": "2026-08-20T18:00:00+00:00",
        },
    }
    _seed_sources(hass, "5858")
    entry = await _setup(hass, _entry())

    hass.states.async_set(WHEEL_SENSOR, "5879")
    await hass.async_block_till_done()

    # 21 rotations run since the upgrade - not the whole 5,879.
    assert entry.runtime_data.data.daily_distance_km == _km(21)
    assert entry.runtime_data.data.night_distance_km == _km(21)


async def test_beta1_storage_still_gets_its_baseline_discarded(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """0.9.3-beta.1 wrote the new lifetime field but kept the bad baseline.

    Detecting the old format by the presence of `lifetime_rotations`
    would therefore have skipped exactly the installations that were
    running the bug in production. The trust marker catches them.
    """
    hass_storage[f"{DOMAIN}_{ENTRY_ID}_baseline"] = {
        "version": STORAGE_VERSION,
        "data": {
            "wheel_sensor": WHEEL_SENSOR,
            # beta.1 storage: new field present, no trust marker,
            # baseline still poisoned.
            "lifetime_rotations": 148_148.0,
            "last_known_count": 5858.0,
            "baseline_count": 0.0,
            "night_baseline_count": 0.0,
            "baseline_window_start": "2026-08-20T06:00:00+00:00",
            "night_window_start": "2026-08-20T18:00:00+00:00",
        },
    }
    _seed_sources(hass, "5858")
    entry = await _setup(hass, _entry())

    hass.states.async_set(WHEEL_SENSOR, "5879")
    await hass.async_block_till_done()

    assert entry.runtime_data.data.daily_distance_km == _km(21)
    assert entry.runtime_data.data.night_distance_km == _km(21)
    # The lifetime total carries over untouched - only baselines are dropped.
    assert entry.runtime_data.data.lifetime_distance_km == _km(148_148 + 21)
