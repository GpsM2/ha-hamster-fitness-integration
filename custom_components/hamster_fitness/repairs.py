"""Fix flow for the "restart required" repair (see update_check.py).

Mirrors the pattern Home Assistant Core's own zeroconf integration uses
for its duplicate-instance-id repair
(homeassistant/components/zeroconf/repairs.py): a confirm step that,
on submission, calls the homeassistant.restart service directly rather
than just telling the user where to click.
"""

from __future__ import annotations

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
)
from homeassistant.components.homeassistant import (
    SERVICE_HOMEASSISTANT_RESTART,
)
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .update_check import ISSUE_RESTART_REQUIRED


class RestartRequiredRepairFlow(RepairsFlow):
    """Confirm step that restarts Home Assistant."""

    @callback
    def _async_get_placeholders(self) -> dict[str, str]:
        registry = ir.async_get(self.hass)
        issue = registry.async_get_issue(self.handler, self.issue_id)
        assert issue is not None
        return issue.translation_placeholders or {}

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            await self.hass.services.async_call(
                HOMEASSISTANT_DOMAIN, SERVICE_HOMEASSISTANT_RESTART
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self._async_get_placeholders(),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a Hamster Fitness repair issue."""
    if issue_id == ISSUE_RESTART_REQUIRED:
        return RestartRequiredRepairFlow()

    # If a confirm-only repair is ever added, this should return a
    # ConfirmRepairFlow instead of raising - see the zeroconf precedent.
    raise ValueError(f"unknown repair {issue_id}")
