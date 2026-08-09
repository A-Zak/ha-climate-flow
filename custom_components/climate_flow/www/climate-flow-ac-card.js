class ClimateFlowAcCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity || !config.entity.startsWith("climate.")) {
      throw new Error("Set entity to a climate entity.");
    }
    if (config.off_states && !Array.isArray(config.off_states)) {
      throw new Error("off_states must be a list of climate states.");
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

  _render() {
    if (!this._config || !this._hass) return;

    const state = this._hass.states[this._config.entity];
    if (!state) {
      this.innerHTML = `<ha-card><div class="error">Entity not found: ${this._config.entity}</div></ha-card>`;
      return;
    }

    const attributes = state.attributes;
    const isOff = this._isOff(state);
    const temperature = Number(attributes.temperature);
    const step = Number(attributes.target_temp_step) || 1;
    const minimum = Number(attributes.min_temp);
    const maximum = Number(attributes.max_temp);
    const canDecrease = !Number.isFinite(temperature) || !Number.isFinite(minimum) || temperature > minimum;
    const canIncrease = !Number.isFinite(temperature) || !Number.isFinite(maximum) || temperature < maximum;
    const name = this._config.name ?? attributes.friendly_name ?? this._config.entity;
    const selectedSwing = attributes.swing_mode;
    const controlsDisabled = isOff ? "disabled" : "";

    this.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .header, .temperature, .swing { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .header { margin-bottom: 20px; font-size: 1.1em; font-weight: 500; }
        .temperature { justify-content: center; margin-bottom: 18px; }
        .temperature-value { min-width: 4.5em; text-align: center; font-size: 2em; font-weight: 400; }
        .swing { justify-content: center; }
        button { border: 0; border-radius: 50%; background: var(--secondary-background-color); color: var(--primary-text-color); cursor: pointer; font: inherit; min-width: 44px; min-height: 44px; padding: 8px; }
        button:hover:not(:disabled), button.selected { background: var(--primary-color); color: var(--text-primary-color); }
        button:disabled { cursor: default; opacity: 0.45; }
        .power { color: var(--state-climate-heat-color, var(--primary-color)); }
        .power.off { color: var(--disabled-text-color); }
        .error { padding: 16px; color: var(--error-color); }
      </style>
      <ha-card>
        <div class="header">
          <span>${this._escape(name)}</span>
          <button class="power ${isOff ? "off" : ""}" data-action="power" aria-label="${isOff ? "Turn on" : "Turn off"}" title="${isOff ? "Turn on" : "Turn off"}">⏻</button>
        </div>
        <div class="temperature">
          <button data-action="temperature" data-offset="-${step}" aria-label="Decrease temperature" ${controlsDisabled} ${canDecrease ? "" : "disabled"}>−</button>
          <span class="temperature-value">${Number.isFinite(temperature) ? `${temperature} ${this._escape(attributes.temperature_unit ?? "°")}` : "—"}</span>
          <button data-action="temperature" data-offset="${step}" aria-label="Increase temperature" ${controlsDisabled} ${canIncrease ? "" : "disabled"}>+</button>
        </div>
        <div class="swing" aria-label="Vertical swing direction">
          ${this._swingButton("fixed 1", "↑", "Top", selectedSwing, controlsDisabled)}
          ${this._swingButton("fixed 3", "↔", "Middle", selectedSwing, controlsDisabled)}
          ${this._swingButton("fixed 5", "↓", "Bottom", selectedSwing, controlsDisabled)}
        </div>
      </ha-card>`;

    this.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => this._handleAction(button, state));
    });
  }

  _swingButton(value, icon, label, selectedSwing, disabled) {
    const selected = value === selectedSwing ? "selected" : "";
    return `<button class="${selected}" data-action="swing" data-swing="${value}" aria-label="Set swing ${label.toLowerCase()}" title="Swing ${label}" ${disabled}>${icon}</button>`;
  }

  _handleAction(button, state) {
    const action = button.dataset.action;
    if (action === "power") {
      this._hass.callService("climate", this._isOff(state) ? "turn_on" : "turn_off", {
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
