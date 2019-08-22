"""MySensors platform that offers a Climate (MySensors-HVAC) component."""
from homeassistant.components import mysensors
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN, STATE_AUTO,
    STATE_COOL, STATE_HEAT, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, TEMP_CELSIUS, TEMP_FAHRENHEIT)

DICT_HA_TO_MYS = {
    STATE_AUTO: 'AutoChangeOver',
    STATE_COOL: 'CoolOn',
    STATE_HEAT: 'HeatOn',
    STATE_OFF: 'Off',
}
DICT_MYS_TO_HA = {
    'AutoChangeOver': STATE_AUTO,
    'CoolOn': STATE_COOL,
    'HeatOn': STATE_HEAT,
    'Off': STATE_OFF,
}

FAN_LIST = ['Auto', 'Min', 'Normal', 'Max']
OPERATION_LIST = [STATE_OFF, STATE_AUTO, STATE_COOL, STATE_HEAT]


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the mysensors climate."""
    mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsHVAC,
        async_add_entities=async_add_entities)


class MySensorsHVAC(mysensors.device.MySensorsEntity, ClimateDevice):
    """Representation of a MySensors HVAC."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = SUPPORT_OPERATION_MODE
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SPEED in self._values:
            features = features | SUPPORT_FAN_MODE
        if (set_req.V_HVAC_SETPOINT_COOL in self._values and
                set_req.V_HVAC_SETPOINT_HEAT in self._values):
            features = (
                features | SUPPORT_TARGET_TEMPERATURE_HIGH |
                SUPPORT_TARGET_TEMPERATURE_LOW)
        else:
            features = features | SUPPORT_TARGET_TEMPERATURE
        return features

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS if self.gateway.metric else TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        value = self._values.get(self.gateway.const.SetReq.V_TEMP)

        if value is not None:
            value = float(value)

        return value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_COOL in self._values and \
                set_req.V_HVAC_SETPOINT_HEAT in self._values:
            return None
        temp = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        if temp is None:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        return float(temp) if temp is not None else None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_HEAT in self._values:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
            return float(temp) if temp is not None else None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_COOL in self._values:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
            return float(temp) if temp is not None else None

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._values.get(self.value_type)

    @property
    def operation_list(self):
        """List of available operation modes."""
        return OPERATION_LIST

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._values.get(self.gateway.const.SetReq.V_HVAC_SPEED)

    @property
    def fan_list(self):
        """List of available fan modes."""
        return FAN_LIST

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        temp = kwargs.get(ATTR_TEMPERATURE)
        low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        heat = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        cool = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        updates = []
        if temp is not None:
            if heat is not None:
                # Set HEAT Target temperature
                value_type = set_req.V_HVAC_SETPOINT_HEAT
            elif cool is not None:
                # Set COOL Target temperature
                value_type = set_req.V_HVAC_SETPOINT_COOL
            if heat is not None or cool is not None:
                updates = [(value_type, temp)]
        elif all(val is not None for val in (low, high, heat, cool)):
            updates = [
                (set_req.V_HVAC_SETPOINT_HEAT, low),
                (set_req.V_HVAC_SETPOINT_COOL, high)]
        for value_type, value in updates:
            self.gateway.set_child_value(
                self.node_id, self.child_id, value_type, value)
            if self.gateway.optimistic:
                # Optimistically assume that device has changed state
                self._values[value_type] = value
                self.async_schedule_update_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_HVAC_SPEED, fan_mode)
        if self.gateway.optimistic:
            # Optimistically assume that device has changed state
            self._values[set_req.V_HVAC_SPEED] = fan_mode
            self.async_schedule_update_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type,
            DICT_HA_TO_MYS[operation_mode])
        if self.gateway.optimistic:
            # Optimistically assume that device has changed state
            self._values[self.value_type] = operation_mode
            self.async_schedule_update_ha_state()

    async def async_update(self):
        """Update the controller with the latest value from a sensor."""
        await super().async_update()
        self._values[self.value_type] = DICT_MYS_TO_HA[
            self._values[self.value_type]]
