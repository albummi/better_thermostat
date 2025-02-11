import logging

from custom_components.better_thermostat.utils.const import (
    CONF_HOMEMATICIP,
    CONF_SLEEP_MODE,
    CONF_SLEEP_TEMPERATURE,
    CONF_SLEEP_DELAY,
    CONF_SLEEP_DELAY_AFTER,
    CONF_DOOR_OVERRIDE,
    CONF_DOOR_TEMPERATURE
)
from ..utils.helpers import convert_to_float
from datetime import datetime
from homeassistant.helpers import issue_registry as ir

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


@callback
async def trigger_temperature_change(self, event):
    """Handle temperature changes.

    Parameters
    ----------
    self :
            self instance of better_thermostat
    event :
            Event object from the eventbus. Contains the current trigger time.

    Returns
    -------
    None
    """
    if self.startup_running:
        return

    new_state = event.data.get("new_state")
    if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
        return

    _incoming_temperature = convert_to_float(
        str(new_state.state), self.device_name, "external_temperature"
    )

    _time_diff = 60

    try:
        for trv in self.all_trvs:
            if trv["advanced"][CONF_HOMEMATICIP]:
                _time_diff = 600
    except KeyError:
        pass

    if _incoming_temperature is None or _incoming_temperature < -50:
        # raise a ha repair notication
        _LOGGER.error(
            "better_thermostat %s: external_temperature is not a valid number: %s",
            self.device_name,
            new_state.state,
        )
        ir.async_create_issue(
            hass=self.hass,
            issue_id=f"missing_entity_{self.device_name}",
            issue_title=f"better_thermostat {self.device_name} has invalid external_temperature value",
            issue_severity="error",
            issue_description=f"better_thermostat {self.device_name} has invalid external_temperature: {new_state.state}",
            issue_category="config",
            issue_suggested_action="Please check the external_temperature sensor",
        )
        return

    if (
        _incoming_temperature != self.cur_temp
        and (datetime.now() - self.last_external_sensor_change).total_seconds()
        > _time_diff
    ):
        _LOGGER.debug(
            "better_thermostat %s: external_temperature changed from %s to %s",
            self.device_name,
            self.cur_temp,
            _incoming_temperature,
        )
        self.cur_temp = _incoming_temperature
        self.last_external_sensor_change = datetime.now()
        self.async_write_ha_state()
        await self.control_queue_task.put(self)
        
        # Handle sleep mode
        if hasattr(self, 'sleep_mode') and self.sleep_mode and hasattr(self, 'door_override') and self.door_override:
            if hasattr(self, 'door_open') and self.door_open:
                self.target_temperature = self.door_temperature
                _LOGGER.debug(
                    f"better_thermostat {self.device_name}: Door is open, setting temperature to {self.door_temperature} due to door override"
                )
            elif hasattr(self, 'sleep_mode') and self.sleep_mode:
                self.target_temperature = self.sleep_temperature
                _LOGGER.debug(
                    f"better_thermostat {self.device_name}: Sleep mode active, setting temperature to {self.sleep_temperature}"
                )
            else:
                self.target_temperature = self.default_target_temperature
                _LOGGER.debug(
                    f"better_thermostat {self.device_name}: Setting temperature to default target temperature {self.default_target_temperature}"
                )
        self.async_write_ha_state()
        await self.control_queue_task.put(self)
