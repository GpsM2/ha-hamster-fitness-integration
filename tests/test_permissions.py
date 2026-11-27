"""Who may change what.

Past hamsters live in the archive every chronicle card renders, so writing
to it is admin-only. Everyday care - entering the weight - is not: any
regular user of the household can do it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness import (
    _ws_add_historical_hamster,
    _ws_remove_historical_hamster,
    _ws_update_historical_hamster,
    archive,
)
from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)


async def _regular_user(hass: HomeAssistant):
    """A non-admin household member, as created in Settings > People.

    Home Assistant makes the first user it creates the owner, who is always
    an admin - so the owner has to exist first.
    """
    await hass.auth.async_create_user("Owner", group_ids=["system-admin"])
    user = await hass.auth.async_create_user("Household", group_ids=["system-users"])
    assert not user.is_admin
    return user


async def test_non_admins_cannot_write_the_archive(hass: HomeAssistant) -> None:
    """A name typed here ends up on every dashboard - admins only."""
    connection = SimpleNamespace(user=await _regular_user(hass))

    for handler in (
        _ws_add_historical_hamster,
        _ws_update_historical_hamster,
        _ws_remove_historical_hamster,
    ):
        with pytest.raises(Unauthorized):
            handler(hass, connection, {"id": 1, "type": "ignored"})

    assert await archive.async_load(hass) == []


async def test_non_admins_can_still_enter_the_weight(hass: HomeAssistant) -> None:
    """The admin-only archive must not spill over into everyday care."""
    hass.states.async_set("sensor.wheel_rotations", "0")
    hass.states.async_set("sensor.cage_temperature", "22")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: "sensor.wheel_rotations",
            CONF_TEMPERATURE_SENSOR: "sensor.cage_temperature",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    user = await _regular_user(hass)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.hamster_taco_weight", "value": 47},
        blocking=True,
        context=Context(user_id=user.id),
    )

    assert entry.runtime_data.weight_g == 47
