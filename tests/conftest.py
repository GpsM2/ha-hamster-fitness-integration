"""Shared test fixtures for the Hamster Fitness test suite."""

from __future__ import annotations

from collections.abc import Generator

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Allow hass to load custom_components/ during tests.

    pytest-homeassistant-custom-component blocks loading anything outside
    HA Core by default, as a safety net for HA Core's own test suite. This
    repo IS a custom integration, so every test needs it enabled.
    """
    yield
