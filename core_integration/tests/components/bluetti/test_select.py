"""Tests for the BLUETTI select platform."""

from unittest.mock import AsyncMock, MagicMock

from pybluetti import UnifyResponse
import pytest

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.coordinator import BluettiDeviceCoordinator
from homeassistant.components.bluetti.models import BluettiData, BluettiDevice
from homeassistant.components.bluetti.select import (
    BluettiSelect,
    async_setup_entry as select_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry

_WORK_MODE_STATE = {
    "fnCode": "SetCtrlWorkMode",
    "fnName": "Mode",
    "fnValue": "0",
    "fnType": "SELECT",
    "supportModeValues": [
        {"code": "0", "name": "Standard"},
        {"code": "1", "name": "Silent"},
    ],
}
_INV_WORK_STATE_STATE = {
    "fnCode": "InvWorkState",
    "fnName": "Inverter Status",
    "fnValue": "state_0",
    "fnType": "SELECT",
    "supportModeValues": [{"code": "state_0", "name": "Idle"}],
}


def _make_coordinator(hass: HomeAssistant) -> BluettiDeviceCoordinator:
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test Device",
        sn="SN1",
        model="AC200L",
        state_list=[_WORK_MODE_STATE, _INV_WORK_STATE_STATE],
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return BluettiDeviceCoordinator(hass, entry, device)


def _entry_with_device(hass: HomeAssistant, device: BluettiDevice) -> MockConfigEntry:
    device.coordinator = MagicMock()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    bluetti_data = BluettiData.__new__(BluettiData)
    bluetti_data.devices = [device]
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=bluetti_data,
        stomp_client=MagicMock(),
        coordinators={},
    )
    return entry


async def test_select_current_option_and_editability(hass: HomeAssistant) -> None:
    """Select current option and editability."""
    coordinator = _make_coordinator(hass)
    state = coordinator.device.get_state("SetCtrlWorkMode")

    entity = BluettiSelect(coordinator.device, state)

    assert entity.options == ["Standard", "Silent"]
    assert entity.current_option == "Standard"
    assert entity._readonly is False


async def test_select_readonly_state_keeps_options_populated(
    hass: HomeAssistant,
) -> None:
    """Select readonly state keeps options populated."""
    coordinator = _make_coordinator(hass)
    state = coordinator.device.get_state("InvWorkState")

    entity = BluettiSelect(coordinator.device, state)

    assert entity._readonly is True
    # Options must stay populated so current_option is never reported as
    # outside of the advertised options list.
    assert entity.options == ["Idle"]
    assert entity.current_option == "Idle"


async def test_select_readonly_option_cannot_be_changed(hass: HomeAssistant) -> None:
    """Select readonly option cannot be changed."""
    coordinator = _make_coordinator(hass)
    state = coordinator.device.get_state("InvWorkState")
    entity = BluettiSelect(coordinator.device, state)

    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("Idle")


async def test_select_invalid_option_raises(hass: HomeAssistant) -> None:
    """Select invalid option raises."""
    coordinator = _make_coordinator(hass)
    state = coordinator.device.get_state("SetCtrlWorkMode")
    entity = BluettiSelect(coordinator.device, state)

    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("does-not-exist")


async def test_select_setup_entry_creates_select_and_controls_it(
    hass: HomeAssistant,
) -> None:
    """Select setup entry creates a select entity and can change its option."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[_WORK_MODE_STATE],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = UnifyResponse(msgId="1", msgCode=0)
    entry = _entry_with_device(hass, device)
    added = []

    await select_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    select = added[0]
    assert isinstance(select, BluettiSelect)

    await select.async_select_option("Silent")
    assert select.current_option == "Silent"


async def test_select_option_raises_when_command_rejected(hass: HomeAssistant) -> None:
    """A rejected command must not silently look like it succeeded.

    Regression coverage for the same set_state_value() validation already
    covered in test_models.py, exercised here through the select entity
    that's the actual caller in production.
    """
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[_WORK_MODE_STATE],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = UnifyResponse(msgId="1", msgCode=1)
    entry = _entry_with_device(hass, device)
    added = []

    await select_setup_entry(hass, entry, added.extend)
    select = added[0]

    with pytest.raises(HomeAssistantError):
        await select.async_select_option("Silent")

    assert select.current_option == "Standard"
