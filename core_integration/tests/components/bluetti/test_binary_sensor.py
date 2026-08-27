"""Tests for the BLUETTI binary_sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.bluetti import BluettiRuntimeData
from homeassistant.components.bluetti.binary_sensor import (
    BluettiOnlineBinarySensor,
    async_setup_entry as binary_sensor_setup_entry,
)
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.coordinator import BluettiDeviceCoordinator
from homeassistant.components.bluetti.models import BluettiData, BluettiDevice
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _make_coordinator(
    hass: HomeAssistant, *, on_line: str = "1"
) -> BluettiDeviceCoordinator:
    device = BluettiDevice(
        device_id="SN1", on_line=on_line, name="Test Device", sn="SN1", model="AC200L"
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return BluettiDeviceCoordinator(hass, entry, device)


def _entry_with_devices(
    hass: HomeAssistant, devices: list[BluettiDevice]
) -> MockConfigEntry:
    for device in devices:
        device.coordinator = MagicMock()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    bluetti_data = BluettiData.__new__(BluettiData)
    bluetti_data.devices = devices
    entry.runtime_data = BluettiRuntimeData(
        auth=MagicMock(),
        bluetti_devices=bluetti_data,
        stomp_client=MagicMock(),
        coordinators={},
    )
    return entry


async def test_binary_sensor_is_on_when_device_online(hass: HomeAssistant) -> None:
    """Binary sensor is on when device online."""
    coordinator = _make_coordinator(hass, on_line="1")

    entity = BluettiOnlineBinarySensor(coordinator.device)

    assert entity.is_on is True
    assert entity.has_entity_name is True
    assert entity.unique_id == "SN1_online"
    assert entity.device_info["identifiers"] == {(DOMAIN, "SN1")}


async def test_binary_sensor_is_off_when_device_offline(hass: HomeAssistant) -> None:
    """Binary sensor is off when device offline."""
    coordinator = _make_coordinator(hass, on_line="0")

    entity = BluettiOnlineBinarySensor(coordinator.device)

    assert entity.is_on is False


async def test_binary_sensor_stays_available_while_device_is_offline(
    hass: HomeAssistant,
) -> None:
    """The connectivity sensor itself must not go unavailable when offline.

    Regression guard: unlike BluettiEntity's state-sourced entities (which
    correctly go unavailable when the device is offline, since their
    readings are then stale), this entity's whole purpose is to report that
    same offline state via is_on=False - it must not instead disappear as
    "unavailable".
    """
    coordinator = _make_coordinator(hass, on_line="0")

    entity = BluettiOnlineBinarySensor(coordinator.device)

    assert entity.available is True
    assert entity.is_on is False


async def test_binary_sensor_setup_entry_creates_one_per_device(
    hass: HomeAssistant,
) -> None:
    """Binary sensor setup entry creates one entity per device."""
    device1 = BluettiDevice(
        device_id="SN1", on_line="1", name="First", sn="SN1", model="AC200L"
    )
    device2 = BluettiDevice(
        device_id="SN2", on_line="0", name="Second", sn="SN2", model="AC200L"
    )
    entry = _entry_with_devices(hass, [device1, device2])
    added = []

    await binary_sensor_setup_entry(hass, entry, added.extend)

    assert len(added) == 2
    assert all(isinstance(e, BluettiOnlineBinarySensor) for e in added)
    assert {e.unique_id for e in added} == {"SN1_online", "SN2_online"}


async def test_binary_sensor_setup_entry_with_no_devices_adds_nothing(
    hass: HomeAssistant,
) -> None:
    """Binary sensor setup entry with no devices adds nothing."""
    entry = _entry_with_devices(hass, [])
    added = []

    await binary_sensor_setup_entry(hass, entry, added.extend)

    assert added == []
