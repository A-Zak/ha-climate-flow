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

  _isOff(state) {
    const offStates = this._config.off_states ?? ["off", "cleaning"];
    return offStates.includes(state.state);
  }

  _isCleaning(state) {
    const cleaningStates = this._config.cleaning_states ?? ["cleaning"];
    return cleaningStates.includes(state.state) || cleaningStates.includes(state.attributes.hvac_action);
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
    const name = this._config.name ?? attributes.friendly_name ?? this._config.entity;
    const mode = attributes.hvac_action ?? state.state;
    const selectedSwing = attributes.swing_mode;
    const mappedSwingModes = ["fixed 1", "fixed 3", "fixed 5"];
    const otherSwingMode = selectedSwing && !mappedSwingModes.includes(selectedSwing) ? selectedSwing : undefined;
    const controlsDisabled = isOff || isUnavailable ? "disabled" : "";
    const powerClass = isCleaning ? "power-cleaning" : isOff || isUnavailable ? "power-off" : "power-on";
    const powerLabel = isCleaning ? "Cleaning" : isUnavailable ? "Unavailable" : isOff ? "Turn on" : "Turn off";

    this.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .header, .temperature, .swing { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .header { margin-bottom: 20px; font-size: 1.1em; font-weight: 500; }
        .header-left { align-items: center; display: flex; gap: 8px; }
        .title { display: grid; gap: 2px; }
        .more-info { font-size: 1.3em; line-height: 1; min-height: 36px; min-width: 36px; padding: 0; }
        .mode-state, .swing-state { color: var(--secondary-text-color); font-size: 0.8em; font-weight: 400; }
        .temperature { justify-content: center; margin-bottom: 4px; }
        .temperature-value { min-width: 4.5em; text-align: center; font-size: 2em; font-weight: 400; }
        .current-temperature { color: var(--secondary-text-color); font-size: 0.9em; margin-bottom: 18px; text-align: center; }
        .swing { justify-content: center; }
        .swing-buttons { display: flex; gap: 12px; }
        button { border: 3px solid transparent; border-radius: 50%; background: var(--secondary-background-color); color: var(--primary-text-color); cursor: pointer; font: inherit; min-width: 44px; min-height: 44px; padding: 8px; }
        button:hover:not(:disabled), button.selected { background: var(--primary-color); color: var(--text-primary-color); }
        button:disabled { cursor: default; opacity: 0.45; }
        .swing-icon { display: block; height: 28px; margin: auto; width: 28px; }
        .swing-ray { fill: none; opacity: 0.28; stroke: currentColor; stroke-linecap: round; stroke-width: 2.5; }
        .swing-ray.active { opacity: 1; stroke-width: 4; }
        .power-on { color: var(--success-color, #4caf50); }
        .power-off { color: var(--error-color, #f44336); }
        .power-cleaning { border-color: var(--info-color, #2196f3); border-style: dashed; color: var(--info-color, #2196f3); }
        .error { padding: 16px; color: var(--error-color); }
      </style>
      <ha-card>
        <div class="header">
          <div class="header-left">
            <button class="more-info" data-action="more-info" aria-label="Open climate controls" title="Open climate controls">⋮</button>
            <div class="title">
              <span>${this._escape(name)}</span>
              <span class="mode-state">${this._escape(this._formatState(mode))}</span>
            </div>
          </div>
          <button class="power ${powerClass}" data-action="power" aria-label="${powerLabel}" title="${powerLabel}" ${isUnavailable ? "disabled" : ""}>⏻</button>
        </div>
        <div class="temperature">
          <button data-action="temperature" data-offset="-${step}" aria-label="Decrease temperature" ${controlsDisabled} ${canDecrease ? "" : "disabled"}>−</button>
          <span class="temperature-value">${Number.isFinite(temperature) ? `${temperature} ${this._escape(attributes.temperature_unit ?? "°")}` : "—"}</span>
          <button data-action="temperature" data-offset="${step}" aria-label="Increase temperature" ${controlsDisabled} ${canIncrease ? "" : "disabled"}>+</button>
        </div>
        ${Number.isFinite(currentTemperature) ? `<div class="current-temperature">Current: ${currentTemperature} ${this._escape(attributes.temperature_unit ?? "°")}</div>` : ""}
        <div class="swing" aria-label="Vertical swing direction">
          <div class="swing-buttons">
            ${this._swingButton("fixed 1", 0, "Top", selectedSwing, controlsDisabled)}
            ${this._swingButton("fixed 3", 2, "Middle", selectedSwing, controlsDisabled)}
            ${this._swingButton("fixed 5", 4, "Bottom", selectedSwing, controlsDisabled)}
          </div>
          ${otherSwingMode ? `<span class="swing-state">${this._escape(this._formatState(otherSwingMode))}</span>` : ""}
        </div>
      </ha-card>`;

    this.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => this._handleAction(button, state));
    });
  }

  _swingButton(value, highlightedIndex, label, selectedSwing, disabled) {
    const selected = value === selectedSwing ? "selected" : "";
    return `<button class="${selected}" data-action="swing" data-swing="${value}" aria-label="Set swing ${label.toLowerCase()}" title="Swing ${label}" ${disabled}>${this._swingIcon(highlightedIndex)}</button>`;
  }

  _swingIcon(highlightedIndex) {
    const rays = Array.from({ length: 5 }, (_, index) => {
      const active = index === highlightedIndex ? "active" : "";
      return `<line class="swing-ray ${active}" x1="8" y1="8" x2="34" y2="8" transform="rotate(${index * 22.5} 8 8)" />`;
    }).join("");
    return `<svg class="swing-icon" viewBox="0 0 40 40" aria-hidden="true">${rays}</svg>`;
  }

  _handleAction(button, state) {
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
    if (action === "power") {
      this._hass.callService("climate", this._isOff(state) || this._isCleaning(state) ? "turn_on" : "turn_off", {
        entity_id: this._config.entity,
      });
      return;
    }
    if (action === "temperature") {
      const current = Number(state.attributes.temperature);
      if (!Number.isFinite(current)) return;
      this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        temperature: current + Number(button.dataset.offset),
      });
      return;
    }
    this._hass.callService("climate", "set_swing_mode", {
      entity_id: this._config.entity,
      swing_mode: button.dataset.swing,
    });
  }

  _escape(value) {
    return String(value).replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[character]);
  }

  _formatState(value) {
    return String(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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
