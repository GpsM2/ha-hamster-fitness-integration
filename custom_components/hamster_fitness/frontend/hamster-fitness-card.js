/**
 * Hamster Fitness Card
 *
 * Bundled with the Hamster Fitness integration, auto-registered as a
 * Lovelace resource (see frontend/__init__.py) - no HACS frontend install
 * needed. Shows one hamster's health score and live speed as two matching
 * ring gauges, plus distances/climate/status below.
 *
 * Config:
 *   type: custom:hamster-fitness-card
 *   entity: sensor.hamster_taco_health_score   # required - the hamster's Health Score sensor
 *   title: Taco                                 # optional - defaults to the hamster slug, capitalized
 *   max_speed: 5                                # optional - km/h, scale of the speed ring (default 5)
 *
 * The other entities (daily_distance, night_distance, lifetime_distance,
 * current_speed, max_speed_tonight, humidity, warning, door, weight,
 * departure_date) are found via the entity/device registry: same
 * device_id as `entity`, matched by translation_key (see siblingEntityId()
 * in hamster-fitness-shared.js). translation_key is a fixed English
 * string set in Python and never changes, unlike entity_id - which Home
 * Assistant generates once from the *translated* name active when the
 * entity was first created, so it can end up in German, French, etc.
 * instead of English. If registry data isn't available for some reason,
 * this falls back to swapping `entity`'s `_health_score` suffix, which
 * only works when entity_id happens to be English.
 *
 * The entity_id itself only needs to END in "_health_score" - it does NOT
 * have to start with "hamster_". New hamsters get that prefix (see
 * hamster_device_info()), but entities created before that naming change
 * keep their original entity_id (e.g. sensor.taco_health_score) unless
 * manually renamed - Home Assistant never renames entity_ids on its own.
 * The card's title prefers the device's own name (also never translated)
 * over parsing the entity_id.
 */

import {
  HAMSTER_PREFIX,
  deviceDisplayName,
  siblingEntityId,
} from "./hamster-fitness-shared.js";

const WARNING_SCORE_THRESHOLD = 50;
const GOOD_SCORE_THRESHOLD = 75;
const DEFAULT_MAX_SPEED = 5;
const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

const RING_COLOR_NEUTRAL = "#00b8a9";

// Running hamster with a headband - same illustration family as the
// Day & Night card's dumbbell logo (see hamster-day-night-card.js and
// design/hamster-headband-logo.svg), just for visual consistency between
// the two cards' headers.
const LOGO_HEADBAND_SVG = `
<svg viewBox="0 0 48 48" width="28" height="28" aria-hidden="true">
  <ellipse cx="24" cy="30" rx="14" ry="11" fill="#C89666"/>
  <ellipse cx="24" cy="30" rx="14" ry="11" fill="none" stroke="#8B5A2B" stroke-width="1"/>
  <ellipse cx="15" cy="34" rx="4.2" ry="3" fill="#C89666" stroke="#8B5A2B" stroke-width="1"/>
  <ellipse cx="33" cy="34" rx="4.2" ry="3" fill="#C89666" stroke="#8B5A2B" stroke-width="1"/>
  <circle cx="24" cy="17" r="9.5" fill="#D9A876"/>
  <circle cx="24" cy="17" r="9.5" fill="none" stroke="#8B5A2B" stroke-width="1"/>
  <path d="M15.5 12.5 A9.5 9.5 0 0 1 32.5 12.5 L31 9.5 A11 11 0 0 0 17 9.5 Z" fill="#e45c5c"/>
  <circle cx="17" cy="10" r="2.6" fill="#C89666" stroke="#8B5A2B" stroke-width="1"/>
  <circle cx="31" cy="10" r="2.6" fill="#C89666" stroke="#8B5A2B" stroke-width="1"/>
  <circle cx="20" cy="16" r="1.4" fill="#3a2a1a"/>
  <circle cx="28" cy="16" r="1.4" fill="#3a2a1a"/>
  <ellipse cx="24" cy="20" rx="2.2" ry="1.6" fill="#f4d9c6"/>
  <circle cx="24" cy="19.3" r="0.7" fill="#5c4030"/>
</svg>
`;

class HamsterFitnessCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error(
        "hamster-fitness-card: 'entity' fehlt - bitte den Health-Score-Sensor eines Hamsters auswählen (endet auf _health_score)."
      );
    }
    const match = config.entity.match(ENTITY_PATTERN);
    if (!match) {
      throw new Error(
        "hamster-fitness-card: 'entity' muss der Health-Score-Sensor eines Hamsters sein (Entity-ID endet auf _health_score)."
      );
    }
    this._config = config;
    this._hamster = match[1].replace(HAMSTER_PREFIX, "");
    this._maxSpeed = Number(config.max_speed) > 0 ? Number(config.max_speed) : DEFAULT_MAX_SPEED;

    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="hfc-root"></div>
        </ha-card>
        <style>${HamsterFitnessCard.styles}</style>
      `;
      this.content = this.querySelector(".hfc-root");
      // Event delegation: every clickable element carries a data-entity
      // attribute (see _ring()/_render()) rather than one listener each,
      // since the whole subtree is replaced on every _render().
      const openMoreInfo = (target) => {
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: target.dataset.entity },
            bubbles: true,
            composed: true,
          })
        );
      };
      this.content.addEventListener("click", (ev) => {
        const target = ev.target.closest("[data-entity]");
        if (target) openMoreInfo(target);
      });
      this.content.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        const target = ev.target.closest("[data-entity]");
        if (!target) return;
        ev.preventDefault();
        openMoreInfo(target);
      });
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("hamster-fitness-card-editor");
  }

  static getStubConfig(hass, entities) {
    const match = (entities || []).find((id) => ENTITY_PATTERN.test(id));
    return { entity: match || "sensor.hamster_taco_health_score" };
  }

  _entityId(key) {
    return (
      siblingEntityId(this._hass, this._config.entity, key) ||
      this._config.entity.replace(HEALTH_SCORE_SUFFIX, `_${key}`)
    );
  }

  _entity(key) {
    if (!this._hass) return undefined;
    return this._hass.states[this._entityId(key)];
  }

  _fmt(value, decimals, unit) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) {
      return "–";
    }
    const num = Number(value).toFixed(decimals).replace(".", ",");
    return unit ? `${num} ${unit}` : num;
  }

  _breakdownItem(icon, label, penalty) {
    const num = Number(penalty);
    const valid = !Number.isNaN(num);
    const active = valid && num > 0.05;
    const display = valid ? `-${this._fmt(num, 0, "")}` : "–";
    return `
      <span class="hfc-breakdown-item${active ? " hfc-breakdown-active" : ""}">
        <span class="hfc-breakdown-icon">${icon}</span>
        <span class="hfc-breakdown-text">${label} <strong>${display}</strong></span>
      </span>
    `;
  }

  _scoreColor(score) {
    if (score === null) return "var(--secondary-text-color)";
    if (score < WARNING_SCORE_THRESHOLD) return "#e45c5c";
    if (score < GOOD_SCORE_THRESHOLD) return "#f0a63c";
    return "#4caf50";
  }

  _ring({ value, max, color, decimals, unit, label, entityId }) {
    const circumference = 2 * Math.PI * 42;
    const valid = value !== undefined && value !== null && !Number.isNaN(Number(value));
    const pct = valid ? Math.min(Math.max(Number(value), 0), max) / max : 0;
    const offset = circumference * (1 - pct);
    const displayValue = valid ? this._fmt(value, decimals, "") : "–";
    const clickable = entityId ? `data-entity="${entityId}" tabindex="0" role="button"` : "";

    return `
      <div class="hfc-ring${entityId ? " hfc-clickable" : ""}" ${clickable}>
        <svg viewBox="0 0 100 100">
          <circle class="hfc-ring-bg" cx="50" cy="50" r="42"></circle>
          <circle
            class="hfc-ring-fg"
            cx="50" cy="50" r="42"
            stroke="${valid ? color : "var(--disabled-color, #888)"}"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${offset}"
          ></circle>
        </svg>
        <div class="hfc-ring-label">
          <span class="hfc-ring-value" style="color:${valid ? color : "var(--secondary-text-color)"}">${displayValue}</span>
          <span class="hfc-ring-unit">${unit}</span>
        </div>
        <div class="hfc-ring-caption">${label}</div>
      </div>
    `;
  }

  _render() {
    if (!this._hass || !this.content || !this._config) return;

    const healthScore = this._entity("health_score");
    const dailyDistance = this._entity("daily_distance");
    const nightDistance = this._entity("night_distance");
    const lifetimeDistance = this._entity("lifetime_distance");
    const currentSpeed = this._entity("current_speed");
    const maxSpeedTonight = this._entity("max_speed_tonight");
    const humidity = this._entity("humidity");
    const warning = this._entity("warning");
    const door = this._entity("door");
    const weight = this._entity("weight");
    const departureDate = this._entity("departure_date");

    if (!healthScore) {
      this.content.innerHTML = `
        <div class="hfc-error">
          Entity "<strong>${this._config.entity}</strong>" nicht gefunden.
          Prüfe die Karten-Konfiguration.
        </div>
      `;
      return;
    }

    const score = Number(healthScore.state);
    const scoreValid = !Number.isNaN(score);
    const scoreColor = this._scoreColor(scoreValid ? score : null);
    const temperature = healthScore.attributes.temperature;
    const title =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._capitalize(this._hamster);
    const isDeparted = departureDate && departureDate.state && departureDate.state !== "unknown";
    const warningOn = warning && warning.state === "on";
    const doorOpen = door && door.state === "on";

    const healthRing = this._ring({
      value: scoreValid ? score : null,
      max: 100,
      color: scoreColor,
      decimals: 0,
      unit: "%",
      label: "Health Score",
      entityId: this._entityId("health_score"),
    });

    const speedRing = this._ring({
      value: currentSpeed ? currentSpeed.state : null,
      max: this._maxSpeed,
      color: RING_COLOR_NEUTRAL,
      decimals: 1,
      unit: "km/h",
      label: "Geschwindigkeit",
      entityId: currentSpeed ? this._entityId("current_speed") : null,
    });

    this.content.innerHTML = `
      <div class="hfc-header">
        <span class="hfc-title">${LOGO_HEADBAND_SVG} ${title}</span>
        ${isDeparted ? '<span class="hfc-badge hfc-badge-muted">Ausgezogen</span>' : ""}
      </div>

      ${
        warningOn
          ? `<div class="hfc-warning">⚠️ ${warning.attributes.warning_reason || "Achtung"}</div>`
          : ""
      }

      <div class="hfc-rings">
        ${healthRing}
        ${speedRing}
      </div>

      <div class="hfc-breakdown hfc-clickable" data-entity="${this._entityId("health_score")}" tabindex="0" role="button">
        ${this._breakdownItem("🏃", "Bewegung", healthScore.attributes.distance_penalty)}
        ${this._breakdownItem("🌡️", "Temperatur", healthScore.attributes.temperature_penalty)}
        ${this._breakdownItem("🧹", "Pflege", healthScore.attributes.care_penalty)}
      </div>

      <div class="hfc-stats">
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("daily_distance")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Heute</span>
          <span class="hfc-stat-value">${this._fmt(dailyDistance && dailyDistance.state, 2, "km")}</span>
        </div>
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("night_distance")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Heute Nacht</span>
          <span class="hfc-stat-value">${this._fmt(nightDistance && nightDistance.state, 2, "km")}</span>
        </div>
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("lifetime_distance")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Insgesamt</span>
          <span class="hfc-stat-value">${this._fmt(lifetimeDistance && lifetimeDistance.state, 1, "km")}</span>
        </div>
        ${
          maxSpeedTonight
            ? `<div class="hfc-stat hfc-clickable" data-entity="${this._entityId("max_speed_tonight")}" tabindex="0" role="button">
                 <span class="hfc-stat-label">Max. heute Nacht</span>
                 <span class="hfc-stat-value">${this._fmt(maxSpeedTonight.state, 1, "km/h")}</span>
               </div>`
            : ""
        }
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("health_score")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Temperatur</span>
          <span class="hfc-stat-value">${this._fmt(temperature, 1, "°C")}</span>
        </div>
        ${
          humidity
            ? `<div class="hfc-stat hfc-clickable" data-entity="${this._entityId("humidity")}" tabindex="0" role="button">
                 <span class="hfc-stat-label">Luftfeuchtigkeit</span>
                 <span class="hfc-stat-value">${this._fmt(humidity.state, 0, "%")}</span>
               </div>`
            : ""
        }
        ${
          weight && weight.state && weight.state !== "unknown"
            ? `<div class="hfc-stat hfc-clickable" data-entity="${this._entityId("weight")}" tabindex="0" role="button">
                 <span class="hfc-stat-label">Gewicht</span>
                 <span class="hfc-stat-value">${this._fmt(weight.state, 0, "g")}</span>
               </div>`
            : ""
        }
      </div>

      ${
        door
          ? `<div class="hfc-footer hfc-clickable" data-entity="${this._entityId("door")}" tabindex="0" role="button">
               <span class="hfc-door ${doorOpen ? "hfc-door-open" : "hfc-door-closed"}">
                 ${doorOpen ? "🚪 Käfig offen" : "🚪 Käfig geschlossen"}
               </span>
             </div>`
          : ""
      }
    `;
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
}

HamsterFitnessCard.styles = `
  ha-card {
    padding: 16px;
  }
  .hfc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .hfc-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 1.2em;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .hfc-title svg {
    flex-shrink: 0;
  }
  .hfc-badge {
    font-size: 0.75em;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--disabled-color, #888);
    color: var(--text-primary-color, #fff);
  }
  .hfc-warning {
    background: rgba(228, 92, 92, 0.12);
    color: #e45c5c;
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 12px;
    font-size: 0.9em;
  }
  .hfc-rings {
    display: flex;
    align-items: flex-start;
    justify-content: space-evenly;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }
  .hfc-ring {
    position: relative;
    width: 110px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .hfc-ring svg {
    width: 100px;
    height: 100px;
    transform: rotate(-90deg);
  }
  .hfc-ring-bg {
    fill: none;
    stroke: var(--divider-color, #444);
    stroke-width: 8;
    opacity: 0.3;
  }
  .hfc-ring-fg {
    fill: none;
    stroke-width: 8;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.4s ease;
  }
  .hfc-ring-label {
    position: absolute;
    top: 0;
    width: 100px;
    height: 100px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .hfc-ring-value {
    font-size: 1.4em;
    font-weight: 700;
    line-height: 1;
  }
  .hfc-ring-unit {
    font-size: 0.7em;
    color: var(--secondary-text-color);
  }
  .hfc-ring-caption {
    margin-top: 4px;
    font-size: 0.8em;
    color: var(--secondary-text-color);
    text-align: center;
  }
  .hfc-breakdown {
    display: flex;
    justify-content: space-evenly;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 14px;
  }
  .hfc-breakdown-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.8em;
    color: var(--secondary-text-color);
  }
  .hfc-breakdown-icon {
    font-size: 1em;
  }
  .hfc-breakdown-item strong {
    color: var(--primary-text-color);
  }
  .hfc-breakdown-active strong {
    color: #e45c5c;
  }
  .hfc-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
    gap: 10px;
  }
  .hfc-stat {
    display: flex;
    flex-direction: column;
  }
  .hfc-stat-label {
    font-size: 0.75em;
    color: var(--secondary-text-color);
  }
  .hfc-stat-value {
    font-size: 1em;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .hfc-footer {
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px solid var(--divider-color, #444);
  }
  .hfc-door {
    font-size: 0.9em;
  }
  .hfc-door-open {
    color: #e45c5c;
  }
  .hfc-door-closed {
    color: #4caf50;
  }
  .hfc-error {
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .hfc-clickable {
    cursor: pointer;
    border-radius: 8px;
    transition: background-color 0.15s ease;
  }
  .hfc-clickable:hover,
  .hfc-clickable:focus-visible {
    background-color: var(--secondary-background-color, rgba(127, 127, 127, 0.15));
    outline: none;
  }
  .hfc-stat.hfc-clickable {
    padding: 4px 6px;
    margin: -4px -6px;
  }
  .hfc-footer.hfc-clickable {
    padding: 4px 8px;
    margin: 4px -8px -4px;
  }

  /* Mobile: schmalere Karten (typ. Handy-Dashboard) - Ringe und Schrift
     etwas verkleinern, damit beide Ringe nebeneinander passen, statt
     unschön umzubrechen. */
  @media (max-width: 380px) {
    ha-card {
      padding: 12px;
    }
    .hfc-rings {
      gap: 4px;
    }
    .hfc-ring {
      width: 92px;
    }
    .hfc-ring svg {
      width: 84px;
      height: 84px;
    }
    .hfc-ring-label {
      width: 84px;
      height: 84px;
    }
    .hfc-ring-value {
      font-size: 1.15em;
    }
    .hfc-stats {
      grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
      gap: 6px;
    }
  }
`;

customElements.define("hamster-fitness-card", HamsterFitnessCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-fitness-card",
  name: "Hamster Fitness: Health Score",
  description:
    "Zeigt Health Score und Live-Geschwindigkeit als Ringe, plus Distanzen, Klima und Status eines Hamsters aus der Hamster-Fitness-Integration.",
});

/**
 * Visual editor ("Configure card" dialog), backed by HA's own <ha-form>
 * so it looks/behaves exactly like the built-in cards' editors.
 */
const EDITOR_SCHEMA = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: { integration: "hamster_fitness", domain: "sensor" } } },
  },
  { name: "title", selector: { text: {} } },
  {
    name: "max_speed",
    selector: { number: { min: 1, max: 50, step: 0.5, mode: "box", unit_of_measurement: "km/h" } },
  },
];

const EDITOR_LABELS = {
  entity: "Health-Score-Sensor des Hamsters",
  title: "Titel (optional)",
  max_speed: "Skala des Geschwindigkeits-Rings (optional, km/h)",
};

class HamsterFitnessCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._renderForm();
  }

  set hass(hass) {
    this._hass = hass;
    this._renderForm();
  }

  _renderForm() {
    if (!this._hass || !this._config) return;

    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => EDITOR_LABELS[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        this._config = ev.detail.value;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }

    this._form.hass = this._hass;
    this._form.schema = EDITOR_SCHEMA;
    this._form.data = this._config;
  }
}

customElements.define("hamster-fitness-card-editor", HamsterFitnessCardEditor);

/**
 * Hamster Fitness Ranking Card
 *
 * Compares all hamster_fitness hamsters found in this Home Assistant by
 * lifetime distance - no config needed, entities are auto-discovered via
 * the entity registry (platform "hamster_fitness", translation_key
 * "lifetime_distance" - see siblingEntityId() above the main card class),
 * so this works regardless of what language entity_ids ended up in.
 * LIFETIME_DISTANCE_PATTERN is only used afterwards, as a fallback for
 * deriving a display name if the device registry lookup fails. Since a
 * departed hamster's lifetime_distance stays frozen (see coordinator.py),
 * retired hamsters remain part of the ranking automatically.
 *
 * Config:
 *   type: custom:hamster-fitness-ranking-card
 *   title: Hamster-Ranking   # optional
 */

const LIFETIME_DISTANCE_PATTERN = /^sensor\.(.+)_lifetime_distance$/;

class HamsterFitnessRankingCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="hfc-root"></div>
        </ha-card>
        <style>${HamsterFitnessCard.styles}</style>
      `;
      this.content = this.querySelector(".hfc-root");
      const openMoreInfo = (target) => {
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: target.dataset.entity },
            bubbles: true,
            composed: true,
          })
        );
      };
      this.content.addEventListener("click", (ev) => {
        const target = ev.target.closest("[data-entity]");
        if (target) openMoreInfo(target);
      });
      this.content.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        const target = ev.target.closest("[data-entity]");
        if (!target) return;
        ev.preventDefault();
        openMoreInfo(target);
      });
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("hamster-fitness-ranking-card-editor");
  }

  static getStubConfig() {
    return { title: "Hamster-Ranking" };
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  _render() {
    if (!this._hass || !this.content) return;

    const entities = this._hass.entities || {};
    const rows = Object.entries(entities)
      .filter(
        ([, entry]) =>
          entry.platform === "hamster_fitness" &&
          entry.translation_key === "lifetime_distance"
      )
      .map(([id]) => {
        const state = this._hass.states[id];
        const distance = state ? Number(state.state) : NaN;
        const departureId = siblingEntityId(this._hass, id, "departure_date");
        const departure = departureId && this._hass.states[departureId];
        const isDeparted = departure && departure.state && departure.state !== "unknown";
        const match = id.match(LIFETIME_DISTANCE_PATTERN);
        const slug = match ? match[1].replace(HAMSTER_PREFIX, "") : id;
        return {
          entityId: id,
          name: deviceDisplayName(this._hass, id) || this._capitalize(slug),
          distance,
          isDeparted,
        };
      })
      .filter((row) => !Number.isNaN(row.distance))
      .sort((a, b) => b.distance - a.distance);

    if (rows.length === 0) {
      this.content.innerHTML = `
        <div class="hfc-error">
          Keine Hamster-Fitness-Hamster gefunden (kein
          sensor.hamster_&lt;name&gt;_lifetime_distance in diesem Home Assistant).
        </div>
      `;
      return;
    }

    const medals = ["🥇", "🥈", "🥉"];

    this.content.innerHTML = `
      <div class="hfc-header">
        <span class="hfc-title">🏆 ${this._config.title || "Hamster-Ranking"}</span>
      </div>
      <div class="hfc-ranking">
        ${rows
          .map(
            (row, index) => `
              <div class="hfc-rank-row hfc-clickable" data-entity="${row.entityId}" tabindex="0" role="button">
                <span class="hfc-rank-medal">${medals[index] || `#${index + 1}`}</span>
                <span class="hfc-rank-name">${row.name}${row.isDeparted ? " 🪦" : ""}</span>
                <span class="hfc-rank-value">${row.distance.toFixed(1).replace(".", ",")} km</span>
              </div>
            `
          )
          .join("")}
      </div>
    `;
  }
}

