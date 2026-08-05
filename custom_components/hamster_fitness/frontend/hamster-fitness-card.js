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
 * departure_date) are derived from `entity` by swapping its `_health_score`
 * suffix - see coordinator.py's hamster_device_info() for the naming
 * convention this relies on.
 *
 * The entity_id itself only needs to END in "_health_score" - it does NOT
 * have to start with "hamster_". New hamsters get that prefix (see
 * hamster_device_info()), but entities created before that naming change
 * keep their original entity_id (e.g. sensor.taco_health_score) unless
 * manually renamed - Home Assistant never renames entity_ids on its own.
 * A leading "hamster_" is only stripped for the card's display title.
 */

const WARNING_SCORE_THRESHOLD = 50;
const GOOD_SCORE_THRESHOLD = 75;
const DEFAULT_MAX_SPEED = 5;
const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;
const HAMSTER_PREFIX = /^hamster_/;

const RING_COLOR_NEUTRAL = "#00b8a9";

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

  _entityId(suffix) {
    return this._config.entity.replace(HEALTH_SCORE_SUFFIX, suffix);
  }

  _entity(suffix) {
    if (!this._hass) return undefined;
    return this._hass.states[this._entityId(suffix)];
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

    const healthScore = this._entity("_health_score");
    const dailyDistance = this._entity("_daily_distance");
    const nightDistance = this._entity("_night_distance");
    const lifetimeDistance = this._entity("_lifetime_distance");
    const currentSpeed = this._entity("_current_speed");
    const maxSpeedTonight = this._entity("_max_speed_tonight");
    const humidity = this._entity("_humidity");
    const warning = this._entity("_warning");
    const door = this._entity("_door");
    const weight = this._entity("_weight");
    const departureDate = this._entity("_departure_date");

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
    const title = this._config.title || this._capitalize(this._hamster);
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
      entityId: this._entityId("_health_score"),
    });

    const speedRing = this._ring({
      value: currentSpeed ? currentSpeed.state : null,
      max: this._maxSpeed,
      color: RING_COLOR_NEUTRAL,
      decimals: 1,
      unit: "km/h",
      label: "Geschwindigkeit",
      entityId: currentSpeed ? this._entityId("_current_speed") : null,
    });

    this.content.innerHTML = `
      <div class="hfc-header">
        <span class="hfc-title">🐹 ${title}</span>
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

      <div class="hfc-breakdown hfc-clickable" data-entity="${this._entityId("_health_score")}" tabindex="0" role="button">
        ${this._breakdownItem("🏃", "Bewegung", healthScore.attributes.distance_penalty)}
        ${this._breakdownItem("🌡️", "Temperatur", healthScore.attributes.temperature_penalty)}
        ${this._breakdownItem("🧹", "Pflege", healthScore.attributes.care_penalty)}
      </div>

      <div class="hfc-stats">
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_daily_distance")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Heute</span>
          <span class="hfc-stat-value">${this._fmt(dailyDistance && dailyDistance.state, 2, "km")}</span>
        </div>
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_night_distance")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Heute Nacht</span>
          <span class="hfc-stat-value">${this._fmt(nightDistance && nightDistance.state, 2, "km")}</span>
        </div>
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_lifetime_distance")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Insgesamt</span>
          <span class="hfc-stat-value">${this._fmt(lifetimeDistance && lifetimeDistance.state, 1, "km")}</span>
        </div>
        ${
          maxSpeedTonight
            ? `<div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_max_speed_tonight")}" tabindex="0" role="button">
                 <span class="hfc-stat-label">Max. heute Nacht</span>
                 <span class="hfc-stat-value">${this._fmt(maxSpeedTonight.state, 1, "km/h")}</span>
               </div>`
            : ""
        }
        <div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_health_score")}" tabindex="0" role="button">
          <span class="hfc-stat-label">Temperatur</span>
          <span class="hfc-stat-value">${this._fmt(temperature, 1, "°C")}</span>
        </div>
        ${
          humidity
            ? `<div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_humidity")}" tabindex="0" role="button">
                 <span class="hfc-stat-label">Luftfeuchtigkeit</span>
                 <span class="hfc-stat-value">${this._fmt(humidity.state, 0, "%")}</span>
               </div>`
            : ""
        }
        ${
          weight && weight.state && weight.state !== "unknown"
            ? `<div class="hfc-stat hfc-clickable" data-entity="${this._entityId("_weight")}" tabindex="0" role="button">
                 <span class="hfc-stat-label">Gewicht</span>
                 <span class="hfc-stat-value">${this._fmt(weight.state, 0, "g")}</span>
               </div>`
            : ""
        }
      </div>

      ${
        door
          ? `<div class="hfc-footer hfc-clickable" data-entity="${this._entityId("_door")}" tabindex="0" role="button">
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
    font-size: 1.2em;
    font-weight: 600;
    color: var(--primary-text-color);
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
  name: "Hamster Fitness Card",
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
 * lifetime distance - no config needed, entities are auto-discovered by
 * matching any sensor.<name>_lifetime_distance (the entity_id only needs
 * to END in that suffix, a leading "hamster_" is optional - see the note
 * on ENTITY_PATTERN above). Since a departed hamster's lifetime_distance
 * stays frozen (see coordinator.py), retired hamsters remain part of the
 * ranking automatically.
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

    const rows = Object.keys(this._hass.states)
      .map((id) => ({ id, match: id.match(LIFETIME_DISTANCE_PATTERN) }))
      .filter(({ match }) => match)
      .map(({ id, match }) => {
        const state = this._hass.states[id];
        const distance = Number(state.state);
        const departureId = id.replace("_lifetime_distance", "_departure_date");
        const departure = this._hass.states[departureId];
        const isDeparted = departure && departure.state && departure.state !== "unknown";
        const slug = match[1].replace(HAMSTER_PREFIX, "");
        return {
          entityId: id,
          slug,
          name: this._capitalize(slug),
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
  name: "Hamster Fitness Ranking Card",
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
