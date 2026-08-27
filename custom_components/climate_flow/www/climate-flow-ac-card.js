const TRANSITIONS_SENSOR = "sensor.pending_transitions";

class ClimateFlowAcCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity || !config.entity.startsWith("climate.")) {
      throw new Error("Set entity to a climate entity.");
    }
    if (config.off_states && !Array.isArray(config.off_states)) {
      throw new Error("off_states must be a list of climate states.");
    }
    if (config.cleaning_states && !Array.isArray(config.cleaning_states)) {
      throw new Error("cleaning_states must be a list of climate states.");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  disconnectedCallback() {
    this._stopTransitionTicking();
  }

  _isOff(state) {
    const offStates = this._config.off_states ?? ["off", "cleaning"];
    return offStates.includes(state.state);
  }

  _isCleaning(state) {
    const cleaningStates = this._config.cleaning_states ?? ["cleaning"];
    return cleaningStates.includes(state.state)
      || cleaningStates.includes(state.attributes.hvac_action)
      || cleaningStates.includes(state.attributes.preset_mode)
      || this._isEnabled(state.attributes.self_cleaning);
  }

  _render() {
    if (!this._config || !this._hass) return;

    const state = this._hass.states[this._config.entity];
    if (!state) {
      this.innerHTML = `<ha-card><div class="error">Entity not found: ${this._config.entity}</div></ha-card>`;
      return;
    }

    const attributes = state.attributes;
    const isCleaning = this._isCleaning(state);
    const isOff = this._isOff(state) || isCleaning;
    const isUnavailable = ["unavailable", "unknown"].includes(state.state);
    const temperature = Number(attributes.temperature);
    const currentTemperature = Number(attributes.current_temperature);
    const step = Number(attributes.target_temp_step) || 1;
    const minimum = Number(attributes.min_temp);
    const maximum = Number(attributes.max_temp);
    const canDecrease = !Number.isFinite(temperature) || !Number.isFinite(minimum) || temperature > minimum;
    const canIncrease = !Number.isFinite(temperature) || !Number.isFinite(maximum) || temperature < maximum;
    const canUseTemperatureSlider = Number.isFinite(temperature)
      && Number.isFinite(minimum)
      && Number.isFinite(maximum);
    const sliderTemperature = Number.isFinite(this._sliderTemperature)
      ? this._sliderTemperature
      : temperature;
    const name = this._config.name ?? attributes.friendly_name ?? this._config.entity;
    const mode = isCleaning ? "cleaning" : attributes.hvac_action ?? state.state;
    const reportedSwingMode = attributes.swing_mode;
    const hasActiveSwingMode = this._normalizeSwingMode(reportedSwingMode) !== "off";
    const selectedSwing = hasActiveSwingMode ? reportedSwingMode : undefined;
    const mappedSwingModes = ["fixed 1", "fixed 3", "fixed 5"];
    const otherSwingMode = selectedSwing && !mappedSwingModes.includes(this._normalizeSwingMode(selectedSwing)) ? selectedSwing : undefined;
    const controlsDisabled = isOff || isUnavailable ? "disabled" : "";
    const powerClass = isCleaning ? "power-cleaning" : isOff || isUnavailable ? "power-off" : "power-on";
    const powerLabel = isCleaning ? "Cleaning" : isUnavailable ? "Unavailable" : isOff ? "Turn on" : "Turn off";
    const powerActionId = "power";
    const decreaseActionId = `temperature:-${step}`;
    const increaseActionId = `temperature:${step}`;
    const pendingTransition = this._hass.states[TRANSITIONS_SENSOR]?.attributes?.[this._config.entity];
    if (pendingTransition) {
      this._transitionTickInterval ??= setInterval(() => this._render(), 1000);
    } else {
      this._stopTransitionTicking();
    }
    const transitionLabel = pendingTransition ? "Edit or cancel the timed transition" : "Set a timed transition";

    this.innerHTML = `
      <style>
        :host { display: block; min-width: 0; }
        ha-card { box-sizing: border-box; min-width: 0; padding: clamp(8px, 4vw, 16px); }
        .header, .temperature, .swing { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .header { margin-bottom: 20px; font-size: 1.1em; font-weight: 500; }
        .header-left, .header-right { align-items: center; display: flex; gap: 8px; }
        .title { display: grid; gap: 2px; min-width: 0; }
        .more-info { font-size: 1.3em; line-height: 1; min-height: 36px; min-width: 36px; padding: 0; }
        .mode-state, .swing-state { color: var(--secondary-text-color); font-size: 0.8em; font-weight: 400; }
        .mode-state.timed { color: var(--warning-color, #ff9800); font-weight: 500; font-variant-numeric: tabular-nums; }
        .timer.armed { border-color: var(--warning-color, #ff9800); border-style: dashed; color: var(--warning-color, #ff9800); }
        .transition-panel { background: var(--secondary-background-color); border-radius: 10px; margin-bottom: 18px; padding: 12px; }
        .transition-panel-title { align-items: center; color: var(--warning-color, #ff9800); display: flex; font-size: 0.78em; font-weight: 700; gap: 6px; letter-spacing: 0.02em; margin-bottom: 10px; text-transform: uppercase; }
        .transition-field-label { color: var(--secondary-text-color); font-size: 0.78em; font-weight: 600; margin: 0 0 6px; }
        .transition-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
        .transition-chip { aspect-ratio: auto; background: var(--card-background-color, var(--ha-card-background)); border: 1.5px solid var(--divider-color); border-radius: 999px; color: var(--primary-text-color); cursor: pointer; font-size: 0.8em; font-weight: 600; min-height: 0; min-width: 0; padding: 6px 12px; }
        .transition-chip.selected { background: var(--warning-color, #ff9800); border-color: var(--warning-color, #ff9800); color: #fff; }
        .transition-stepper { align-items: center; display: flex; gap: 10px; justify-content: center; margin-bottom: 12px; }
        .transition-stepper button { min-height: 32px; min-width: 32px; }
        .transition-stepper-value { font-variant-numeric: tabular-nums; font-weight: 600; min-width: 5em; text-align: center; }
        .transition-segmented { background: var(--card-background-color, var(--ha-card-background)); border-radius: 999px; display: flex; flex-wrap: wrap; gap: 2px; margin-bottom: 12px; padding: 3px; }
        .transition-segmented button { aspect-ratio: auto; background: transparent; border: 0; border-radius: 999px; color: var(--primary-text-color); cursor: pointer; flex: 1; font-size: 0.8em; font-weight: 600; min-height: 0; min-width: 0; padding: 7px 0; }
        .transition-segmented button.selected { background: var(--warning-color, #ff9800); color: #fff; }
        .transition-panel-footer { align-items: center; display: flex; gap: 10px; justify-content: flex-end; }
        .transition-text-button { aspect-ratio: auto; background: none; border: 0; color: var(--secondary-text-color); cursor: pointer; font-size: 0.8em; font-weight: 600; min-height: 0; min-width: 0; padding: 8px 6px; }
        .transition-start-button { aspect-ratio: auto; background: var(--warning-color, #ff9800); border: 0; border-radius: 999px; color: #fff; cursor: pointer; font-size: 0.85em; font-weight: 700; min-height: 0; min-width: 0; padding: 9px 16px; }
        .temperature-section { position: relative; }
        .temperature { display: grid; gap: 8px; grid-template-columns: 40px minmax(4.5em, auto) 40px; justify-content: center; margin: 0 auto 4px; max-width: 200px; width: 100%; }
        .temperature-value { min-width: 4.5em; text-align: center; font-size: 2em; font-weight: 400; }
        .temperature-trigger { background: transparent; border: 0; border-radius: 4px; min-height: 0; min-width: 0; padding: 0; }
        .temperature-trigger:active:not(:disabled) { background: var(--secondary-background-color); color: var(--primary-text-color); }
        .temperature-slider-row { align-items: center; background: var(--ha-card-background, var(--card-background-color)); bottom: calc(100% + 4px); box-sizing: border-box; display: flex; gap: 8px; left: 50%; margin: 0; max-width: 260px; padding: 4px 8px; position: absolute; transform: translateX(-50%); width: 100%; z-index: 1; }
        .temperature-slider { accent-color: var(--primary-color); flex: 1; min-width: 0; }
        .temperature-slider-value { font-variant-numeric: tabular-nums; min-width: 3em; text-align: right; }
        .slider-work-indicator { animation: rotate-work-indicator 0.8s linear infinite; border: 2px solid transparent; border-radius: 50%; border-right-color: var(--primary-color); border-top-color: var(--primary-color); box-shadow: 0 0 6px var(--primary-color); height: 14px; width: 14px; }
        .current-temperature { color: var(--secondary-text-color); font-size: 0.9em; margin-bottom: 18px; text-align: center; }
        .swing { justify-content: center; }
        .swing-buttons { display: flex; gap: 12px; }
        button { aspect-ratio: 1 / 1; border: 3px solid transparent; border-radius: 50%; background: var(--secondary-background-color); color: var(--primary-text-color); cursor: pointer; flex-shrink: 0; font: inherit; min-width: 44px; min-height: 44px; padding: 8px; position: relative; }
        button:active:not(:disabled), button.selected { background: var(--primary-color); color: var(--text-primary-color); }
        button:disabled { cursor: default; opacity: 0.45; }
        .button-label { align-items: center; display: inline-flex; height: 100%; justify-content: center; width: 100%; }
        .work-indicator { animation: rotate-work-indicator 0.8s linear infinite; border: 3px solid transparent; border-radius: inherit; border-right-color: var(--primary-color); border-top-color: var(--primary-color); box-shadow: 0 0 8px var(--primary-color); inset: -3px; pointer-events: none; position: absolute; }
        @keyframes rotate-work-indicator { to { transform: rotate(360deg); } }
        .swing-icon { display: block; height: 28px; margin: auto; width: 28px; }
        .swing-ray { fill: none; opacity: 0.28; stroke: currentColor; stroke-linecap: round; stroke-width: 2.5; }
        .swing-ray.active { opacity: 1; stroke-width: 4; }
        .power-on { border-color: currentColor; color: var(--success-color, #4caf50); }
        .power-off { border-color: currentColor; color: var(--error-color, #f44336); }
        .power-cleaning { border-color: var(--info-color, #2196f3); border-style: dashed; color: var(--info-color, #2196f3); }
        .error { padding: 16px; color: var(--error-color); }
      </style>
      <ha-card>
        <div class="header">
          <div class="header-left">
            <button class="more-info" data-action="more-info" aria-label="Open climate controls" title="Open climate controls">⋮</button>
            <div class="title">
              <span>${this._escape(name)}</span>
              <span class="mode-state ${pendingTransition ? "timed" : ""}">${pendingTransition ? this._escape(this._transitionCountdownLabel(pendingTransition)) : this._escape(this._formatState(mode))}</span>
            </div>
          </div>
          <div class="header-right">
            <button class="timer ${pendingTransition ? "armed" : ""}" data-action="toggle-transition-panel" aria-label="${transitionLabel}" title="${transitionLabel}">${this._buttonContent("⏱", false)}</button>
            <button class="power ${powerClass}" data-action="power" aria-label="${powerLabel}" title="${powerLabel}" ${isUnavailable || this._isActionPending(powerActionId) ? "disabled" : ""}>${this._buttonContent("⏻", this._isActionPending(powerActionId))}</button>
          </div>
        </div>
        ${this._transitionPanelOpen ? this._transitionPanelHtml(state, pendingTransition) : ""}
        <div class="temperature-section">
          ${this._sliderOpen && canUseTemperatureSlider ? `<div class="temperature-slider-row"><input class="temperature-slider" data-action="temperature-slider" type="range" min="${minimum}" max="${maximum}" step="${step}" value="${sliderTemperature}" aria-label="Target temperature" ${this._isActionPending("temperature-slider") ? "disabled" : ""}><span class="temperature-slider-value">${sliderTemperature} ${this._escape(attributes.temperature_unit ?? "°")}</span>${this._isActionPending("temperature-slider") ? '<span class="slider-work-indicator" aria-label="Setting temperature"></span>' : ""}</div>` : ""}
          <div class="temperature">
            <button data-action="temperature" data-offset="-${step}" aria-label="Decrease temperature" ${controlsDisabled} ${canDecrease && !this._isActionPending(decreaseActionId) ? "" : "disabled"}>${this._buttonContent("−", this._isActionPending(decreaseActionId))}</button>
            <button class="temperature-value temperature-trigger" data-action="toggle-temperature-slider" aria-label="Set target temperature" title="Set target temperature" ${controlsDisabled || !canUseTemperatureSlider ? "disabled" : ""}>${Number.isFinite(temperature) ? `${temperature} ${this._escape(attributes.temperature_unit ?? "°")}` : "—"}</button>
            <button data-action="temperature" data-offset="${step}" aria-label="Increase temperature" ${controlsDisabled} ${canIncrease && !this._isActionPending(increaseActionId) ? "" : "disabled"}>${this._buttonContent("+", this._isActionPending(increaseActionId))}</button>
          </div>
        </div>
        ${Number.isFinite(currentTemperature) ? `<div class="current-temperature">Current: ${currentTemperature} ${this._escape(attributes.temperature_unit ?? "°")}</div>` : ""}
        <div class="swing" aria-label="Vertical swing direction">
          <div class="swing-buttons">
            ${this._swingButton("fixed 5", 4, "Bottom", selectedSwing, controlsDisabled)}
            ${this._swingButton("fixed 3", 2, "Middle", selectedSwing, controlsDisabled)}
            ${this._swingButton("fixed 1", 0, "Top", selectedSwing, controlsDisabled)}
          </div>
          ${otherSwingMode ? `<span class="swing-state">${this._escape(this._formatState(otherSwingMode))}</span>` : ""}
        </div>
      </ha-card>`;

    this.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => this._handleAction(button, state));
    });
    const slider = this.querySelector('[data-action="temperature-slider"]');
    slider?.addEventListener("input", () => {
      this._sliderTemperature = Number(slider.value);
      this.querySelector(".temperature-slider-value").textContent = `${slider.value} ${attributes.temperature_unit ?? "°"}`;
    });
    slider?.addEventListener("change", () => {
      this._asyncSetSliderTemperature(Number(slider.value), state);
    });
  }

  _swingButton(value, highlightedIndex, label, selectedSwing, disabled) {
    const selected = this._normalizeSwingMode(value) === this._normalizeSwingMode(selectedSwing) ? "selected" : "";
    const pending = this._isActionPending(`swing:${value}`);
    return `<button class="${selected}" data-action="swing" data-swing="${value}" aria-label="Set swing ${label.toLowerCase()}" title="Swing ${label}" ${disabled || pending ? "disabled" : ""}>${this._buttonContent(this._swingIcon(highlightedIndex), pending)}</button>`;
  }

  _swingIcon(highlightedIndex) {
    const rays = Array.from({ length: 5 }, (_, index) => {
      const active = index === highlightedIndex ? "active" : "";
      return `<line class="swing-ray ${active}" x1="8" y1="8" x2="34" y2="8" transform="rotate(${index * 22.5} 8 8)" />`;
    }).join("");
    return `<svg class="swing-icon" viewBox="0 0 40 40" aria-hidden="true">${rays}</svg>`;
  }

  _transitionPanelHtml(state, pendingTransition) {
    const attributes = state.attributes;
    const minimum = Number(attributes.min_temp) || 16;
    const maximum = Number(attributes.max_temp) || 30;
    const minutes = this._transitionMinutes ?? 30;
    const target = this._transitionTarget ?? "off";
    const temperature = Number.isFinite(this._transitionTemperature)
      ? this._transitionTemperature
      : Math.round(Number(attributes.temperature)) || minimum;
    const goal = target === "temp" ? `${temperature}°` : target === "on" ? "On" : "Off";
    const quickOptions = [15, 30, 60, 120];
    return `
      <div class="transition-panel">
        <div class="transition-panel-title">⏱ Timed transition</div>
        <p class="transition-field-label">In</p>
        <div class="transition-chip-row">
          ${quickOptions.map((value) => `<button class="transition-chip ${minutes === value ? "selected" : ""}" data-action="transition-minutes" data-minutes="${value}">${this._formatMinutes(value)}</button>`).join("")}
        </div>
        <div class="transition-stepper">
          <button data-action="transition-minutes-step" data-step="-5" aria-label="Decrease delay">−</button>
          <span class="transition-stepper-value">${this._formatMinutes(minutes)}</span>
          <button data-action="transition-minutes-step" data-step="5" aria-label="Increase delay">+</button>
        </div>
        <p class="transition-field-label">Then</p>
        <div class="transition-segmented">
          <button class="${target === "off" ? "selected" : ""}" data-action="transition-target" data-target="off">Turn off</button>
          <button class="${target === "on" ? "selected" : ""}" data-action="transition-target" data-target="on">Turn on</button>
          <button class="${target === "temp" ? "selected" : ""}" data-action="transition-target" data-target="temp">Set temp</button>
        </div>
        ${target === "temp" ? `<div class="transition-stepper">
          <button data-action="transition-temperature-step" data-step="-1" aria-label="Decrease temperature">−</button>
          <span class="transition-stepper-value">${temperature} ${this._escape(attributes.temperature_unit ?? "°")}</span>
          <button data-action="transition-temperature-step" data-step="1" aria-label="Increase temperature">+</button>
        </div>` : ""}
        <div class="transition-panel-footer">
          ${pendingTransition ? `<button class="transition-text-button" data-action="transition-cancel">Cancel transition</button>` : `<button class="transition-text-button" data-action="transition-dismiss">Dismiss</button>`}
          <button class="transition-start-button" data-action="transition-start">${pendingTransition ? "Update" : "Start"} · ${goal} in ${this._formatMinutes(minutes)}</button>
        </div>
      </div>`;
  }

  _transitionCountdownLabel(pendingTransition) {
    const remainingSeconds = Math.max(
      0,
      Math.round((new Date(pendingTransition.fires_at).getTime() - Date.now()) / 1000),
    );
    const goal = pendingTransition.turn_off
      ? "Off"
      : pendingTransition.turn_on
        ? "On"
        : `${pendingTransition.temperature_celsius}°`;
    return `${goal} in ${this._formatCountdown(remainingSeconds)}`;
  }

  _formatCountdown(totalSeconds) {
    const pad = (value) => String(value).padStart(2, "0");
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`;
  }

  _formatMinutes(minutes) {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `${hours}h ${rest}m` : `${hours}h`;
  }

  _stopTransitionTicking() {
    if (this._transitionTickInterval) {
      clearInterval(this._transitionTickInterval);
      this._transitionTickInterval = undefined;
    }
  }

  async _handleAction(button, state) {
    const action = button.dataset.action;
    if (action === "more-info") {
      const event = new Event("hass-action", { bubbles: true, composed: true });
      event.detail = {
        config: {
          entity: this._config.entity,
          tap_action: { action: "more-info" },
        },
        action: "tap",
      };
      this.dispatchEvent(event);
      return;
    }
    if (action === "toggle-temperature-slider") {
      this._sliderOpen = !this._sliderOpen;
      this._sliderTemperature = Number(state.attributes.temperature);
      this._render();
      return;
    }
    if (action === "toggle-transition-panel") {
      this._transitionPanelOpen = !this._transitionPanelOpen;
      if (this._transitionPanelOpen) {
        const pending = this._hass.states[TRANSITIONS_SENSOR]?.attributes?.[this._config.entity];
        this._transitionTarget = pending
          ? pending.turn_off
            ? "off"
            : pending.turn_on
              ? "on"
              : "temp"
          : "off";
        this._transitionTemperature = pending?.temperature_celsius ?? Number(state.attributes.temperature);
        this._transitionMinutes = pending
          ? Math.max(5, Math.round((new Date(pending.fires_at).getTime() - Date.now()) / 60000 / 5) * 5)
          : 30;
      }
      this._render();
      return;
    }
    if (action === "transition-minutes") {
      this._transitionMinutes = Number(button.dataset.minutes);
      this._render();
      return;
    }
    if (action === "transition-minutes-step") {
      this._transitionMinutes = Math.min(360, Math.max(5, (this._transitionMinutes ?? 30) + Number(button.dataset.step)));
      this._render();
      return;
    }
    if (action === "transition-target") {
      this._transitionTarget = button.dataset.target;
      this._render();
      return;
    }
    if (action === "transition-temperature-step") {
      const minimum = Number(state.attributes.min_temp) || 16;
      const maximum = Number(state.attributes.max_temp) || 30;
      const current = Number.isFinite(this._transitionTemperature)
        ? this._transitionTemperature
        : Number(state.attributes.temperature) || minimum;
      this._transitionTemperature = Math.min(maximum, Math.max(minimum, current + Number(button.dataset.step)));
      this._render();
      return;
    }
    if (action === "transition-dismiss") {
      this._transitionPanelOpen = false;
      this._render();
      return;
    }
    if (action === "transition-start") {
      this._transitionPanelOpen = false;
      const data = { entity_id: this._config.entity, delay_seconds: (this._transitionMinutes ?? 30) * 60 };
      if (this._transitionTarget === "temp") {
        data.temperature = this._transitionTemperature;
      } else if (this._transitionTarget === "on") {
        data.turn_on = true;
      } else {
        data.turn_off = true;
      }
      this._render();
      try {
        await this._hass.callService("climate_flow", "schedule_transition", data);
      } catch {
        // Home Assistant surfaces the error toast; nothing further to do here.
      }
      return;
    }
    if (action === "transition-cancel") {
      this._transitionPanelOpen = false;
      this._render();
      try {
        await this._hass.callService("climate_flow", "cancel_transition", { entity_id: this._config.entity });
      } catch {
        // Home Assistant surfaces the error toast; nothing further to do here.
      }
      return;
    }
    const actionId = this._actionId(button);
    if (!this._startAction(actionId)) return;
    try {
      if (action === "power") {
        await this._hass.callService("climate", this._isOff(state) || this._isCleaning(state) ? "turn_on" : "turn_off", {
          entity_id: this._config.entity,
        });
        return;
      }
      if (action === "temperature") {
        const current = Number(state.attributes.temperature);
        if (!Number.isFinite(current)) return;
        await this._hass.callService("climate", "set_temperature", {
          entity_id: this._config.entity,
          temperature: current + Number(button.dataset.offset),
        });
        return;
      }
      const requestedSwingMode = button.dataset.swing;
      const swingMode = state.attributes.swing_modes?.find(
        (mode) => this._normalizeSwingMode(mode) === this._normalizeSwingMode(requestedSwingMode),
      ) ?? requestedSwingMode;
      await this._hass.callService("climate", "set_swing_mode", {
        entity_id: this._config.entity,
        swing_mode: swingMode,
      });
    } catch {
      // The Home Assistant frontend reports the action error; always clear feedback.
    } finally {
      this._finishAction(actionId);
    }
  }

  _actionId(button) {
    if (button.dataset.action === "power") return "power";
    return `${button.dataset.action}:${button.dataset.offset ?? button.dataset.swing}`;
  }

  async _asyncSetSliderTemperature(temperature, state) {
    const actionId = "temperature-slider";
    if (!Number.isFinite(temperature) || !this._startAction(actionId)) return;
    try {
      await this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        temperature,
      });
    } catch {
      // The Home Assistant frontend reports the action error; always clear feedback.
    } finally {
      this._sliderOpen = false;
      this._sliderTemperature = undefined;
      this._finishAction(actionId);
    }
  }

  _startAction(actionId) {
    this._pendingActions ??= new Set();
    if (this._pendingActions.has(actionId)) return false;
    this._pendingActions.add(actionId);
    this._render();
    return true;
  }

  _finishAction(actionId) {
    this._pendingActions.delete(actionId);
    this._render();
  }

  _isActionPending(actionId) {
    return this._pendingActions?.has(actionId) ?? false;
  }

  _buttonContent(content, pending) {
    return `<span class="button-label">${content}</span>${pending ? '<span class="work-indicator" aria-hidden="true"></span>' : ""}`;
  }

  _escape(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[character]);
  }

  _formatState(value) {
    return String(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  _normalizeSwingMode(value) {
    return String(value ?? "").trim().toLowerCase().replace(/[_-]+/g, " ");
  }

  _isEnabled(value) {
    return value === true || ["on", "true", "1"].includes(String(value).toLowerCase());
  }
}

customElements.define("climate-flow-ac-card", ClimateFlowAcCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "climate-flow-ac-card",
  name: "Climate Flow AC Card",
  description: "A compact climate control card with mapped swing directions.",
  preview: false,
  getEntitySuggestion: (_hass, entityId) => entityId.startsWith("climate.") ? {} : null,
});
