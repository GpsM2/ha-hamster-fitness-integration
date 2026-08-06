/**
 * Hamster Fitness: Day & Night Card
 *
 * Bundled with the Hamster Fitness integration, auto-registered as a
 * Lovelace resource (see frontend/__init__.py) - no HACS frontend install
 * needed. Big illustrated card: the hamster runs in its wheel (animated,
 * speed-coupled) at night, or sleeps in a nest during the day - driven by
 * the hamster's *actual* activity (night_active_duration sensor), not
 * just the clock, layered on top of a sun-position-driven background.
 *
 * Config:
 *   type: custom:hamster-day-night-card
 *   entity: sensor.hamster_taco_health_score   # required - same as the main card
 *   title: Taco                                 # optional - defaults to the device name
 *   show_speed: true                            # optional, all default true
 *   show_distance: true
 *   show_active_duration: true
 *   show_rest_duration: true
 *   show_climate: true
 *
 * Sibling entities (night_active_duration, day_rest_duration,
 * current_speed, daily_distance, humidity, ...) are resolved the same
 * way as the main card - see hamster-fitness-shared.js.
 */

import {
  deviceDisplayName,
  siblingEntityId,
} from "./hamster-fitness-shared.js";

const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

const MIN_SPIN_S = 0.4;
const MAX_SPIN_S = 6;
const MIN_SPEED_KMH = 0.5;
const MAX_SPEED_KMH = 20;

const NIGHT_GRADIENT = ["#0B132B", "#1C2541"];
const DAY_GRADIENT_HORIZON = ["#F4A261", "#E9C46A"];
const DAY_GRADIENT_MIDDAY = ["#4EA8DE", "#90E0EF"];
const DAY_ELEVATION_FULL_AT = 30; // degrees - gradient stops shifting past this

const STATUS_ONLINE = { label: "Online", color: "#06D6A0" };
const STATUS_OFFLINE = { label: "Offline", color: "#EF476F" };
const STATUS_UNAVAILABLE = { label: "Nicht verfügbar", color: "#8D99AE" };

const DEFAULT_TOGGLES = {
  show_speed: true,
  show_distance: true,
  show_active_duration: true,
  show_rest_duration: true,
  show_climate: true,
};

// Hamster with dumbbells, side view - compact version of
// design/hamster-dumbbell-logo.svg, for the card header. Same
// illustration family as the main card's headband-hamster logo.
const LOGO_DUMBBELL_SVG = `
<svg viewBox="0 0 200 200" width="30" height="30" aria-hidden="true">
  <ellipse cx="70" cy="150" rx="13" ry="9" fill="#C89666" stroke="#8B5A2B" stroke-width="3" transform="rotate(15 70 150)"/>
  <ellipse cx="128" cy="150" rx="13" ry="9" fill="#D9A876" stroke="#8B5A2B" stroke-width="3" transform="rotate(-15 128 150)"/>
  <circle cx="52" cy="122" r="8" fill="#C89666" stroke="#8B5A2B" stroke-width="2.5"/>
  <ellipse cx="100" cy="122" rx="48" ry="38" fill="#C89666" stroke="#8B5A2B" stroke-width="3"/>
  <circle cx="112" cy="70" r="30" fill="#D9A876" stroke="#8B5A2B" stroke-width="3"/>
  <circle cx="90" cy="48" r="9" fill="#C89666" stroke="#8B5A2B" stroke-width="3"/>
  <circle cx="128" cy="46" r="9" fill="#C89666" stroke="#8B5A2B" stroke-width="3"/>
  <circle cx="122" cy="66" r="4.5" fill="#3a2a1a"/>
  <ellipse cx="134" cy="76" rx="6.5" ry="5" fill="#f4d9c6" stroke="#8B5A2B" stroke-width="1.5"/>
  <circle cx="137" cy="76" r="2" fill="#5c4030"/>
  <path d="M138 108 Q158 96 168 74" fill="none" stroke="#D9A876" stroke-width="14" stroke-linecap="round"/>
  <path d="M78 132 Q66 148 60 162" fill="none" stroke="#C89666" stroke-width="13" stroke-linecap="round"/>
  <g transform="rotate(-28 168 74)">
    <rect x="150" y="70" width="36" height="8" rx="4" fill="#5c4a3a"/>
    <rect x="144" y="62" width="12" height="24" rx="4" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
    <rect x="180" y="62" width="12" height="24" rx="4" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
  </g>
</svg>
`;

