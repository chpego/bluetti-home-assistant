"""Tests for the BLUETTI switch platform."""

from unittest.mock import AsyncMock, MagicMock

from pybluetti import UnifyResponse
import pytest

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.coordinator import BluettiDeviceCoordinator
from homeassistant.components.bluetti.models import (
    BluettiData,
    BluettiDevice,
    BluettiState,
)
from homeassistant.components.bluetti.switch import (
    BluettiSwitch,
    async_setup_entry as switch_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


def _make_coordinator(hass: HomeAssistant) -> BluettiDeviceCoordinator:
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test Device",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SetCtrlAc",
                "fnName": "AC Output",
                "fnValue": "0",
                "fnType": "SWITCH",
            }
        ],
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


async def test_switch_is_on_and_off(hass: HomeAssistant) -> None:
    """Switch is on and off."""
    coordinator = _make_coordinator(hass)
    state = coordinator.device.get_state("SetCtrlAc")

    entity = BluettiSwitch(coordinator.device, state)

    assert entity.is_on is False
    assert entity.name == "AC Output"
    assert entity.unique_id == "SN1_SetCtrlAc"


async def test_switch_power_toggle_available_even_when_offline(
    hass: HomeAssistant,
) -> None:
    """The power switch stays controllable even when the device reports offline."""
    coordinator = _make_coordinator(hass)
    coordinator.device.on_line = "0"
    # SetCtrlPowerOn is not in the fixture state list; add it directly.
    power_state = BluettiState(
        fn_code="SetCtrlPowerOn", fn_name="Power", fn_value="1", fn_type="SWITCH"
    )
    coordinator.device.states.append(power_state)

    entity = BluettiSwitch(coordinator.device, power_state)

    assert entity.available is True


async def test_switch_setup_entry_creates_switch_and_controls_it(
    hass: HomeAssistant,
) -> None:
    """Switch setup entry creates a switch entity and can turn it on and off."""
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SetCtrlAc",
                "fnName": "AC",
                "fnValue": "0",
                "fnType": "SWITCH",
            }
        ],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = UnifyResponse(msgId="1", msgCode=0)
    entry = _entry_with_device(hass, device)
    added = []

    await switch_setup_entry(hass, entry, added.extend)

    assert len(added) == 1
    switch = added[0]
    assert isinstance(switch, BluettiSwitch)
    assert switch.is_on is False

    await switch.async_turn_on()
    assert switch.is_on is True

    await switch.async_turn_off()
    assert switch.is_on is False


async def test_switch_turn_on_raises_when_command_rejected(hass: HomeAssistant) -> None:
    """A rejected command must not silently look like it succeeded.

    Regression coverage for the same set_state_value() validation already
    covered in test_models.py, exercised here through the switch entity
    that's the actual caller in production.
    """
    device = BluettiDevice(
        device_id="SN1",
        on_line="1",
        name="Test",
        sn="SN1",
        model="AC200L",
        state_list=[
            {
                "fnCode": "SetCtrlAc",
                "fnName": "AC",
                "fnValue": "0",
                "fnType": "SWITCH",
            }
        ],
    )
    device._api_client = AsyncMock()
    device._api_client.control_device.return_value = UnifyResponse(msgId="1", msgCode=1)
    entry = _entry_with_device(hass, device)
    added = []

    await switch_setup_entry(hass, entry, added.extend)
    switch = added[0]

    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()

    assert switch.is_on is False
