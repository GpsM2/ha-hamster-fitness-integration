"""Tests for breed-aware weight assessment.

40 g is a perfectly healthy Roborovski and a dangerously underweight
Syrian, so the thresholds come from the breed. Where the breed is unknown
there is nothing honest to say, and nothing is deducted.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    BREED_GOLDEN,
    BREED_OTHER,
    BREED_ROBOROVSKI,
    CONF_ACQUISITION_DATE,
    CONF_BREED,
    CONF_BREED_OTHER,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    MAX_WEIGHT_G,
    WEIGHT_CLASSES,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"

HEALTH_SCORE = "sensor.hamster_taco_health_score"
WEIGHT_ENTITY = "number.hamster_taco_weight"


async def _setup(hass: HomeAssistant, breed: str = BREED_GOLDEN) -> MockConfigEntry:
    """A hamster of `breed`, running healthily, with no weight recorded."""
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    data = {
        CONF_HAMSTER_NAME: "Taco",
        CONF_ACQUISITION_DATE: "2024-01-01",
        CONF_BREED: breed,
        CONF_WHEEL_DIAMETER: 28.0,
        CONF_WHEEL_SENSOR: WHEEL_SENSOR,
        CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
        CONF_DOOR_SENSOR: DOOR_SENSOR,
    }
    if breed == BREED_OTHER:
        data[CONF_BREED_OTHER] = "Mischling"

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="taco", title="Taco", data=data
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # A good night, so nothing but weight can move the score.
    hass.states.async_set(WHEEL_SENSOR, "7800")
    await hass.async_block_till_done()
    return entry


async def _weigh(hass: HomeAssistant, grams: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": WEIGHT_ENTITY, "value": grams},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_no_weight_means_no_penalty(hass: HomeAssistant) -> None:
    """Never having weighed must not cost points.

    The value is hand-entered; deducting for its absence would punish
    someone for not having got round to it.
    """
    entry = await _setup(hass)
    data = entry.runtime_data.data

    assert data.weight_g is None
    assert data.weight_status is None
    assert data.weight_penalty == 0.0
    assert data.health_score == 100


async def test_healthy_weight_costs_nothing(hass: HomeAssistant) -> None:
    """A Syrian at 130 g sits squarely in the ideal range."""
    entry = await _setup(hass, BREED_GOLDEN)
    await _weigh(hass, 130)

    data = entry.runtime_data.data
    assert data.weight_status == "normal"
    assert data.weight_penalty == 0.0
    assert data.health_score == 100


@pytest.mark.parametrize(
    ("breed", "grams", "expected"),
    [
        # A Syrian at 40 g is starving; a Roborovski at 40 g is obese.
        (BREED_GOLDEN, 40, "underweight"),
        (BREED_ROBOROVSKI, 40, "overweight"),
        (BREED_GOLDEN, 130, "normal"),
        (BREED_ROBOROVSKI, 22, "normal"),
        (BREED_GOLDEN, 200, "overweight"),
        (BREED_ROBOROVSKI, 12, "underweight"),
    ],
)
async def test_same_number_means_different_things_per_breed(
    hass: HomeAssistant, breed: str, grams: float, expected: str
) -> None:
    """The whole reason the thresholds are per breed."""
    entry = await _setup(hass, breed)
    await _weigh(hass, grams)

    assert entry.runtime_data.data.weight_status == expected


async def test_penalty_grows_with_the_deviation(hass: HomeAssistant) -> None:
    """Slightly off costs a little, far off costs a lot."""
    entry = await _setup(hass, BREED_GOLDEN)

    await _weigh(hass, 165)  # just over the ideal 160
    slight = entry.runtime_data.data.weight_penalty

    await _weigh(hass, 175)  # past the overweight threshold of 170
    past_threshold = entry.runtime_data.data.weight_penalty

    await _weigh(hass, 240)  # unmistakably obese
    severe = entry.runtime_data.data.weight_penalty

    assert 0 < slight < past_threshold < severe
    assert severe <= 20.0  # capped


async def test_unknown_breed_is_not_judged(hass: HomeAssistant) -> None:
    """Without a species there is no reference range, so no verdict."""
    entry = await _setup(hass, BREED_OTHER)
    await _weigh(hass, 240)

    data = entry.runtime_data.data
    assert data.weight_g == 240
    assert data.weight_status is None
    assert data.weight_penalty == 0.0
    assert data.health_score == 100


async def test_weight_warning_fires_and_clears(hass: HomeAssistant) -> None:
    """Being off-weight is worth a notification, and recovering clears it."""
    entry = await _setup(hass, BREED_GOLDEN)

    await _weigh(hass, 210)
    assert "overweight" in entry.runtime_data.data.warning_reasons

    await _weigh(hass, 130)
    assert entry.runtime_data.data.warning_reasons == {}


async def test_weight_entity_caps_at_250_grams(hass: HomeAssistant) -> None:
    """The heaviest hamster is ~180 g; 1200 g is a typo, not a hamster."""
    await _setup(hass)
    assert MAX_WEIGHT_G == 250.0

    state = hass.states.get(WEIGHT_ENTITY)
    assert state.attributes["max"] == 250.0

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": WEIGHT_ENTITY, "value": 1200},
            blocking=True,
        )


async def test_weight_survives_a_reload(hass: HomeAssistant) -> None:
    """The coordinator owns the weight now, so it has to persist it."""
    entry = await _setup(hass)
    await _weigh(hass, 142)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.weight_g == 142
    assert hass.states.get(WEIGHT_ENTITY).state == "142.0"


async def test_card_gets_the_breed_range(hass: HomeAssistant) -> None:
    """The weighing card draws its dial from these attributes."""
    await _setup(hass, BREED_ROBOROVSKI)

    attrs = hass.states.get(HEALTH_SCORE).attributes
    classes = WEIGHT_CLASSES[BREED_ROBOROVSKI]
    assert attrs["weight_normal_min_g"] == classes["normal_min"]
    assert attrs["weight_normal_max_g"] == classes["normal_max"]
    assert attrs["weight_dial_max_g"] == classes["dial_max"]


async def test_unknown_breed_gets_no_range_but_still_a_dial(
    hass: HomeAssistant,
) -> None:
    """A dial still needs a maximum, even with no zones to draw on it."""
    await _setup(hass, BREED_OTHER)

    attrs = hass.states.get(HEALTH_SCORE).attributes
    assert attrs["weight_normal_min_g"] is None
    assert attrs["weight_dial_max_g"] == 250.0