function hexToRgb(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function lerpColor(hexA, hexB, t) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const rgb = a.map((channel, i) => Math.round(channel + (b[i] - channel) * t));
  return `rgb(${rgb.join(", ")})`;
}

class HamsterDayNightCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error(
        "hamster-day-night-card: 'entity' fehlt - bitte den Health-Score-Sensor eines Hamsters auswählen (endet auf _health_score)."
      );
    }
    if (!config.entity.match(ENTITY_PATTERN)) {
      throw new Error(
        "hamster-day-night-card: 'entity' muss der Health-Score-Sensor eines Hamsters sein (Entity-ID endet auf _health_score)."
      );
    }
    this._config = { ...DEFAULT_TOGGLES, ...config };

    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="hdn-root"></div>
        </ha-card>
        <style>${HamsterDayNightCard.styles}</style>
      `;
      this.content = this.querySelector(".hdn-root");
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
    return 6;
  }

  static getConfigElement() {
    return document.createElement("hamster-day-night-card-editor");
  }

  static getStubConfig(hass, entities) {
    const match = (entities || []).find((id) => ENTITY_PATTERN.test(id));
    return { entity: match || "sensor.hamster_taco_health_score", ...DEFAULT_TOGGLES };
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

  _fmtDuration(minutes) {
    if (minutes === undefined || minutes === null || Number.isNaN(Number(minutes))) {
      return "–";
    }
    const total = Math.max(0, Math.round(Number(minutes)));
    const h = Math.floor(total / 60);
    const m = total % 60;
    return h > 0 ? `${h} Std. ${m} Min.` : `${m} Min.`;
  }

  _backgroundGradient() {
    const sun = this._hass.states["sun.sun"];
    if (!sun || sun.state === "below_horizon") {
      return `linear-gradient(180deg, ${NIGHT_GRADIENT[0]}, ${NIGHT_GRADIENT[1]})`;
    }
    const elevation = Number(sun.attributes && sun.attributes.elevation);
    const t = Number.isFinite(elevation)
      ? Math.min(1, Math.max(0, elevation / DAY_ELEVATION_FULL_AT))
      : 1;
    const from = lerpColor(DAY_GRADIENT_HORIZON[0], DAY_GRADIENT_MIDDAY[0], t);
    const to = lerpColor(DAY_GRADIENT_HORIZON[1], DAY_GRADIENT_MIDDAY[1], t);
    return `linear-gradient(180deg, ${from}, ${to})`;
  }

  _isNight() {
    const sun = this._hass.states["sun.sun"];
    return !sun || sun.state === "below_horizon";
  }

  _spinDurationS(currentSpeed) {
    const speed = currentSpeed ? Number(currentSpeed.state) : NaN;
    const clamped = Number.isFinite(speed)
      ? Math.min(Math.max(speed, MIN_SPEED_KMH), MAX_SPEED_KMH)
      : MIN_SPEED_KMH * 2;
    // Inversely proportional to speed, then clamped to a sane animation range.
    const raw = (MIN_SPIN_S * MAX_SPEED_KMH) / clamped;
    return Math.min(MAX_SPIN_S, Math.max(MIN_SPIN_S, raw)).toFixed(2);
  }

  _connectionStatus(currentSpeedEntityId) {
    const state = this._hass.states[currentSpeedEntityId];
    if (!state) return STATUS_ONLINE; // no speed sensor configured - no reliable signal either way
    if (state.state === "unavailable") return STATUS_OFFLINE;
    if (state.state === "unknown") return STATUS_UNAVAILABLE;
    return STATUS_ONLINE;
  }

  _wheelScene(spinDurationS) {
    return `
      <svg class="hdn-scene-svg" viewBox="0 0 200 200" aria-hidden="true">
        <g class="hdn-wheel-spin" style="animation-duration: ${spinDurationS}s">
          <circle cx="100" cy="100" r="82" fill="none" stroke="#8B5A2B" stroke-width="11"/>
          <circle cx="100" cy="100" r="68" fill="#C19A6B" opacity="0.3"/>
          <g stroke="#8B5A2B" stroke-width="6" stroke-linecap="round">
            <line x1="100" y1="20" x2="100" y2="180"/>
            <line x1="20" y1="100" x2="180" y2="100"/>
            <line x1="44" y1="44" x2="156" y2="156"/>
            <line x1="156" y1="44" x2="44" y2="156"/>
          </g>
          <circle cx="100" cy="100" r="11" fill="#8B5A2B"/>
        </g>
        <g class="hdn-hamster-run">
          <ellipse cx="88" cy="172" rx="10" ry="6" fill="#C89666" stroke="#8B5A2B" stroke-width="2"/>
          <ellipse cx="112" cy="172" rx="10" ry="6" fill="#D9A876" stroke="#8B5A2B" stroke-width="2"/>
          <ellipse cx="100" cy="158" rx="26" ry="19" fill="#C89666" stroke="#8B5A2B" stroke-width="2.5"/>
          <circle cx="120" cy="144" r="15" fill="#D9A876" stroke="#8B5A2B" stroke-width="2.5"/>
          <circle cx="112" cy="132" r="5" fill="#C89666" stroke="#8B5A2B" stroke-width="2"/>
          <circle cx="126" cy="141" r="2.3" fill="#3a2a1a"/>
        </g>
      </svg>
    `;
  }

  _restScene() {
    return `
      <svg class="hdn-scene-svg" viewBox="0 0 200 200" aria-hidden="true">
        <g opacity="0.3">
          <circle cx="100" cy="55" r="38" fill="none" stroke="#8B5A2B" stroke-width="6"/>
          <line x1="100" y1="19" x2="100" y2="91" stroke="#8B5A2B" stroke-width="3"/>
          <line x1="64" y1="55" x2="136" y2="55" stroke="#8B5A2B" stroke-width="3"/>
        </g>
        <text class="hdn-zzz hdn-zzz-1" x="128" y="95">Z</text>
        <text class="hdn-zzz hdn-zzz-2" x="144" y="78">Z</text>
        <text class="hdn-zzz hdn-zzz-3" x="160" y="62">Z</text>
        <ellipse cx="100" cy="168" rx="58" ry="17" fill="#e8d3a0"/>
        <path d="M50 168 q10 -8 20 0 M60 172 q10 -8 20 0 M120 172 q10 -8 20 0 M130 168 q10 -8 20 0"
              fill="none" stroke="#c9a86a" stroke-width="2.5" stroke-linecap="round"/>
        <g class="hdn-hamster-sleep">
          <ellipse cx="100" cy="150" rx="40" ry="30" fill="#C89666" stroke="#8B5A2B" stroke-width="3"/>
          <circle cx="70" cy="134" r="21" fill="#D9A876" stroke="#8B5A2B" stroke-width="3"/>
          <circle cx="57" cy="121" r="7.5" fill="#C89666" stroke="#8B5A2B" stroke-width="2"/>
          <path d="M60 132 q4 3 8 0" fill="none" stroke="#3a2a1a" stroke-width="2.2" stroke-linecap="round"/>
          <ellipse cx="80" cy="140" rx="5" ry="4" fill="#f4d9c6"/>
        </g>
      </svg>
    `;
  }

  _render() {
    if (!this._hass || !this.content || !this._config) return;

    const healthScore = this._entity("health_score");
    if (!healthScore) {
      this.content.innerHTML = `
        <div class="hdn-error">
          Entity "<strong>${this._config.entity}</strong>" nicht gefunden.
          Prüfe die Karten-Konfiguration.
        </div>
      `;
      return;
    }

    const nightActive = this._entity("night_active_duration");
    const dayRest = this._entity("day_rest_duration");
    const currentSpeed = this._entity("current_speed");
    const dailyDistance = this._entity("daily_distance");
    const humidity = this._entity("humidity");
    const temperature = healthScore.attributes.temperature;

    const activeMinutes = nightActive ? Number(nightActive.state) : 0;
    const isActive = Number.isFinite(activeMinutes) && activeMinutes > 0;

    const title =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._capitalize(this._config.entity.match(ENTITY_PATTERN)[1]);

    const status = this._connectionStatus(this._entityId("current_speed"));
    const scene = isActive
      ? this._wheelScene(this._spinDurationS(currentSpeed))
      : this._restScene();

    this.content.style.setProperty("--hdn-bg", this._backgroundGradient());

    this.content.innerHTML = `
      <div class="hdn-banner" style="background: var(--hdn-bg)">
        ${this._isNight() ? this._starsAndMoon() : ""}
        <div class="hdn-header">
          ${LOGO_DUMBBELL_SVG}
          <div class="hdn-header-text">
            <span class="hdn-title">${title.toUpperCase()}</span>
            <span class="hdn-subtitle">Hamster Day &amp; Night</span>
          </div>
        </div>
        <div class="hdn-scene">${scene}</div>
      </div>

      <div class="hdn-stats">
        ${
          this._config.show_active_duration
            ? `<div class="hdn-stat hdn-clickable" data-entity="${this._entityId("night_active_duration")}" tabindex="0" role="button">
                 <span class="hdn-stat-label">Aktuelle Lauf-Dauer</span>
                 <span class="hdn-stat-value">${this._fmtDuration(activeMinutes)}</span>
               </div>`
            : ""
        }
        ${
          this._config.show_rest_duration
            ? `<div class="hdn-stat hdn-clickable" data-entity="${this._entityId("day_rest_duration")}" tabindex="0" role="button">
                 <span class="hdn-stat-label">Ruhezeit</span>
                 <span class="hdn-stat-value">${this._fmtDuration(dayRest && dayRest.state)}</span>
               </div>`
            : ""
        }
        ${
          this._config.show_speed
            ? `<div class="hdn-stat hdn-clickable" data-entity="${this._entityId("current_speed")}" tabindex="0" role="button">
                 <span class="hdn-stat-label">Geschwindigkeit</span>
                 <span class="hdn-stat-value">${this._fmt(currentSpeed && currentSpeed.state, 1, "km/h")}</span>
               </div>`
            : ""
        }
        ${
          this._config.show_distance
            ? `<div class="hdn-stat hdn-clickable" data-entity="${this._entityId("daily_distance")}" tabindex="0" role="button">
                 <span class="hdn-stat-label">Distanz heute</span>
                 <span class="hdn-stat-value">${this._fmt(dailyDistance && dailyDistance.state, 2, "km")}</span>
               </div>`
            : ""
        }
        ${
          this._config.show_climate
            ? `<div class="hdn-stat hdn-clickable" data-entity="${this._entityId("health_score")}" tabindex="0" role="button">
                 <span class="hdn-stat-label">Temperatur</span>
                 <span class="hdn-stat-value">${this._fmt(temperature, 1, "°C")}</span>
               </div>
               ${
                 humidity
                   ? `<div class="hdn-stat hdn-clickable" data-entity="${this._entityId("humidity")}" tabindex="0" role="button">
                        <span class="hdn-stat-label">Luftfeuchtigkeit</span>
                        <span class="hdn-stat-value">${this._fmt(humidity.state, 0, "%")}</span>
                      </div>`
                   : ""
               }`
            : ""
        }
      </div>

      <div class="hdn-footer">
        <span class="hdn-status-dot" style="background: ${status.color}"></span>
        <span class="hdn-status-label" style="color: ${status.color}">${status.label}</span>
      </div>
    `;
  }

  _starsAndMoon() {
    return `
      <svg class="hdn-stars" viewBox="0 0 300 160" preserveAspectRatio="none" aria-hidden="true">
        <circle cx="30" cy="24" r="1.6" fill="#fff" opacity="0.8"/>
        <circle cx="70" cy="14" r="1.1" fill="#fff" opacity="0.6"/>
        <circle cx="120" cy="30" r="1.4" fill="#fff" opacity="0.7"/>
        <circle cx="160" cy="12" r="1" fill="#fff" opacity="0.5"/>
        <circle cx="200" cy="26" r="1.3" fill="#fff" opacity="0.7"/>
        <circle cx="50" cy="44" r="1" fill="#fff" opacity="0.5"/>
        <circle cx="100" cy="10" r="1.2" fill="#fff" opacity="0.6"/>
        <path d="M258 34 a16 16 0 1 0 0.5 0 a12 12 0 1 1 -0.5 0" fill="#F4E285" opacity="0.9"/>
      </svg>
    `;
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
}

HamsterDayNightCard.styles = `
  ha-card {
    padding: 0;
    overflow: hidden;
  }
  .hdn-error {
    color: var(--secondary-text-color);
    font-size: 0.9em;
    padding: 16px;
  }
  .hdn-banner {
    position: relative;
    padding: 16px 16px 0;
    overflow: hidden;
    transition: background 0.6s ease;
  }
  .hdn-stars {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100px;
    pointer-events: none;
  }
  .hdn-header {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    z-index: 1;
  }
  .hdn-header-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }
  .hdn-title {
    font-size: 1.3em;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: #ffffff;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
  }
  .hdn-subtitle {
    font-size: 0.75em;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.85);
  }
  .hdn-scene {
    position: relative;
    margin-top: 4px;
    z-index: 1;
  }
  .hdn-scene-svg {
    display: block;
    width: 100%;
    height: auto;
    max-height: 220px;
  }
  .hdn-wheel-spin {
    transform-origin: 100px 100px;
    animation-name: spinWheel;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
  }
  @keyframes spinWheel {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .hdn-hamster-run {
    animation: runBob 0.5s ease-in-out infinite;
    transform-origin: 100px 172px;
  }
  @keyframes runBob {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-3px); }
  }
  .hdn-hamster-sleep {
    animation: breathPulse 3.5s ease-in-out infinite;
    transform-origin: 100px 150px;
  }
  @keyframes breathPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.03); opacity: 0.92; }
  }
  .hdn-zzz {
    font-size: 16px;
    font-weight: 700;
    fill: #ffffff;
    opacity: 0;
    animation: floatZzz 3s ease-in infinite;
  }
  .hdn-zzz-1 { animation-delay: 0s; }
  .hdn-zzz-2 { animation-delay: 0.6s; }
  .hdn-zzz-3 { animation-delay: 1.2s; }
  @keyframes floatZzz {
    0% { opacity: 0; transform: translateY(6px); }
    15% { opacity: 0.9; }
    80% { opacity: 0.3; }
    100% { opacity: 0; transform: translateY(-14px); }
  }
  .hdn-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
    padding: 14px 16px;
  }
  .hdn-stat {
    display: flex;
    flex-direction: column;
  }
  .hdn-stat-label {
    font-size: 0.75em;
    color: var(--secondary-text-color);
  }
  .hdn-stat-value {
    font-size: 1em;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .hdn-footer {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 16px 14px;
    font-size: 0.8em;
  }
  .hdn-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .hdn-status-label {
    font-weight: 600;
  }
  .hdn-clickable {
    cursor: pointer;
    border-radius: 8px;
    padding: 4px 6px;
    margin: -4px -6px;
    transition: background-color 0.15s ease;
  }
  .hdn-clickable:hover,
  .hdn-clickable:focus-visible {
    background-color: var(--secondary-background-color, rgba(127, 127, 127, 0.15));
    outline: none;
  }

  @media (max-width: 380px) {
    .hdn-title {
      font-size: 1.1em;
    }
    .hdn-scene-svg {
      max-height: 170px;
    }
    .hdn-stats {
      grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
      gap: 6px;
      padding: 10px 12px;
    }
  }
`;

customElements.define("hamster-day-night-card", HamsterDayNightCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-day-night-card",
  name: "Hamster Fitness: Day & Night",
  description:
    "Zeigt den Hamster animiert im Laufrad (nachts/aktiv) oder schlafend im Nest (tagsüber/ruhend), mit sonnenstand-abhängigem Hintergrund.",
});

/**
 * Visual editor ("Configure card" dialog), backed by <ha-form> - same
 * pattern as the other two cards' editors.
 */
const DAY_NIGHT_EDITOR_SCHEMA = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: { integration: "hamster_fitness", domain: "sensor" } } },
  },
  { name: "title", selector: { text: {} } },
  { name: "show_speed", selector: { boolean: {} } },
  { name: "show_distance", selector: { boolean: {} } },
  { name: "show_active_duration", selector: { boolean: {} } },
  { name: "show_rest_duration", selector: { boolean: {} } },
  { name: "show_climate", selector: { boolean: {} } },
];

const DAY_NIGHT_EDITOR_LABELS = {
  entity: "Health-Score-Sensor des Hamsters",
  title: "Titel (optional)",
  show_speed: "Geschwindigkeit anzeigen",
  show_distance: "Distanz anzeigen",
  show_active_duration: "Aktuelle Lauf-Dauer anzeigen",
  show_rest_duration: "Ruhezeit anzeigen",
  show_climate: "Temperatur/Luftfeuchtigkeit anzeigen",
};

class HamsterDayNightCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULT_TOGGLES, ...config };
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
      this._form.computeLabel = (schema) => DAY_NIGHT_EDITOR_LABELS[schema.name] || schema.name;
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
    this._form.schema = DAY_NIGHT_EDITOR_SCHEMA;
    this._form.data = this._config;
  }
}

customElements.define("hamster-day-night-card-editor", HamsterDayNightCardEditor);
