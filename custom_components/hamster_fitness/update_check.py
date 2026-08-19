"""Notices when HACS has updated the files but Home Assistant hasn't restarted.

After HACS downloads a new version, the files on disk change but the
running code does not - Python keeps the modules it already imported
until Home Assistant restarts. Until then the user is running the old
version while HACS reports the new one as installed.

The only hint today is HACS's own "restart required" note inside the
HACS panel. Nothing surfaces in Settings -> Devices & Services, where
the integration actually lives, so it is easy to miss and easy to
conclude "the fix didn't work".

This module compares the version Home Assistant *loaded* against the
version currently on disk and raises a Repairs entry when they diverge.
It resolves itself after the restart, since the two match again.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_RESTART_REQUIRED = "restart_required"

# HACS writes the new files in one go, so there is nothing to catch in
# real time - an hourly check is soon enough to be useful and rare enough
# to cost nothing.
CHECK_INTERVAL = timedelta(hours=1)

DATA_RUNNING_VERSION = f"{DOMAIN}_running_version"


def _read_manifest_version(manifest_path: Path) -> str | None:
    """Read `version` straight off disk. Runs in the executor - blocking I/O."""
    try:
        with manifest_path.open(encoding="utf-8") as file:
            return json.load(file).get("version")
    except (OSError, ValueError):
        # Mid-update HACS may have the file open, half-written, or briefly
        # absent. Nothing to report - the next check picks it up.
        return None


async def async_setup_update_check(hass: HomeAssistant) -> None:
    """Record the running version and start watching the file on disk.

    Registered once per Home Assistant (from `async_setup`), not per
    config entry: the version is a property of the integration, so
    several hamsters would otherwise each start their own identical
    timer and race to raise the same repair.
    """
    if DATA_RUNNING_VERSION in hass.data:
        return

    integration = await async_get_integration(hass, DOMAIN)
    running_version = str(integration.version) if integration.version else None
    if running_version is None:
        # A manifest with no version at all isn't something this can
        # reason about; nothing to compare against.
        return

    hass.data[DATA_RUNNING_VERSION] = running_version
    manifest_path = Path(integration.file_path) / "manifest.json"

    async def _async_check(_now: Any = None) -> None:
        on_disk = await hass.async_add_executor_job(
            _read_manifest_version, manifest_path
        )
        if on_disk is None or on_disk == running_version:
            # Also clears a repair raised before a restart that has since
            # happened - though in practice the restart wipes it anyway,
            # since the issue registry is rebuilt from scratch.
            ir.async_delete_issue(hass, DOMAIN, ISSUE_RESTART_REQUIRED)
            return

        _LOGGER.debug(
            "Hamster Fitness: Version auf der Festplatte (%s) weicht von der "
            "geladenen (%s) ab - Neustart erforderlich",
            on_disk,
            running_version,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_RESTART_REQUIRED,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_RESTART_REQUIRED,
            translation_placeholders={
                "running_version": running_version,
                "installed_version": on_disk,
            },
        )

    await _async_check()
    async_track_time_interval(
        hass,
        _async_check,
        CHECK_INTERVAL,
        # A version check is never worth delaying a shutdown for.
        cancel_on_shutdown=True,
    )
