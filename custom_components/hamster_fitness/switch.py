"""Switch platform for the Hamster Fitness integration.

Exposes the cage-light automation as something the user can actually see
and turn off, instead of it being an invisible side effect of having
picked a light during setup. Only created when CONF_LIGHT_ENTITY is set -
without a light there is no automation to switch.

The permanent on/off state and the temporary pause both live on the
coordinator (see coordinator.py), so `door_light.py`, this entity and the
`hamster_fitness.pause_light_automation` action all read the same truth.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DURATION_MINUTES,
    CONF_LIGHT_ENTITY,
    DEFAULT_LIGHT_PAUSE_MINUTES,
    GUEST_URL_PREFIX,
    MAX_LIGHT_PAUSE_MINUTES,
    SERVICE_PAUSE_LIGHT_AUTOMATION,
)
from .coordinator import (
    HamsterFitnessConfigEntry,
    HamsterFitnessCoordinator,
    hamster_device_info,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HamsterFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hamster Fitness switches from a config entry."""
    entities: list[SwitchEntity] = [
        HamsterBoardingSwitch(entry.runtime_data, entry),
        HamsterGuestShareSwitch(hass, entry.runtime_data, entry),
    ]

    if not entry.data.get(CONF_LIGHT_ENTITY):
        async_add_entities(entities)
        return

    # An entity service rather than a domain-level one: the pause always
    # applies to exactly one hamster's automation, so letting Home
    # Assistant do the targeting keeps it correct with several hamsters
    # set up side by side (and gives the UI a proper target picker).
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_PAUSE_LIGHT_AUTOMATION,
        {
            vol.Optional(
                ATTR_DURATION_MINUTES, default=DEFAULT_LIGHT_PAUSE_MINUTES
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=MAX_LIGHT_PAUSE_MINUTES))
        },
        "async_pause_automation",
    )

    entities.append(HamsterLightAutomationSwitch(entry.runtime_data, entry))
    async_add_entities(entities)


class HamsterBoardingSwitch(
    CoordinatorEntity[HamsterFitnessCoordinator], SwitchEntity
):
    """Suspends evaluation while the hamster is temporarily away.

    For a stay at a foster home, a trip to the vet, or someone else
    looking after the hamster. Distinct from a departure date, which is
    permanent and archives the hamster: this changes nothing about the
    hamster's standing, writes no archive record, and simply resumes when
    switched back off.

    Without it, an empty cage's temperature and a motionless wheel drag
    the health score down and fire warnings about a hamster that is not
    even there.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "boarding"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the boarding switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_boarding"
        self._attr_device_info = hamster_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return whether the hamster is currently away."""
        return self.coordinator.boarding

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mark the hamster as away and pause evaluation."""
        await self.coordinator.async_set_boarding(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Welcome the hamster back and resume evaluation."""
        await self.coordinator.async_set_boarding(False)


class HamsterLightAutomationSwitch(
    CoordinatorEntity[HamsterFitnessCoordinator], SwitchEntity
):
    """Turns the door-triggered cage-light automation on or off.

    Stays `on` while a temporary pause is running - the pause is a short
    break, not a change of intent, and it reports itself through the
    `pause_active`/`paused_until` attributes so a dashboard can say
    "paused until 14:32" without the switch flipping back and forth.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "light_automation"

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the light-automation switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_light_automation"
        self._attr_device_info = hamster_device_info(entry)
        self._light_entity: str = entry.data[CONF_LIGHT_ENTITY]

    @property
    def is_on(self) -> bool:
        """Return whether the automation is switched on."""
        return self.coordinator.light_automation_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the pause state and the light this automation controls."""
        paused_until = self.coordinator.light_pause_until
        return {
            "pause_active": paused_until is not None,
            "paused_until": paused_until.isoformat() if paused_until else None,
            "light_entity": self._light_entity,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Re-arm the cage-light automation."""
        await self.coordinator.async_set_light_automation_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the cage-light automation from reacting to the door."""
        await self.coordinator.async_set_light_automation_enabled(False)

    async def async_pause_automation(self, duration_minutes: float) -> None:
        """Handle `hamster_fitness.pause_light_automation`."""
        await self.coordinator.async_pause_light_automation(duration_minutes)


class HamsterGuestShareSwitch(
    CoordinatorEntity[HamsterFitnessCoordinator], SwitchEntity
):
    """Turns the read-only guest link on or off (#147).

    The entity is the source of truth for whether a link exists at all -
    the `hamster-guest-share-card` is just a friendlier surface for the
    same on/off state and its `share_url` attribute, and an automation
    can flip it exactly the same way. Turning it on mints a fresh,
    unguessable link; turning it off invalidates whatever was shared
    immediately, see `HamsterFitnessCoordinator.async_set_guest_share()`.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "guest_share"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HamsterFitnessCoordinator,
        entry: HamsterFitnessConfigEntry,
    ) -> None:
        """Initialize the guest-share switch."""
        super().__init__(coordinator)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_guest_share"
        self._attr_device_info = hamster_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return whether a guest link currently exists."""
        return self.coordinator.guest_share_token is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full guest URL, if sharing is on.

        Built from Home Assistant's own configured URL rather than
        stored - so it always reflects the instance's current
        internal/external address instead of going stale if that ever
        changes. Preferring the external URL matches the actual use case
        (a boarding sitter checking in from outside the house); on a
        purely local setup with no external URL configured at all, the
        link falls back to the internal one, which still works for
        anyone on the same network.
        """
        token = self.coordinator.guest_share_token
        if token is None:
            return {"share_url": None}
        try:
            base_url = get_url(self._hass, prefer_external=True)
        except NoURLAvailableError:
            _LOGGER.warning(
                "Hamster Fitness: Kein Gast-Link möglich - Home Assistant "
                "hat weder eine interne noch eine externe URL konfiguriert."
            )
            return {"share_url": None}
        return {"share_url": f"{base_url}{GUEST_URL_PREFIX}/{token}"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Generate a fresh guest link."""
        await self.coordinator.async_set_guest_share(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Revoke the guest link immediately."""
        await self.coordinator.async_set_guest_share(False)
