"""Two hamsters running side by side must stay completely separate.

Every store this integration writes is keyed by entry_id, with exactly
one deliberate exception (the shared lifetime archive, see archive.py) -
these tests pin that down, along with entity ids, per-entry state and the
per-hamster light automation, so a second hamster can't quietly overwrite
the first one's data.
"""

from __future__ import annotations

import math

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hamster_fitness.archive import STORAGE_KEY as ARCHIVE_KEY
from custom_components.hamster_fitness.const import (
    ATTR_DURATION_MINUTES,
    COAT_COLOR_BLACK,
    COAT_COLOR_HEX,
    COAT_COLOR_SILVER_GREY,
    CONF_ACQUISITION_DATE,
    CONF_COAT_COLOR,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_LIGHT_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    SERVICE_PAUSE_LIGHT_AUTOMATION,
)

TEMPERATURE_SENSOR = "sensor.cage_temperature"

# Each hamster gets its own hardware, as it would in reality.
TACO = {
    "slug": "taco",
    "name": "Taco",
    "wheel": "sensor.taco_wheel",
    "door": "binary_sensor.taco_door",
    "light": "light.taco_cage",
    "color": COAT_COLOR_SILVER_GREY,
}
NALA = {
    "slug": "nala",
    "name": "Nala",
    "wheel": "sensor.nala_wheel",
    "door": "binary_sensor.nala_door",
    "light": "light.nala_cage",
    "color": COAT_COLOR_BLACK,
}


async def _setup(hass: HomeAssistant, hamster: dict) -> MockConfigEntry:
    """Set up one hamster with its own sensors."""
    hass.states.async_set(hamster["wheel"], "0")
    hass.states.async_set(hamster["door"], "off")
    hass.states.async_set(hamster["light"], "off")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=hamster["slug"],
        title=hamster["name"],
        data={
            CONF_HAMSTER_NAME: hamster["name"],
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_COAT_COLOR: hamster["color"],
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: hamster["wheel"],
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: hamster["door"],
            CONF_LIGHT_ENTITY: hamster["light"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _setup_both(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockConfigEntry]:
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    return await _setup(hass, TACO), await _setup(hass, NALA)


async def test_each_hamster_gets_its_own_entities(hass: HomeAssistant) -> None:
    """No entity_id collisions between two hamsters."""
    await _setup_both(hass)

    for suffix in (
        "health_score",
        "night_distance",
        "activity_score",
        "sleep_score",
        "climate_score",
        "care_score",
    ):
        assert hass.states.get(f"sensor.hamster_taco_{suffix}") is not None, suffix
        assert hass.states.get(f"sensor.hamster_nala_{suffix}") is not None, suffix

    assert hass.states.get("switch.hamster_taco_light_automation") is not None
    assert hass.states.get("switch.hamster_nala_light_automation") is not None


async def test_running_one_wheel_does_not_move_the_other(
    hass: HomeAssistant,
) -> None:
    """Distance is per hamster - the classic cross-talk bug."""
    taco, nala = await _setup_both(hass)

    hass.states.async_set(TACO["wheel"], "5000")
    await hass.async_block_till_done()

    expected = round(5000 * (28.0 * math.pi) / 100_000, 3)
    assert taco.runtime_data.data.night_distance_km == expected
    assert nala.runtime_data.data.night_distance_km == 0.0


async def test_storage_keys_are_scoped_per_entry(hass: HomeAssistant) -> None:
    """Both stores carry the entry_id; only the archive is shared."""
    taco, nala = await _setup_both(hass)

    taco_key = taco.runtime_data._store.key
    nala_key = nala.runtime_data._store.key

    assert taco.entry_id in taco_key
    assert nala.entry_id in nala_key
    assert taco_key != nala_key
    # The one intentional exception, spelled out so a future change has to
    # be deliberate: the lifetime archive is shared by every hamster.
    assert ARCHIVE_KEY.startswith(DOMAIN)
    assert ARCHIVE_KEY.endswith("history_lifedata")
    assert taco.entry_id not in ARCHIVE_KEY


async def test_profiles_stay_separate(hass: HomeAssistant) -> None:
    """Each hamster keeps its own coat colour for the cards."""
    await _setup_both(hass)

    taco_attrs = hass.states.get("sensor.hamster_taco_health_score").attributes
    nala_attrs = hass.states.get("sensor.hamster_nala_health_score").attributes

    assert taco_attrs["coat_color_hex"] == COAT_COLOR_HEX[COAT_COLOR_SILVER_GREY]
    assert nala_attrs["coat_color_hex"] == COAT_COLOR_HEX[COAT_COLOR_BLACK]


async def test_pausing_one_light_leaves_the_other_armed(
    hass: HomeAssistant,
) -> None:
    """The pause service targets one hamster, not the integration."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    taco, nala = await _setup_both(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAUSE_LIGHT_AUTOMATION,
        {
            "entity_id": "switch.hamster_taco_light_automation",
            ATTR_DURATION_MINUTES: 30,
        },
        blocking=True,
    )

    assert taco.runtime_data.light_pause_until is not None
    assert nala.runtime_data.light_pause_until is None

    # Opening both cages: only Nala's light may react.
    hass.states.async_set(TACO["door"], "on")
    hass.states.async_set(NALA["door"], "on")
    await hass.async_block_till_done()

    assert [call.data["entity_id"] for call in turn_on] == [NALA["light"]]


async def test_one_departure_does_not_freeze_the_other(
    hass: HomeAssistant,
) -> None:
    """Archiving one hamster leaves the other one running normally."""
    from datetime import date

    taco, nala = await _setup_both(hass)

    await taco.runtime_data.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    hass.states.async_set(TACO["wheel"], "9000")
    hass.states.async_set(NALA["wheel"], "9000")
    await hass.async_block_till_done()

    # Taco is frozen, Nala keeps counting.
    assert taco.runtime_data.data.night_distance_km == 0.0
    assert nala.runtime_data.data.night_distance_km > 0.0
