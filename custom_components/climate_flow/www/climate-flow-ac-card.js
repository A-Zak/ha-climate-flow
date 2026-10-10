const TRANSITIONS_SENSOR = "sensor.pending_transitions";
const TEMPERATURE_DEBOUNCE_MS = 500;

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
    clearTimeout(this._debounceTimer);
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
    const effectiveTemperature = Number.isFinite(this._debouncedTemperature)
      ? this._debouncedTemperature
      : temperature;
    const canDecrease = !Number.isFinite(effectiveTemperature) || !Number.isFinite(minimum) || effectiveTemperature > minimum;
    const canIncrease = !Number.isFinite(effectiveTemperature) || !Number.isFinite(maximum) || effectiveTemperature < maximum;
    const canShowTemperaturePicker = Number.isFinite(temperature)
      && Number.isFinite(minimum)
      && Number.isFinite(maximum);
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
        ha-card { box-sizing: border-box; min-width: 0; padding: clamp(8px, 4vw, 16px); position: relative; }
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
        .transition-static-label { color: var(--primary-text-color); font-size: 0.85em; font-weight: 600; margin: 0 0 12px; }
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
        .temperature-section { position: static; }
        .temperature { display: grid; gap: 8px; grid-template-columns: 40px minmax(4.5em, auto) 40px; justify-content: center; margin: 0 auto 4px; max-width: 200px; width: 100%; }
        .temperature-value { min-width: 4.5em; text-align: center; font-size: 2em; font-weight: 400; }
        .temperature-trigger { background: transparent; border: 0; border-radius: 4px; min-height: 0; min-width: 0; padding: 0; }
        .temperature-trigger:active:not(:disabled) { background: var(--secondary-background-color); color: var(--primary-text-color); }
        .temperature-value-wrap { align-items: center; display: flex; gap: 6px; justify-content: center; min-width: 0; }
        .temperature-work-indicator { animation: rotate-work-indicator 0.8s linear infinite; border: 2px solid transparent; border-radius: 50%; border-right-color: var(--primary-color); border-top-color: var(--primary-color); box-shadow: 0 0 6px var(--primary-color); flex-shrink: 0; height: 14px; width: 14px; }
        .temperature-picker-row { background: var(--ha-card-background, var(--card-background-color)); border-radius: 12px; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4); box-sizing: border-box; height: 90%; left: 50%; padding: 10px; position: absolute; top: 50%; transform: translate(-50%, -50%); width: 80%; z-index: 2; }
        .temperature-picker-close { aspect-ratio: 1 / 1; background: var(--secondary-background-color); border: 2px solid var(--ha-card-background, var(--card-background-color)); border-radius: 50%; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35); color: var(--primary-text-color); cursor: pointer; font-size: 0.85em; line-height: 1; min-height: 30px; min-width: 30px; padding: 0; position: absolute; right: -10px; top: -10px; z-index: 3; }
        .temperature-picker-grid { display: grid; gap: 6px; grid-auto-rows: 1fr; height: 100%; width: 100%; }
        .temperature-picker-option { aspect-ratio: auto; font-size: 0.8em; font-weight: 600; height: 100%; min-height: 0; min-width: 0; padding: 0; width: 100%; }
        .current-temperature { color: var(--secondary-text-color); font-size: 0.9em; margin-bottom: 18px; text-align: center; }
        .swing { justify-content: center; }
        .swing-buttons { display: flex; gap: 12px; }
        button { align-items: center; aspect-ratio: 1 / 1; border: 3px solid transparent; border-radius: 50%; background: var(--secondary-background-color); box-sizing: border-box; color: var(--primary-text-color); cursor: pointer; display: flex; flex-shrink: 0; font: inherit; justify-content: center; min-width: 44px; min-height: 44px; padding: 8px; position: relative; }
        button:active:not(:disabled), button.selected { background: var(--primary-color); color: var(--text-primary-color); }
        button:disabled { cursor: default; opacity: 0.45; }
        .button-label { align-items: center; display: inline-flex; justify-content: center; }
        .work-indicator { animation: rotate-work-indicator 0.8s linear infinite; border: 3px solid transparent; border-radius: inherit; border-right-color: var(--primary-color); border-top-color: var(--primary-color); box-shadow: 0 0 8px var(--primary-color); inset: -3px; pointer-events: none; position: absolute; }
        @keyframes rotate-work-indicator { to { transform: rotate(360deg); } }
        .swing-icon { display: block; height: 28px; margin: auto; width: 28px; }
        .swing-ray { fill: none; opacity: 0.28; stroke: currentColor; stroke-linecap: round; stroke-width: 2.5; }
        .swing-ray.active { opacity: 1; stroke-width: 4; }
        .button-icon { display: block; fill: none; margin: auto; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.2; height: 22px; width: 22px; }
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
            <button class="timer ${pendingTransition ? "armed" : ""}" data-action="toggle-transition-panel" aria-label="${transitionLabel}" title="${transitionLabel}">${this._buttonContent(this._clockIcon(), false)}</button>
            <button class="power ${powerClass}" data-action="power" aria-label="${powerLabel}" title="${powerLabel}" ${isUnavailable || this._isActionPending(powerActionId) ? "disabled" : ""}>${this._buttonContent(this._powerIcon(), this._isActionPending(powerActionId))}</button>
          </div>
        </div>
        ${this._transitionPanelOpen ? this._transitionPanelHtml(state, pendingTransition) : ""}
        <div class="temperature-section">
          ${this._pickerOpen && canShowTemperaturePicker ? this._temperaturePickerHtml(minimum, maximum, step, effectiveTemperature) : ""}
          <div class="temperature">
            <button data-action="temperature" data-offset="-${step}" aria-label="Decrease temperature" ${controlsDisabled} ${canDecrease ? "" : "disabled"}>${this._buttonContent(this._minusIcon(), false)}</button>
            <div class="temperature-value-wrap">
              <button class="temperature-value temperature-trigger" data-action="toggle-temperature-picker" aria-label="Set target temperature" title="Set target temperature" ${controlsDisabled || !canShowTemperaturePicker ? "disabled" : ""}>${Number.isFinite(effectiveTemperature) ? `${effectiveTemperature} ${this._escape(attributes.temperature_unit ?? "°")}` : "—"}</button>
              ${this._isActionPending("temperature-debounce") ? '<span class="temperature-work-indicator" aria-label="Setting temperature"></span>' : ""}
            </div>
            <button data-action="temperature" data-offset="${step}" aria-label="Increase temperature" ${controlsDisabled} ${canIncrease ? "" : "disabled"}>${this._buttonContent(this._plusIcon(), false)}</button>
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
  }

  _temperaturePickerHtml(minimum, maximum, step, selected) {
    const pending = this._isActionPending("temperature-picker");
    const options = this._temperatureOptions(minimum, maximum, step);
    const columns = this._temperaturePickerColumns(options.length);
    const remainder = options.length % columns;
    const lastRowStart = options.length - remainder;
    const centerOffset = remainder > 0 ? Math.floor((columns - remainder) / 2) : 0;
    return `
      <div class="temperature-picker-row">
        <button class="temperature-picker-close" data-action="temperature-picker-close" aria-label="Close temperature picker" title="Close">✕</button>
        <div class="temperature-picker-grid" style="grid-template-columns: repeat(${columns}, 1fr);">
          ${options.map((value, index) => {
            const inLastRow = remainder > 0 && index >= lastRowStart;
            const column = inLastRow ? centerOffset + (index - lastRowStart) + 1 : null;
            const columnStyle = column ? ` style="grid-column: ${column} / span 1;"` : "";
            return `<button class="temperature-picker-option ${value === selected ? "selected" : ""}" data-action="temperature-picker-select" data-temperature="${value}" aria-label="Set temperature to ${value}" ${pending ? "disabled" : ""}${columnStyle}>${this._buttonContent(String(value), pending && value === this._pendingPickerValue)}</button>`;
          }).join("")}
        </div>
      </div>`;
  }

  _temperaturePickerColumns(count) {
    if (count <= 1) return 1;
    // The picker area tends to be noticeably wider than it is tall, so bias
    // toward more columns than a plain square grid would pick.
    return Math.max(1, Math.round(Math.sqrt(count * 1.4)));
  }

  _temperatureOptions(minimum, maximum, step) {
    const options = [];
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || !Number.isFinite(step) || step <= 0) {
      return options;
    }
    for (let value = minimum; value <= maximum + 1e-6; value += step) {
      options.push(Math.round(value * 100) / 100);
    }
    return options;
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

  _iconSvg(inner) {
    return `<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true">${inner}</svg>`;
  }

  _minusIcon() {
    return this._iconSvg('<line x1="5" y1="12" x2="19" y2="12" />');
  }

  _plusIcon() {
    return this._iconSvg('<line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />');
  }

  _clockIcon() {
    return this._iconSvg('<circle cx="12" cy="12" r="8.5" /><line x1="12" y1="12" x2="12" y2="7.5" /><line x1="12" y1="12" x2="15.5" y2="14" />');
  }

  _powerIcon() {
    return this._iconSvg('<path d="M12 4v7" /><path d="M7.5 7a7.5 7.5 0 1 0 9 0" />');
  }

  _transitionPanelHtml(state, pendingTransition) {
    const attributes = state.attributes;
    const minimum = Number(attributes.min_temp) || 16;
    const maximum = Number(attributes.max_temp) || 30;
    const minutes = this._transitionMinutes ?? 30;
    const currentlyOff = this._isOff(state) || this._isCleaning(state);
    const target = currentlyOff ? "temp" : (this._transitionTarget ?? "off");
    const temperature = Number.isFinite(this._transitionTemperature)
      ? this._transitionTemperature
      : Math.round(Number(attributes.temperature)) || minimum;
    const goal = target === "temp" ? (currentlyOff ? `On, ${temperature}°` : `${temperature}°`) : "Off";
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
        ${currentlyOff
          ? `<p class="transition-static-label">Turn on and set temperature</p>`
          : `<div class="transition-segmented">
              <button class="${target === "off" ? "selected" : ""}" data-action="transition-target" data-target="off">Turn off</button>
              <button class="${target === "temp" ? "selected" : ""}" data-action="transition-target" data-target="temp">Set temp</button>
            </div>`}
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
    const hasTemperature = pendingTransition.temperature_celsius != null;
    const goal = pendingTransition.turn_off
      ? "Off"
      : hasTemperature
        ? (pendingTransition.turn_on ? `On, ${pendingTransition.temperature_celsius}°` : `${pendingTransition.temperature_celsius}°`)
        : "On";
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
    if (action === "toggle-temperature-picker") {
      this._pickerOpen = !this._pickerOpen;
      this._render();
      return;
    }
    if (action === "temperature-picker-select") {
      await this._asyncSetPickerTemperature(Number(button.dataset.temperature), state);
      return;
    }
    if (action === "temperature-picker-close") {
      this._pickerOpen = false;
      this._render();
      return;
    }
    if (action === "temperature") {
      const base = Number.isFinite(this._debouncedTemperature)
        ? this._debouncedTemperature
        : Number(state.attributes.temperature);
      if (!Number.isFinite(base)) return;
      const minimum = Number(state.attributes.min_temp);
      const maximum = Number(state.attributes.max_temp);
      let next = Math.round((base + Number(button.dataset.offset)) * 1000) / 1000;
      if (Number.isFinite(minimum)) next = Math.max(minimum, next);
      if (Number.isFinite(maximum)) next = Math.min(maximum, next);
      this._debouncedTemperature = next;
      this._render();
      this._scheduleDebouncedTemperature();
      return;
    }
    if (action === "toggle-transition-panel") {
      this._transitionPanelOpen = !this._transitionPanelOpen;
      if (this._transitionPanelOpen) {
        const pending = this._hass.states[TRANSITIONS_SENSOR]?.attributes?.[this._config.entity];
        const currentlyOff = this._isOff(state) || this._isCleaning(state);
        this._transitionTarget = currentlyOff ? "temp" : pending?.turn_off ? "off" : "temp";
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
      const currentlyOff = this._isOff(state) || this._isCleaning(state);
      const data = { entity_id: this._config.entity, delay_seconds: (this._transitionMinutes ?? 30) * 60 };
      if (this._transitionTarget === "temp") {
        data.temperature = this._transitionTemperature;
        if (currentlyOff) data.turn_on = true;
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
    if (action === "power") {
      const pending = this._hass.states[TRANSITIONS_SENSOR]?.attributes?.[this._config.entity];
      if (
        pending &&
        !window.confirm("Turning this AC on or off will cancel its scheduled transition. Continue?")
      ) {
        return;
      }
      const actionId = this._actionId(button);
      if (!this._startAction(actionId)) return;
      try {
        if (pending) {
          await this._hass.callService("climate_flow", "cancel_transition", {
            entity_id: this._config.entity,
          });
        }
        await this._hass.callService("climate", this._isOff(state) || this._isCleaning(state) ? "turn_on" : "turn_off", {
          entity_id: this._config.entity,
        });
      } catch {
        // The Home Assistant frontend reports the action error; always clear feedback.
      } finally {
        this._finishAction(actionId);
      }
      return;
    }
    const actionId = this._actionId(button);
    if (!this._startAction(actionId)) return;
    try {
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

  _scheduleDebouncedTemperature() {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      this._commitDebouncedTemperature();
    }, TEMPERATURE_DEBOUNCE_MS);
  }

  async _commitDebouncedTemperature() {
    const temperature = this._debouncedTemperature;
    if (!Number.isFinite(temperature)) return;
    const actionId = "temperature-debounce";
    if (!this._startAction(actionId)) return;
    try {
      await this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        temperature,
      });
    } catch {
      // The Home Assistant frontend reports the action error; always clear feedback.
    } finally {
      this._debouncedTemperature = undefined;
      this._finishAction(actionId);
    }
  }

  async _asyncSetPickerTemperature(temperature, state) {
    if (!Number.isFinite(temperature)) return;
    const actionId = "temperature-picker";
    this._pendingPickerValue = temperature;
    if (!this._startAction(actionId)) {
      this._pendingPickerValue = undefined;
      return;
    }
    try {
      await this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        temperature,
      });
    } catch {
      // The Home Assistant frontend reports the action error; always clear feedback.
    } finally {
      this._pickerOpen = false;
      this._pendingPickerValue = undefined;
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
