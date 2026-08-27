"""Binary sensor platform for the BLUETTI integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BluettiConfigEntry
from .const import DOMAIN
from .coordinator import BluettiDeviceCoordinator
from .models import BluettiData, BluettiDevice

# Entities only read from the coordinator and never poll or call the API
# themselves, so there is no need to limit concurrent updates.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluettiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bluetti binary sensors from config entry."""
    bluetti_devices: BluettiData = config_entry.runtime_data.bluetti_devices

    entities = [BluettiOnlineBinarySensor(device) for device in bluetti_devices.devices]

    if entities:
        async_add_entities(entities)


class BluettiOnlineBinarySensor(
    CoordinatorEntity[BluettiDeviceCoordinator], BinarySensorEntity
):
    """Whether the device currently reports itself online to the BLUETTI cloud.

    Unlike BluettiEntity's state-sourced entities, this has no corresponding
    BluettiState - the cloud's on-line flag is a top-level product field
    (BluettiDevice.on_line), not an entry in stateList. This also means it
    must not reuse BluettiEntity.available's "unavailable when offline"
    behavior: this entity's whole purpose is to show is_on=False when the
    device is offline, which requires staying available while that happens.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(self, device: BluettiDevice) -> None:
        """Initialize the binary sensor from its owning device."""
        assert device.coordinator is not None, (
            "entities must be created after the device's coordinator is wired up"
        )
        super().__init__(device.coordinator)
        self._device = device
        self._attr_unique_id = f"{device.device_id}_online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.sn,
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the device reports itself online."""
        return self._device.online