HamsterFitnessRankingCard.styles = `
  .hfc-ranking {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .hfc-rank-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 6px;
  }
  .hfc-rank-medal {
    font-size: 1.2em;
    width: 28px;
    text-align: center;
    flex-shrink: 0;
  }
  .hfc-rank-name {
    flex: 1;
    color: var(--primary-text-color);
  }
  .hfc-rank-value {
    font-weight: 600;
    color: var(--primary-text-color);
  }
`;

customElements.define("hamster-fitness-ranking-card", HamsterFitnessRankingCard);

window.customCards.push({
  type: "hamster-fitness-ranking-card",
  name: "Hamster Fitness: Ranking",
  description:
    "Vergleicht alle Hamster in diesem Home Assistant nach Lebenszeit-Distanz - erkennt sie automatisch, keine Konfiguration nötig.",
});

const RANKING_EDITOR_SCHEMA = [{ name: "title", selector: { text: {} } }];
const RANKING_EDITOR_LABELS = { title: "Titel (optional)" };

class HamsterFitnessRankingCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._renderForm();
  }

  set hass(hass) {
    this._hass = hass;
    this._renderForm();
  }

  _renderForm() {
    if (!this._hass || !this._config) return;

    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => RANKING_EDITOR_LABELS[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        this._config = ev.detail.value;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }

    this._form.hass = this._hass;
    this._form.schema = RANKING_EDITOR_SCHEMA;
    this._form.data = this._config;
  }
}

customElements.define(
  "hamster-fitness-ranking-card-editor",
  HamsterFitnessRankingCardEditor
);
