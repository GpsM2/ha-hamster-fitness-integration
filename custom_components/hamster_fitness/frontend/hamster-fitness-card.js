/**
 * Hamster Fitness Card
 *
 * Bundled with the Hamster Fitness integration, auto-registered as a
 * Lovelace resource (see frontend/__init__.py) - no HACS frontend install
 * needed. Shows one hamster's health score, distances, climate and status
 * in a single card, reading entities by their predictable
 * `<domain>.hamster_<hamster>_<suffix>` naming (see coordinator.py's
 * hamster_device_info()).
 *
 * Config:
 *   type: custom:hamster-fitness-card
 *   hamster: taco        # required - the hamster's slug, as in the entity_ids
 *   title: Taco           # optional - defaults to the hamster slug, capitalized
 */

const WARNING_SCORE_THRESHOLD = 50;
const GOOD_SCORE_THRESHOLD = 75;

class HamsterFitnessCard extends HTMLElement {
  setConfig(config) {
    if (!config.hamster) {
      throw new Error(
        "hamster-fitness-card: 'hamster' fehlt in der Card-Konfiguration, z. B. hamster: taco"
      );
    }
    this._config = config;
    this._hamster = config.hamster;
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="hfc-root"></div>
        </ha-card>
        <style>${HamsterFitnessCard.styles}</style>
      `;
      this.content = this.querySelector(".hfc-root");
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  static getStubConfig() {
    return { hamster: "taco" };
  }

  _entity(domain, suffix) {
    const id = `${domain}.hamster_${this._hamster}_${suffix}`;
    return this._hass && this._hass.states[id];
  }

  _fmt(value, decimals, unit) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) {
      return "–";
    }
    const num = Number(value).toFixed(decimals).replace(".", ",");
    return unit ? `${num} ${unit}` : num;
  }

  _scoreColor(score) {
    if (score === null) return "var(--secondary-text-color)";
    if (score < WARNING_SCORE_THRESHOLD) return "#e45c5c";
    if (score < GOOD_SCORE_THRESHOLD) return "#f0a63c";
    return "#4caf50";
  }

  _render() {
    if (!this._hass || !this.content) return;

    const healthScore = this._entity("sensor", "health_score");
    const dailyDistance = this._entity("sensor", "daily_distance");
    const nightDistance = this._entity("sensor", "night_distance");
    const lifetimeDistance = this._entity("sensor", "lifetime_distance");
    const currentSpeed = this._entity("sensor", "current_speed");
    const maxSpeedTonight = this._entity("sensor", "max_speed_tonight");
    const humidity = this._entity("sensor", "humidity");
    const warning = this._entity("binary_sensor", "warning");
    const door = this._entity("binary_sensor", "door");
    const weight = this._entity("number", "weight");
    const departureDate = this._entity("date", "departure_date");

    if (!healthScore) {
      this.content.innerHTML = `
        <div class="hfc-error">
          Keine Entities für Hamster "<strong>${this._hamster}</strong>" gefunden.
          Prüfe die Schreibweise (siehe sensor.hamster_${this._hamster}_health_score
          im Entwicklertools-Bereich "Zustände").
        </div>
      `;
      return;
    }

    const score = Number(healthScore.state);
    const scoreValid = !Number.isNaN(score);
    const scoreColor = this._scoreColor(scoreValid ? score : null);
    const ringCircumference = 2 * Math.PI * 42;
    const ringOffset = scoreValid
      ? ringCircumference * (1 - Math.min(Math.max(score, 0), 100) / 100)
      : 0;

    const temperature = healthScore.attributes.temperature;
    const title = this._config.title || this._capitalize(this._hamster);
    const isDeparted = departureDate && departureDate.state && departureDate.state !== "unknown";
    const warningOn = warning && warning.state === "on";
    const doorOpen = door && door.state === "on";

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

      <div class="hfc-body">
        <div class="hfc-ring">
          <svg viewBox="0 0 100 100">
            <circle class="hfc-ring-bg" cx="50" cy="50" r="42"></circle>
            <circle
              class="hfc-ring-fg"
              cx="50" cy="50" r="42"
              stroke="${scoreColor}"
              stroke-dasharray="${ringCircumference}"
              stroke-dashoffset="${ringOffset}"
            ></circle>
          </svg>
          <div class="hfc-ring-label">
            <span class="hfc-ring-value" style="color:${scoreColor}">${
      scoreValid ? Math.round(score) : "–"
    }</span>
            <span class="hfc-ring-unit">%</span>
          </div>
        </div>

        <div class="hfc-stats">
          <div class="hfc-stat">
            <span class="hfc-stat-label">Heute</span>
            <span class="hfc-stat-value">${this._fmt(dailyDistance && dailyDistance.state, 2, "km")}</span>
          </div>
          <div class="hfc-stat">
            <span class="hfc-stat-label">Heute Nacht</span>
            <span class="hfc-stat-value">${this._fmt(nightDistance && nightDistance.state, 2, "km")}</span>
          </div>
          <div class="hfc-stat">
            <span class="hfc-stat-label">Insgesamt</span>
            <span class="hfc-stat-value">${this._fmt(lifetimeDistance && lifetimeDistance.state, 1, "km")}</span>
          </div>
          ${
            currentSpeed
              ? `<div class="hfc-stat">
                   <span class="hfc-stat-label">Geschwindigkeit</span>
                   <span class="hfc-stat-value">${this._fmt(currentSpeed.state, 1, "km/h")}</span>
                 </div>`
              : ""
          }
          ${
            maxSpeedTonight
              ? `<div class="hfc-stat">
                   <span class="hfc-stat-label">Max. heute Nacht</span>
                   <span class="hfc-stat-value">${this._fmt(maxSpeedTonight.state, 1, "km/h")}</span>
                 </div>`
              : ""
          }
          <div class="hfc-stat">
            <span class="hfc-stat-label">Temperatur</span>
            <span class="hfc-stat-value">${this._fmt(temperature, 1, "°C")}</span>
          </div>
          ${
            humidity
              ? `<div class="hfc-stat">
                   <span class="hfc-stat-label">Luftfeuchtigkeit</span>
                   <span class="hfc-stat-value">${this._fmt(humidity.state, 0, "%")}</span>
                 </div>`
              : ""
          }
          ${
            weight && weight.state && weight.state !== "unknown"
              ? `<div class="hfc-stat">
                   <span class="hfc-stat-label">Gewicht</span>
                   <span class="hfc-stat-value">${this._fmt(weight.state, 0, "g")}</span>
                 </div>`
              : ""
          }
        </div>
      </div>

      ${
        door
          ? `<div class="hfc-footer">
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
  .hfc-body {
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
  }
  .hfc-ring {
    position: relative;
    width: 100px;
    height: 100px;
    flex-shrink: 0;
  }
  .hfc-ring svg {
    width: 100%;
    height: 100%;
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
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .hfc-ring-value {
    font-size: 1.5em;
    font-weight: 700;
    line-height: 1;
  }
  .hfc-ring-unit {
    font-size: 0.75em;
    color: var(--secondary-text-color);
  }
  .hfc-stats {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
    gap: 10px;
    min-width: 180px;
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
`;

customElements.define("hamster-fitness-card", HamsterFitnessCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-fitness-card",
  name: "Hamster Fitness Card",
  description:
    "Zeigt Health Score, Laufstrecken, Klima und Status eines Hamsters aus der Hamster-Fitness-Integration.",
});
