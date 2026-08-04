"""Config and subentry flows for the Climate Flow integration."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    DurationSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)
from homeassistant.util import slugify

from .const import (
    CONF_DURATION,
    CONF_FAN_MODE,
    CONF_FLOW_ID,
    CONF_HVAC_MODE,
    CONF_NAME,
    CONF_PRESET_MODE,
    CONF_STAGES,
    CONF_SWING_MODE,
    CONF_TARGETS,
    CONF_TEMPERATURE,
    CONF_TEMPERATURE_CELSIUS,
    DOMAIN,
    FLOW_SUBENTRY_TYPE,
)
from .flow import ClimateState, FlowStage, SavedFlow, is_valid_flow_id
from .flow_capabilities import (
    InvalidClimateTargetsError,
    SharedClimateCapabilities,
    selector_options,
    shared_capabilities,
    temperature_from_celsius,
    temperature_to_celsius,
)


def _duration_seconds(duration: Mapping[str, float]) -> float:
    """Convert a Home Assistant duration selector result to seconds."""
    seconds = (
        duration.get("days", 0) * 86400
        + duration.get("hours", 0) * 3600
        + duration.get("minutes", 0) * 60
        + duration.get("seconds", 0)
        + duration.get("milliseconds", 0) / 1000
    )
    if seconds <= 0:
        raise ValueError
    return seconds


def _duration_suggestion(seconds: float | None) -> dict[str, float] | None:
    """Convert stored seconds to a duration-selector suggestion."""
    if seconds is None:
        return None
    whole_seconds, milliseconds = divmod(seconds, 1)
    whole_seconds = int(whole_seconds)
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    suggestion: dict[str, float] = {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds_part,
    }
    if milliseconds:
        suggestion["milliseconds"] = round(milliseconds * 1000, 3)
    return suggestion


class InvalidStageInputError(ValueError):
    """Raised when a stage form value is not valid for its selected targets."""

    def __init__(self, field: str) -> None:
        """Set the translated field that should receive the error."""
        self.field = field


class ClimateFlowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Climate Flow's singleton config entry and saved flows."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the saved-flow subentry type."""
        return {FLOW_SUBENTRY_TYPE: ClimateFlowSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial integration setup step."""
        if user_input is not None:
            return self.async_create_entry(title="Climate Flow", data={})

        return self.async_show_form(step_id="user")

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Offer the user immediate creation of their first saved flow."""
        entry = result["result"]
        subentry_result = await self.hass.config_entries.subentries.async_init(
            (entry.entry_id, FLOW_SUBENTRY_TYPE),
            context=SubentryFlowContext(source=SOURCE_USER),
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result


class ClimateFlowSubentryFlow(ConfigSubentryFlow):
    """Create and reconfigure one saved two-stage flow."""

    _capabilities: SharedClimateCapabilities
    _flow_id: str
    _name: str
    _stages: list[FlowStage]
    _targets: tuple[str, ...]

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Collect the display name before suggesting a logical ID."""
        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            if name:
                self._name = name
                self._flow_id = slugify(name)
                self._targets = ()
                self._stages = []
                return await self.async_step_details()
            return self.async_show_form(
                step_id="user",
                data_schema=self._name_schema(),
                errors={CONF_NAME: "invalid_name"},
            )

        return self.async_show_form(step_id="user", data_schema=self._name_schema())

    async def async_step_reconfigure(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Load a saved flow before collecting its replacement definition."""
        if user_input is not None:
            raise ValueError("Reconfigure input is handled by the details step")

        subentry = self._get_reconfigure_subentry()
        data = subentry.data
        self._name = subentry.title
        self._flow_id = str(data[CONF_FLOW_ID])
        self._targets = tuple(data[CONF_TARGETS])
        self._stages = self._stages_from_data(data)
        return await self.async_step_details()

    async def async_step_details(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Collect the flow identity and selected climate targets."""
        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            flow_id = str(user_input[CONF_FLOW_ID]).strip()
            targets = tuple(user_input[CONF_TARGETS])
            errors = self._validate_details(name, flow_id, targets)
            if not errors:
                try:
                    capabilities = shared_capabilities(self.hass, targets)
                except InvalidClimateTargetsError:
                    errors["base"] = "invalid_targets"
                else:
                    if not capabilities.hvac_modes:
                        errors["base"] = "unsupported_targets"
                    else:
                        self._name = name
                        self._flow_id = flow_id
                        self._targets = targets
                        self._capabilities = capabilities
                        return await self.async_step_stage_1()
            return self.async_show_form(
                step_id="details",
                data_schema=self._details_schema(),
                errors=errors,
            )

        if self._targets:
            try:
                self._capabilities = shared_capabilities(self.hass, self._targets)
            except InvalidClimateTargetsError:
                pass
        return self.async_show_form(
            step_id="details", data_schema=self._details_schema()
        )

    async def async_step_stage_1(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Collect the required-duration first stage."""
        if user_input is not None:
            try:
                stage = self._stage_from_input(user_input, duration_required=True)
            except InvalidStageInputError as err:
                return self.async_show_form(
                    step_id="stage_1",
                    data_schema=self._stage_schema(1, duration_required=True),
                    errors={err.field: "invalid_stage"},
                )
            except ValueError:
                return self.async_show_form(
                    step_id="stage_1",
                    data_schema=self._stage_schema(1, duration_required=True),
                    errors={CONF_DURATION: "invalid_duration"},
                )
            self._stages = [stage]
            return await self.async_step_stage_2()

        return self.async_show_form(
            step_id="stage_1",
            data_schema=self._stage_schema(1, duration_required=True),
        )

    async def async_step_stage_2(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Collect the optional-duration final stage and save the flow."""
        if user_input is not None:
            try:
                stage = self._stage_from_input(user_input, duration_required=False)
            except InvalidStageInputError as err:
                return self.async_show_form(
                    step_id="stage_2",
                    data_schema=self._stage_schema(2, duration_required=False),
                    errors={err.field: "invalid_stage"},
                )
            except ValueError:
                return self.async_show_form(
                    step_id="stage_2",
                    data_schema=self._stage_schema(2, duration_required=False),
                    errors={CONF_DURATION: "invalid_duration"},
                )

            saved_flow = SavedFlow(
                flow_id=self._flow_id,
                targets=self._targets,
                stages=(self._stages[0], stage),
            )
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    title=self._name,
                    data=saved_flow.as_dict(),
                    unique_id=self._flow_id,
                )
            return self.async_create_entry(
                title=self._name,
                data=saved_flow.as_dict(),
                unique_id=self._flow_id,
            )

        return self.async_show_form(
            step_id="stage_2",
            data_schema=self._stage_schema(2, duration_required=False),
        )

    def _name_schema(self) -> vol.Schema:
        """Return the first-step schema."""
        return vol.Schema({vol.Required(CONF_NAME): TextSelector()})

    def _details_schema(self) -> vol.Schema:
        """Return the flow details schema with its current suggestions."""
        schema: dict[Any, Any] = {
            vol.Required(CONF_NAME, default=self._name): TextSelector(),
            vol.Required(CONF_FLOW_ID, default=self._flow_id): TextSelector(),
            vol.Required(CONF_TARGETS, default=list(self._targets)): EntitySelector(
                EntitySelectorConfig(filter={"domain": "climate"}, multiple=True)
            ),
        }
        return vol.Schema(schema)

    def _stage_schema(self, index: int, *, duration_required: bool) -> vol.Schema:
        """Return the schema for one fixed Milestone 2 stage."""
        suggested = self._stages[index - 1] if len(self._stages) >= index else None
        state = suggested.climate_state if suggested else None
        capabilities = self._capabilities
        hvac_selector = SelectSelector(
            SelectSelectorConfig(options=selector_options(capabilities.hvac_modes))
        )
        schema: dict[Any, Any] = {
            self._field(
                CONF_HVAC_MODE,
                state.hvac_mode if state else None,
                required=True,
            ): hvac_selector
        }
        temperature_selector = NumberSelector(
            NumberSelectorConfig(
                min=capabilities.minimum_temperature,
                max=capabilities.maximum_temperature,
                step=0.1,
                unit_of_measurement=self.hass.config.units.temperature_unit,
                mode=NumberSelectorMode.BOX,
            )
        )
        temperature_suggestion = (
            temperature_from_celsius(self.hass, state.temperature_celsius)
            if state and state.temperature_celsius is not None
            else None
        )
        schema[
            self._field(
                CONF_TEMPERATURE,
                temperature_suggestion,
                required=False,
            )
        ] = temperature_selector
        self._add_optional_mode(
            schema,
            CONF_FAN_MODE,
            capabilities.fan_modes,
            state.fan_mode if state else None,
        )
        self._add_optional_mode(
            schema,
            CONF_SWING_MODE,
            capabilities.swing_modes,
            state.swing_mode if state else None,
        )
        self._add_optional_mode(
            schema,
            CONF_PRESET_MODE,
            capabilities.preset_modes,
            state.preset_mode if state else None,
        )
        duration_suggestion = _duration_suggestion(
            suggested.duration_seconds if suggested else None
        )
        schema[
            self._field(
                CONF_DURATION,
                duration_suggestion,
                required=duration_required,
            )
        ] = DurationSelector()
        return vol.Schema(schema)

    @staticmethod
    def _field(key: str, suggested: Any, *, required: bool) -> Any:
        """Return a schema key with an optional suggested value."""
        if required:
            return (
                vol.Required(key)
                if suggested is None
                else vol.Required(key, default=suggested)
            )
        return (
            vol.Optional(key)
            if suggested is None
            else vol.Optional(key, default=suggested)
        )

    @staticmethod
    def _add_optional_mode(
        schema: dict[Any, Any], key: str, values: tuple[str, ...], suggested: str | None
    ) -> None:
        """Add an optional shared mode selector when targets support it."""
        if not values:
            return
        selector = SelectSelector(
            SelectSelectorConfig(options=selector_options(values))
        )
        field = ClimateFlowSubentryFlow._field(key, suggested, required=False)
        schema[field] = selector

    def _validate_details(
        self, name: str, flow_id: str, targets: tuple[str, ...]
    ) -> dict[str, str]:
        """Return translated field errors for flow identity and targets."""
        errors: dict[str, str] = {}
        if not name:
            errors[CONF_NAME] = "invalid_name"
        if not is_valid_flow_id(flow_id):
            errors[CONF_FLOW_ID] = "invalid_flow_id"
        elif any(
            subentry.unique_id == flow_id
            and subentry.subentry_id != self._reconfigured_subentry_id()
            for subentry in self._get_entry().get_subentries_of_type(FLOW_SUBENTRY_TYPE)
        ):
            errors[CONF_FLOW_ID] = "duplicate_flow_id"
        if not targets:
            errors[CONF_TARGETS] = "no_targets"
        return errors

    def _reconfigured_subentry_id(self) -> str | None:
        """Return the subentry currently being updated, if any."""
        if self.source != SOURCE_RECONFIGURE:
            return None
        return self._get_reconfigure_subentry().subentry_id

    def _stage_from_input(
        self, user_input: Mapping[str, object], *, duration_required: bool
    ) -> FlowStage:
        """Normalize a stage form result for persistent storage."""
        duration: float | None = None
        if CONF_DURATION in user_input:
            duration_input = user_input[CONF_DURATION]
            if not isinstance(duration_input, Mapping):
                raise ValueError
            duration = _duration_seconds(duration_input)
        elif duration_required:
            raise ValueError

        temperature: float | None = None
        if CONF_TEMPERATURE in user_input:
            temperature_input = float(user_input[CONF_TEMPERATURE])
            if not (
                self._capabilities.minimum_temperature
                <= temperature_input
                <= self._capabilities.maximum_temperature
            ):
                raise InvalidStageInputError(CONF_TEMPERATURE)
            temperature = temperature_to_celsius(self.hass, temperature_input)

        hvac_mode = str(user_input[CONF_HVAC_MODE])
        if hvac_mode not in self._capabilities.hvac_modes:
            raise InvalidStageInputError(CONF_HVAC_MODE)

        fan_mode = self._validated_optional_mode(
            user_input, CONF_FAN_MODE, self._capabilities.fan_modes
        )
        swing_mode = self._validated_optional_mode(
            user_input, CONF_SWING_MODE, self._capabilities.swing_modes
        )
        preset_mode = self._validated_optional_mode(
            user_input, CONF_PRESET_MODE, self._capabilities.preset_modes
        )

        return FlowStage(
            climate_state=ClimateState(
                hvac_mode=hvac_mode,
                temperature_celsius=temperature,
                fan_mode=fan_mode,
                swing_mode=swing_mode,
                preset_mode=preset_mode,
            ),
            duration_seconds=duration,
        )

    @staticmethod
    def _optional_string(user_input: Mapping[str, object], key: str) -> str | None:
        """Return an optional selector value."""
        value = user_input.get(key)
        return str(value) if value is not None else None

    @classmethod
    def _validated_optional_mode(
        cls,
        user_input: Mapping[str, object],
        key: str,
        supported_values: tuple[str, ...],
    ) -> str | None:
        """Return an optional mode after validating its target support."""
        value = cls._optional_string(user_input, key)
        if value is not None and value not in supported_values:
            raise InvalidStageInputError(key)
        return value

    @staticmethod
    def _stages_from_data(data: Mapping[str, Any]) -> list[FlowStage]:
        """Load stored Milestone 2 stages for reconfiguration suggestions."""
        stages: list[FlowStage] = []
        for stored_stage in data[CONF_STAGES]:
            stored_state = stored_stage["climate_state"]
            stages.append(
                FlowStage(
                    climate_state=ClimateState(
                        hvac_mode=stored_state[CONF_HVAC_MODE],
                        temperature_celsius=stored_state.get(CONF_TEMPERATURE_CELSIUS),
                        fan_mode=stored_state.get(CONF_FAN_MODE),
                        swing_mode=stored_state.get(CONF_SWING_MODE),
                        preset_mode=stored_state.get(CONF_PRESET_MODE),
                    ),
                    duration_seconds=stored_stage.get(CONF_DURATION),
                )
            )
        return stages
