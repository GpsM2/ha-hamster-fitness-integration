"""Shared test fixtures for the Hamster Fitness test suite."""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator, Generator

import aiohttp.connector
import aiohttp.resolver
import pytest
import pytest_socket
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState

from custom_components.hamster_fitness.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


if not hasattr(config_entries, "OptionsFlowWithReload"):
    # manifest.json requires Home Assistant 2026.3.0, where
    # OptionsFlowWithReload (added in 2025.8) has long existed. The newest
    # pytest-homeassistant-custom-component release still pins an older
    # Core, so importing config_flow.py - and with it setting up ANY entry -
    # would blow up here for a reason that cannot occur in a supported
    # installation. Backfill the class so the suite is runnable; the only
    # thing lost is the automatic entry reload on option changes, which no
    # test asserts on. Disappears by itself once the pinned Core catches up.
    class _OptionsFlowWithReload(config_entries.OptionsFlow):  # type: ignore[misc]
        """Minimal stand-in for older Home Assistant Core versions."""

    config_entries.OptionsFlowWithReload = _OptionsFlowWithReload  # type: ignore[attr-defined]


if sys.platform == "win32":

    def _allow_loopback_sockets(allow_unix_socket: bool = False) -> None:
        """Let asyncio create its self-pipe socket on Windows.

        pytest-homeassistant-custom-component blocks all sockets per test
        and re-allows only AF_UNIX ones, which is enough on Linux/macOS:
        `socket.socketpair()` is an AF_UNIX pair there. Windows has no
        AF_UNIX socketpair, so asyncio's event loop falls back to a
        loopback AF_INET pair - which the blanket block rejects before a
        single test can even get its event loop, making the entire suite
        unrunnable on a Windows dev machine.

        This replaces `pytest_socket.disable_socket` itself rather than
        undoing it from a hook: the plugin re-applies the block on every
        single test from its own `pytest_runtest_setup`, so any attempt to
        re-enable afterwards is a hook-ordering race. Swapping the
        function out once, at import time, is deterministic.

        Sockets stay constructible, but connections remain restricted to
        loopback, so the actual point of the block - no test ever reaching
        the real network - still holds. Other platforms are untouched and
        keep pytest-socket's strict default.
        """
        pytest_socket.enable_socket()
        pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"])

    pytest_socket.disable_socket = _allow_loopback_sockets

    # aiohttp picks AsyncResolver (backed by aiodns) as its DefaultResolver
    # whenever aiodns is merely importable, with no way to opt out short of
    # not having it installed - and aiodns hard-requires a SelectorEventLoop,
    # which Windows has not defaulted to since Python 3.8. Any test that
    # opens a real aiohttp connection (hass_ws_client, hass_client) then
    # fails with "aiodns needs a SelectorEventLoop on Windows" before it
    # gets anywhere near this integration's own code.
    #
    # Tests only ever talk to 127.0.0.1, so real DNS resolution never
    # happens either way - ThreadedResolver is a functionally identical,
    # SelectorEventLoop-free substitute for that. Patched on
    # aiohttp.connector (where TCPConnector actually looks it up, via
    # `from .resolver import DefaultResolver`) rather than on
    # aiohttp.resolver: that import already copied the old reference in,
    # so patching the source module would be invisible to it.
    aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver


@pytest.fixture(autouse=True)
async def unload_entries_after_test(request: pytest.FixtureRequest) -> AsyncGenerator[None]:
    """Unload every Hamster Fitness entry a test left behind.

    Stopping Home Assistant does not unload config entries, so the
    listeners each entry registers through `entry.async_on_unload()` -
    the daily-reset timers, the notifier's summary timer - stay armed and
    trip the harness's lingering-timer check. Unloading here is what a
    real Home Assistant does when the integration is removed or reloaded,
    so it also exercises that path on every test for free.

    Skipped for tests that never asked for `hass` (the pure-function
    ones), so they don't pay for spinning one up.
    """
    yield

    hass = request.node.funcargs.get("hass")
    if hass is None:
        return
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def expected_lingering_tasks() -> bool:
    """Tolerate the HTTP server's accept loop outliving a test on Windows.

    This integration depends on `frontend`, which pulls in `http`, so every
    test spins up a real aiohttp server. On Windows its
    `IocpProactor.accept` task survives `hass.async_stop()` long enough for
    the harness to flag it (and to keep port 8123 bound for the next test).
    Nothing in this repo can cancel that task, and the failure is pure
    teardown noise.

    Deliberately narrow: only the *task* check is relaxed, and only here.
    `expected_lingering_timers` stays strict, since that one catches real
    bugs in this integration's own timers - it did exactly that for the
    per-minute duration timer, which was missing `cancel_on_shutdown`.
    """
    return sys.platform == "win32"


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
