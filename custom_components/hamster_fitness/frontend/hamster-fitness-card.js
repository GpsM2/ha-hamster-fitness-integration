/**
 * Hamster Fitness: Health Score Card
 *
 * Bundled with the Hamster Fitness integration, auto-registered as a
 * Lovelace resource (see frontend/__init__.py) - no HACS frontend install
 * needed.
 *
 * Layout mirrors the Day & Night card: a coloured banner header (the very
 * same markup and CSS, from hamster-fitness-shared.js) over the score
 * ring, a plain-language "Smart Insight", the four pillars of health as
 * an interactive 2x2 grid, and a 7-day trend at the bottom. Each pillar
 * tile opens a modal with the concrete numbers behind it plus a care tip.
 *
 * Config:
 *   type: custom:hamster-fitness-card
 *   entity: sensor.hamster_taco_health_score   # required - the hamster's Health Score sensor
 *   title: Taco                                 # optional - defaults to the device name
 *   max_speed: 5                                # optional - km/h, scale of the speed ring (default 5)
 *   show_speed: true                            # optional - second ring next to the score
 *   show_pillars: true
 *   show_trend: true
 *
 * Sibling entities (night_distance, lifetime_distance, current_speed,
 * the four pillar scores, humidity, warning, door, weight,
 * departure_date) are found via the entity/device registry: same
 * device_id as `entity`, matched by translation_key (see
 * siblingEntityId() in hamster-fitness-shared.js). translation_key is a
 * fixed English string set in Python and never changes, unlike entity_id -
 * which Home Assistant generates once from the *translated* name active
 * when the entity was first created, so it can end up in German, French,
 * etc. instead of English. If registry data isn't available, this falls
 * back to swapping `entity`'s `_health_score` suffix, which only works
 * when entity_id happens to be English.
 *
 * The entity_id itself only needs to END in "_health_score" - it does NOT
 * have to start with "hamster_". New hamsters get that prefix (see
 * hamster_device_info()), but entities created before that naming change
 * keep their original entity_id unless manually renamed.
 *
 * With no usable entity (the dashboard editor's preview, before a
 * hamster is picked) the card renders itself from demo data instead of an
 * error, so the layout is visible while configuring it.
 */

import {
  HAMSTER_PREFIX,
  HEADER_STYLES,
  applyFur,
  coatColor,
  deviceDisplayName,
  renderCardHeader,
  shade,
  siblingEntityId,
} from "./hamster-fitness-shared.js?v=2";

const WARNING_SCORE_THRESHOLD = 50;
const GOOD_SCORE_THRESHOLD = 75;
const DEFAULT_MAX_SPEED = 5;
const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

const RING_COLOR_NEUTRAL = "#00b8a9";
const COLOR_GOOD = "#4caf50";
const COLOR_WATCH = "#f0a63c";
const COLOR_BAD = "#e45c5c";

const DEFAULT_TOGGLES = {
  show_speed: true,
  show_pillars: true,
  show_trend: true,
};

/**
 * The four pillars of health. `key` is the sibling entity's
 * translation_key; `tip` is the husbandry advice shown in the modal, and
 * `facts` pulls the concrete numbers behind the score out of that
 * entity's attributes so the modal explains itself rather than just
 * repeating a percentage.
 */
const PILLARS = [
  {
    id: "activity",
    key: "score_activity",
    icon: "🏃",
    name: "Aktivität",
    long: "Aktivität & Ausdauer",
    tip:
      "Hamster verbergen Krankheit instinktiv so lange wie möglich. Ein plötzlicher Einbruch " +
      "der nächtlichen Laufstrecke um mehr als 30 % ist oft das allererste Anzeichen – achte " +
      "auf den Trend, nicht auf eine einzelne Nacht.",
    facts: (attrs, fmt) => [
      ["Diese Nacht", fmt(attrs.night_distance_km, 2, "km")],
      ["Letzte volle Nacht", fmt(attrs.last_completed_night_km, 2, "km")],
      [
        "Ideal",
        `${fmt(attrs.ideal_distance_min_km, 0, "")}–${fmt(attrs.ideal_distance_max_km, 0, "km")}`,
      ],
    ],
  },
  {
    id: "sleep",
    key: "score_sleep",
    icon: "😴",
    name: "Schlaf",
    long: "Schlaf & Ruhequalität",
    tip:
      "Hamster sind dämmerungs- und nachtaktiv. Wird ihre Hauptschlafphase (10:00–17:00 Uhr) " +
      "durch Licht, Erschütterungen oder Käfigöffnungen gestört, entsteht chronischer Stress " +
      "und das Immunsystem leidet.",
    facts: (attrs, fmt) => [
      ["Käfig geöffnet (Schlafzeit)", fmt(attrs.sleep_door_openings, 0, "×")],
      ["Aufgewacht und gelaufen", fmt(attrs.sleep_activity_sessions, 0, "×")],
      [
        "Schlafphase",
        `${fmt(attrs.sleep_phase_start_hour, 0, "")}–${fmt(attrs.sleep_phase_end_hour, 0, "Uhr")}`,
      ],
    ],
  },
  {
    id: "climate",
    key: "score_climate",
    icon: "🌡️",
    name: "Klima",
    long: "Klima & Umgebung",
    tip:
      "Ideal sind 18–22 °C bei 40–60 % Luftfeuchtigkeit. Unter 15 °C droht lebensgefährliche " +
      "Kältestarre, über 24 °C Hitzschlag.",
    facts: (attrs, fmt) => [
      ["Temperatur", fmt(attrs.temperature, 1, "°C")],
      ["Luftfeuchtigkeit", fmt(attrs.humidity, 0, "%")],
    ],
  },
  {
    id: "care",
    key: "score_care",
    icon: "🧹",
    name: "Pflege",
    long: "Pflege & Interaktion",
    tip:
      "Gemessen über den Deckel-/Türsensor: wie regelmäßig der Käfig zum Füttern und Reinigen " +
      "geöffnet wird. Am besten 1–2 kurze Öffnungen am späten Abend; häufiges Öffnen tagsüber " +
      "besser vermeiden.",
    facts: (attrs, fmt) => [
      ["Deckel zu seit", fmt(attrs.hours_door_closed, 0, "Std.")],
      ["Deckel gerade", attrs.door_open ? "offen" : "geschlossen"],
      ["Als vernachlässigt ab", fmt(attrs.neglect_threshold_hours, 0, "Std.")],
    ],
  },
];

// Running hamster with a headband - same illustration family as the
// Day & Night card's dumbbell logo (see design/hamster-headband-logo.svg),
// tinted with the hamster's own coat colour.
const LOGO_HEADBAND_SVG = `
<svg viewBox="0 0 48 48" width="34" height="34" aria-hidden="true">
  <ellipse cx="24" cy="30" rx="14" ry="11" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="1"/>
  <ellipse cx="15" cy="34" rx="4.2" ry="3" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="1"/>
  <ellipse cx="33" cy="34" rx="4.2" ry="3" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="1"/>
  <circle cx="24" cy="17" r="9.5" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="1"/>
  <path d="M15.5 12.5 A9.5 9.5 0 0 1 32.5 12.5 L31 9.5 A11 11 0 0 0 17 9.5 Z" fill="#e45c5c"/>
  <circle cx="17" cy="10" r="2.6" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="1"/>
  <circle cx="31" cy="10" r="2.6" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="1"/>
  <circle cx="20" cy="16" r="1.4" fill="#3a2a1a"/>
  <circle cx="28" cy="16" r="1.4" fill="#3a2a1a"/>
  <ellipse cx="24" cy="20" rx="2.2" ry="1.6" fill="#f4d9c6"/>
  <circle cx="24" cy="19.3" r="0.7" fill="#5c4030"/>
</svg>
`;

/** Demo values for the dashboard editor preview (no entity yet). */
const MOCK = {
  name: "Taco",
  score: 88,
  months: 9,
  speed: 3.4,
  pillars: { activity: 100, sleep: 80, climate: 100, care: 92 },
  insight: "Alles im grünen Bereich – gestern Nacht 6,1 km gelaufen.",
  history: [
    { date: "2026-07-31", score: 74 },
    { date: "2026-08-01", score: 81 },
    { date: "2026-08-02", score: 92 },
    { date: "2026-08-03", score: 88 },
    { date: "2026-08-04", score: 70 },
    { date: "2026-08-05", score: 85 },
    { date: "2026-08-06", score: 88 },
  ],
};

function scoreColor(score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) {
    return "var(--secondary-text-color)";
  }
  if (score < WARNING_SCORE_THRESHOLD) return COLOR_BAD;
  if (score < GOOD_SCORE_THRESHOLD) return COLOR_WATCH;
  return COLOR_GOOD;
}

function scoreBadge(score) {
  if (score === null || Number.isNaN(Number(score))) {
    return { label: "Unbekannt", color: "#8D99AE" };
  }
  if (score < WARNING_SCORE_THRESHOLD) {
    return { label: "Tierarzt prüfen", color: COLOR_BAD };
  }
  if (score < GOOD_SCORE_THRESHOLD) return { label: "Beobachten", color: COLOR_WATCH };
  return { label: "Voll vital", color: COLOR_GOOD };
}

/** "seit 9 Monaten bei dir", from the acquisition date. */
function togetherSince(acquisitionDate) {
  if (!acquisitionDate) return "Health Score";
  const start = new Date(acquisitionDate);
  if (Number.isNaN(start.getTime())) return "Health Score";
  const days = Math.floor((Date.now() - start.getTime()) / 86400000);
  if (days < 0) return "Health Score";
  if (days < 31) return `seit ${days} ${days === 1 ? "Tag" : "Tagen"} bei dir`;
  const months = Math.floor(days / 30.44);
  if (months < 24) {
    return `seit ${months} ${months === 1 ? "Monat" : "Monaten"} bei dir`;
  }
  const years = Math.floor(months / 12);
  return `seit ${years} Jahren bei dir`;
}

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
    this._config = { ...DEFAULT_TOGGLES, ...config };
    this._hamster = match[1].replace(HAMSTER_PREFIX, "");
    this._maxSpeed =
      Number(config.max_speed) > 0 ? Number(config.max_speed) : DEFAULT_MAX_SPEED;
    this._ensureSkeleton();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  static getConfigElement() {
    return document.createElement("hamster-fitness-card-editor");
  }

  static getStubConfig(hass, entities) {
    const match = (entities || []).find((id) => ENTITY_PATTERN.test(id));
    return { entity: match || "sensor.hamster_taco_health_score", ...DEFAULT_TOGGLES };
  }

  _ensureSkeleton() {
    if (this._root) return;

    this.innerHTML = `
      <ha-card>
        <div class="hfc-root">
          <div class="hfc-banner"></div>
          <div class="hfc-body"></div>
          <div class="hfc-modal-host"></div>
        </div>
      </ha-card>
      <style>${HamsterFitnessCard.styles}</style>
    `;

    this._root = this.querySelector(".hfc-root");
    this._bannerEl = this.querySelector(".hfc-banner");
    this._bodyEl = this.querySelector(".hfc-body");
    this._modalHost = this.querySelector(".hfc-modal-host");

    // Event delegation: the body is re-rendered wholesale, so per-element
    // listeners would be lost. Nothing here animates, unlike the Day &
    // Night card's wheel, so a full re-render is fine.
    const openMoreInfo = (target) => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: target.dataset.entity },
          bubbles: true,
          composed: true,
        })
      );
    };
    const handle = (ev) => {
      const tile = ev.target.closest("[data-pillar]");
      if (tile) {
        ev.preventDefault();
        this._openModal(tile.dataset.pillar);
        return;
      }
      const target = ev.target.closest("[data-entity]");
      if (target) openMoreInfo(target);
    };
    this._root.addEventListener("click", (ev) => {
      if (ev.target.closest(".hfc-modal-host")) return;
      handle(ev);
    });
    this._root.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      if (ev.target.closest(".hfc-modal-host")) return;
      if (!ev.target.closest("[data-pillar], [data-entity]")) return;
      ev.preventDefault();
      handle(ev);
    });

    this._modalHost.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-close]") || ev.target === this._modalHost.firstElementChild) {
        this._closeModal();
      }
    });
    this._onKeyDown = (ev) => {
      if (ev.key === "Escape" && this._modalHost.hasChildNodes()) this._closeModal();
    };
  }

  connectedCallback() {
    if (this._onKeyDown) document.addEventListener("keydown", this._onKeyDown);
  }

  disconnectedCallback() {
    if (this._onKeyDown) document.removeEventListener("keydown", this._onKeyDown);
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
        <div class="hfc-ring-value" style="color: ${valid ? color : "var(--secondary-text-color)"}">
          <span class="hfc-ring-number">${displayValue}</span>
          <span class="hfc-ring-unit">${unit}</span>
        </div>
        <div class="hfc-ring-caption">${label}</div>
      </div>
    `;
  }

  _pillarTile(pillar, value) {
    const valid = value !== null && !Number.isNaN(Number(value));
    const color = scoreColor(valid ? Number(value) : null);
    const pct = valid ? Math.min(100, Math.max(0, Number(value))) : 0;
    return `
      <div class="hfc-tile" data-pillar="${pillar.id}" tabindex="0" role="button"
           aria-label="${pillar.long} – Details anzeigen">
        <div class="hfc-tile-top">
          <span class="hfc-tile-icon">${pillar.icon}</span>
          <span class="hfc-tile-name">${pillar.name}</span>
          <span class="hfc-tile-value" style="color: ${color}">${valid ? Math.round(value) : "–"}</span>
        </div>
        <div class="hfc-tile-bar"><span style="width: ${pct}%; background: ${color}"></span></div>
      </div>
    `;
  }

  _trend(currentScore, history) {
    if (!history.length) {
      return `
        <div class="hfc-trend">
          <div class="hfc-section-label">7-Tage-Trend</div>
          <div class="hfc-trend-empty">
            Noch keine abgeschlossenen Tage – der erste Wert erscheint morgen früh um 9 Uhr.
          </div>
        </div>
      `;
    }

    const scores = history.map((item) => Number(item.score)).filter((n) => !Number.isNaN(n));
    const avg = scores.reduce((sum, n) => sum + n, 0) / scores.length;
    const delta = currentScore === null ? null : Math.round(currentScore - avg);
    const deltaText =
      delta === null
        ? ""
        : delta > 0
          ? `<span class="hfc-delta hfc-delta-up">+${delta} ggü. Schnitt</span>`
          : delta < 0
            ? `<span class="hfc-delta hfc-delta-down">${delta} ggü. Schnitt</span>`
            : `<span class="hfc-delta">wie im Schnitt</span>`;

    const bars = history
      .map((item) => {
        const value = Number(item.score);
        const valid = !Number.isNaN(value);
        const height = valid ? Math.max(4, value) : 4;
        const day = new Date(item.date);
        const label = Number.isNaN(day.getTime())
          ? "?"
          : day.toLocaleDateString("de-DE", { weekday: "short" }).slice(0, 2);
        return `
          <div class="hfc-bar-col" title="${item.date}: ${valid ? value : "?"}">
            <div class="hfc-bar-track">
              <div class="hfc-bar" style="height: ${height}%; background: ${scoreColor(valid ? value : null)}"></div>
            </div>
            <span class="hfc-bar-label">${label}</span>
          </div>
        `;
      })
      .join("");

    return `
      <div class="hfc-trend">
        <div class="hfc-section-label">
          7-Tage-Trend
          <span class="hfc-trend-avg">Ø ${Math.round(avg)}</span>
          ${deltaText}
        </div>
        <div class="hfc-bars">${bars}</div>
      </div>
    `;
  }

  _openModal(pillarId) {
    const pillar = PILLARS.find((item) => item.id === pillarId);
    if (!pillar) return;

    const state = this._entity(pillar.key);
    const value = state ? Number(state.state) : this._mock.pillars[pillar.id];
    const attrs = state ? state.attributes : this._mockAttrs(pillar.id);
    const color = scoreColor(value);
    const facts = pillar
      .facts(attrs, (v, d, u) => this._fmt(v, d, u))
      .map(
        ([label, text]) =>
          `<div class="hfc-fact"><span>${label}</span><strong>${text}</strong></div>`
      )
      .join("");

    this._modalHost.innerHTML = `
      <div class="hfc-overlay">
        <div class="hfc-modal" role="dialog" aria-modal="true" aria-label="${pillar.long}">
          <div class="hfc-modal-head" style="background: ${color}">
            <span class="hfc-modal-icon">${pillar.icon}</span>
            <span class="hfc-modal-title">${pillar.long}</span>
            <button class="hfc-modal-close" data-close type="button" aria-label="Schließen">×</button>
          </div>
          <div class="hfc-modal-body">
            <div class="hfc-modal-score" style="color: ${color}">
              ${Number.isNaN(Number(value)) ? "–" : Math.round(value)}<span>/100</span>
            </div>
            <div class="hfc-facts">${facts}</div>
            <div class="hfc-tip">
              <span class="hfc-tip-label">Gut zu wissen</span>
              <p>${pillar.tip}</p>
            </div>
            ${
              state
                ? `<button class="hfc-modal-link" data-close data-entity="${this._entityId(pillar.key)}" type="button">Verlauf öffnen</button>`
                : ""
            }
          </div>
        </div>
      </div>
    `;
    const closeButton = this._modalHost.querySelector(".hfc-modal-close");
    if (closeButton) closeButton.focus();
  }

  _closeModal() {
    this._modalHost.innerHTML = "";
  }

  _mockAttrs(pillarId) {
    const byPillar = {
      activity: {
        night_distance_km: 6.1,
        last_completed_night_km: 5.4,
        ideal_distance_min_km: 5,
        ideal_distance_max_km: 10,
      },
      sleep: {
        sleep_door_openings: 1,
        sleep_activity_sessions: 0,
        sleep_phase_start_hour: 10,
        sleep_phase_end_hour: 17,
      },
      climate: { temperature: 21.4, humidity: 52 },
      care: { hours_door_closed: 14, door_open: false, neglect_threshold_hours: 48 },
    };
    return byPillar[pillarId] || {};
  }

  _render() {
    if (!this._root || !this._config) return;

    const healthScore = this._hass ? this._entity("health_score") : undefined;
    const preview = !healthScore;
    this._mock = MOCK;
    this._root.classList.toggle("hfc-preview", preview);

    const attrs = healthScore ? healthScore.attributes : {};
    const score = healthScore ? Number(healthScore.state) : MOCK.score;
    const scoreValid = !Number.isNaN(score);
    const color = scoreColor(scoreValid ? score : null);
    const badge = scoreBadge(scoreValid ? score : null);

    applyFur(this._root, coatColor(healthScore));

    const title = preview
      ? MOCK.name
      : this._config.title ||
        deviceDisplayName(this._hass, this._config.entity) ||
        this._capitalize(this._hamster);

    const departureDate = this._entity("departure_date");
    const isDeparted =
      departureDate && departureDate.state && departureDate.state !== "unknown";
    const subtitle = isDeparted
      ? "ausgezogen"
      : preview
        ? `seit ${MOCK.months} Monaten bei dir`
        : togetherSince(attrs.acquisition_date);

    this._bannerEl.style.background = `linear-gradient(135deg, ${shade(
      badge.color === "#8D99AE" ? "#8D99AE" : badge.color,
      -0.28
    )}, ${shade(badge.color === "#8D99AE" ? "#8D99AE" : badge.color, -0.05)})`;

    this._bannerEl.innerHTML = renderCardHeader({
      logoSvg: LOGO_HEADBAND_SVG,
      title: title.toUpperCase(),
      subtitle,
      badgeHtml: `<span class="hf-badge">
        <span class="hf-badge-dot" style="background: ${badge.color}"></span>
        ${badge.label}
      </span>`,
    });

    const currentSpeed = this._entity("current_speed");
    const warning = this._entity("warning");
    const warningOn = warning && warning.state === "on";
    const insight = preview
      ? MOCK.insight
      : warningOn && warning.attributes.warning_reason
        ? warning.attributes.warning_reason
        : this._positiveInsight(attrs, scoreValid ? score : null);

    const rings = `
      ${this._ring({
        value: scoreValid ? score : null,
        max: 100,
        color,
        decimals: 0,
        unit: "%",
        label: "Health Score",
        entityId: preview ? null : this._entityId("health_score"),
      })}
      ${
        this._config.show_speed && (preview || currentSpeed)
          ? this._ring({
              value: preview ? MOCK.speed : currentSpeed.state,
              max: this._maxSpeed,
              color: RING_COLOR_NEUTRAL,
              decimals: 1,
              unit: "km/h",
              label: "Geschwindigkeit",
              entityId: preview ? null : this._entityId("current_speed"),
            })
          : ""
      }
    `;

    const pillars = this._config.show_pillars
      ? `<div class="hfc-tiles">${PILLARS.map((pillar) => {
          const state = this._entity(pillar.key);
          const value = preview
            ? MOCK.pillars[pillar.id]
            : state
              ? Number(state.state)
              : null;
          return this._pillarTile(pillar, value);
        }).join("")}</div>`
      : "";

    const history = preview ? MOCK.history : attrs.score_history || [];
    const trend = this._config.show_trend
      ? this._trend(scoreValid ? score : null, history)
      : "";

    this._bodyEl.innerHTML = `
      ${preview ? '<div class="hfc-preview-note">Vorschau mit Beispieldaten</div>' : ""}
      <div class="hfc-rings">${rings}</div>
      <div class="hfc-insight${warningOn ? " hfc-insight-warn" : ""}">
        <span class="hfc-insight-icon">${warningOn ? "⚠️" : "💡"}</span>
        <span class="hfc-insight-text">${insight}</span>
      </div>
      ${pillars}
      ${trend}
    `;
  }

  /**
   * The line shown when no warning is active. Still keyed off the score:
   * a middling score with no acute warning is not "all good", and saying
   * so under an amber badge would just read as contradictory.
   */
  _positiveInsight(attrs, score) {
    if (score !== null && score < GOOD_SCORE_THRESHOLD) {
      return "Nichts akut Auffälliges, aber der Score liegt unter dem üblichen Niveau – die vier Säulen unten zeigen, woran es hängt.";
    }
    const night = Number(
      attrs.night_distance_km >= attrs.last_completed_night_km
        ? attrs.night_distance_km
        : attrs.last_completed_night_km
    );
    if (!Number.isNaN(night) && night > 0) {
      return `Alles im grünen Bereich – zuletzt ${this._fmt(night, 2, "km")} in einer Nacht gelaufen.`;
    }
    return "Alles im grünen Bereich – keine Auffälligkeiten.";
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
}

HamsterFitnessCard.styles = `
  ${HEADER_STYLES}

  ha-card {
    padding: 0;
    overflow: hidden;
  }
  .hfc-root {
    --hf-fur: #D48C46;
    --hf-fur-light: #e0a869;
    --hf-fur-dark: #7f5429;
    --hf-belly: #f2ddc4;
    position: relative;
  }
  .hfc-banner {
    padding: 14px 16px;
    transition: background 0.6s ease;
  }
  .hfc-body {
    padding: 14px 16px 16px;
  }
  .hfc-preview-note {
    font-size: 0.75em;
    color: var(--secondary-text-color);
    margin-bottom: 8px;
  }
  .hfc-error {
    color: var(--secondary-text-color);
    font-size: 0.9em;
    padding: 16px;
  }
  .hfc-rings {
    display: flex;
    justify-content: space-around;
    align-items: flex-start;
    gap: 12px;
  }
  .hfc-ring {
    position: relative;
    flex: 1;
    max-width: 168px;
    text-align: center;
  }
  .hfc-ring svg {
    width: 100%;
    height: auto;
    transform: rotate(-90deg);
  }
  .hfc-ring-bg {
    fill: none;
    stroke: var(--divider-color, #e0e0e0);
    stroke-width: 8;
  }
  .hfc-ring-fg {
    fill: none;
    stroke-width: 8;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.6s ease, stroke 0.6s ease;
  }
  .hfc-ring-value {
    position: absolute;
    top: 42%;
    left: 0;
    right: 0;
    transform: translateY(-50%);
    line-height: 1;
  }
  .hfc-ring-number {
    font-size: 1.9em;
    font-weight: 800;
  }
  .hfc-ring-unit {
    font-size: 0.8em;
    margin-left: 2px;
  }
  .hfc-ring-caption {
    margin-top: 2px;
    font-size: 0.78em;
    color: var(--secondary-text-color);
  }
  .hfc-insight {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    margin-top: 12px;
    padding: 11px 13px;
    border-radius: 14px;
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.1));
    border-left: 4px solid ${COLOR_GOOD};
  }
  .hfc-insight-warn {
    border-left-color: ${COLOR_BAD};
  }
  .hfc-insight-icon {
    flex-shrink: 0;
  }
  .hfc-insight-text {
    font-size: 0.92em;
    color: var(--primary-text-color);
  }
  .hfc-tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 9px;
    margin-top: 12px;
  }
  .hfc-tile {
    padding: 10px 12px;
    border-radius: 14px;
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.1));
    cursor: pointer;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
  }
  .hfc-tile:hover,
  .hfc-tile:focus-visible {
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.14);
    outline: none;
  }
  .hfc-tile-top {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .hfc-tile-name {
    font-size: 0.85em;
    color: var(--primary-text-color);
  }
  .hfc-tile-value {
    margin-left: auto;
    font-size: 1.15em;
    font-weight: 800;
  }
  .hfc-tile-bar {
    margin-top: 7px;
    height: 5px;
    border-radius: 999px;
    background: var(--divider-color, #e0e0e0);
    overflow: hidden;
  }
  .hfc-tile-bar span {
    display: block;
    height: 100%;
    border-radius: 999px;
    transition: width 0.5s ease;
  }
  .hfc-section-label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 14px 0 6px;
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .hfc-trend-avg {
    font-weight: 800;
    color: var(--primary-text-color);
  }
  .hfc-delta {
    margin-left: auto;
    text-transform: none;
    letter-spacing: 0;
    font-size: 1.05em;
  }
  .hfc-delta-up { color: ${COLOR_GOOD}; }
  .hfc-delta-down { color: ${COLOR_BAD}; }
  .hfc-trend-empty {
    font-size: 0.85em;
    color: var(--secondary-text-color);
  }
  .hfc-bars {
    display: flex;
    align-items: flex-end;
    gap: 6px;
    height: 74px;
  }
  .hfc-bar-col {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
  }
  .hfc-bar-track {
    flex: 1;
    width: 100%;
    display: flex;
    align-items: flex-end;
  }
  .hfc-bar {
    width: 100%;
    border-radius: 5px 5px 0 0;
    transition: height 0.5s ease;
  }
  .hfc-bar-label {
    margin-top: 4px;
    font-size: 0.66em;
    color: var(--secondary-text-color);
  }
  .hfc-clickable {
    cursor: pointer;
  }
  .hfc-clickable:focus-visible {
    outline: 2px solid var(--primary-color, #03a9f4);
    outline-offset: 2px;
    border-radius: 8px;
  }

  /* Modal: a plain overlay rather than <ha-dialog>, so the card keeps
     working in the dashboard editor preview and in isolation. */
  .hfc-overlay {
    position: absolute;
    inset: 0;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 14px;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(2px);
  }
  .hfc-modal {
    width: 100%;
    max-width: 380px;
    max-height: 100%;
    overflow: auto;
    border-radius: 18px;
    background: var(--card-background-color, #fff);
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.32);
    animation: hfcModalIn 0.16s ease-out;
  }
  @keyframes hfcModalIn {
    from { opacity: 0; transform: translateY(8px) scale(0.98); }
    to { opacity: 1; transform: none; }
  }
  .hfc-modal-head {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 12px 14px;
    color: #fff;
  }
  .hfc-modal-title {
    font-weight: 800;
  }
  .hfc-modal-close {
    margin-left: auto;
    border: none;
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    font-size: 1.1em;
    line-height: 1;
    cursor: pointer;
  }
  .hfc-modal-body {
    padding: 14px;
  }
  .hfc-modal-score {
    font-size: 2.4em;
    font-weight: 900;
    line-height: 1;
  }
  .hfc-modal-score span {
    font-size: 0.4em;
    font-weight: 700;
    color: var(--secondary-text-color);
  }
  .hfc-facts {
    margin: 12px 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .hfc-fact {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 0.88em;
    color: var(--secondary-text-color);
  }
  .hfc-fact strong {
    color: var(--primary-text-color);
  }
  .hfc-tip {
    padding: 11px 12px;
    border-radius: 12px;
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.1));
  }
  .hfc-tip-label {
    font-size: 0.68em;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .hfc-tip p {
    margin: 5px 0 0;
    font-size: 0.88em;
    line-height: 1.45;
    color: var(--primary-text-color);
  }
  .hfc-modal-link {
    margin-top: 12px;
    width: 100%;
    padding: 9px;
    border: none;
    border-radius: 10px;
    background: var(--primary-color, #03a9f4);
    color: #fff;
    font-family: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  /* Ranking card (same bundle, see below) */
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
  .hfc-plain-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 14px 16px 6px;
  }
  .hfc-plain-title {
    font-size: 1.1em;
    font-weight: 700;
    color: var(--primary-text-color);
  }

  @media (max-width: 400px) {
    .hfc-rings {
      gap: 6px;
    }
    .hfc-ring-number {
      font-size: 1.5em;
    }
    .hfc-tiles {
      gap: 7px;
    }
  }
`;

customElements.define("hamster-fitness-card", HamsterFitnessCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-fitness-card",
  name: "Hamster Fitness: Health Score",
  description:
    "Health Score als Ring, verständlicher Hinweistext, die vier Säulen der Gesundheit zum Antippen und ein 7-Tage-Trend.",
});

const EDITOR_SCHEMA = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: { integration: "hamster_fitness", domain: "sensor" } } },
  },
  { name: "title", selector: { text: {} } },
  { name: "max_speed", selector: { number: { min: 1, max: 30, step: 0.5, mode: "box" } } },
  { name: "show_speed", selector: { boolean: {} } },
  { name: "show_pillars", selector: { boolean: {} } },
  { name: "show_trend", selector: { boolean: {} } },
];

const EDITOR_LABELS = {
  entity: "Health-Score-Sensor des Hamsters",
  title: "Titel (optional)",
  max_speed: "Skala des Geschwindigkeits-Rings (km/h)",
  show_speed: "Geschwindigkeits-Ring anzeigen",
  show_pillars: "Die vier Säulen anzeigen",
  show_trend: "7-Tage-Trend anzeigen",
};

class HamsterFitnessCardEditor extends HTMLElement {
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
 * "lifetime_distance"), so this works regardless of what language
 * entity_ids ended up in. LIFETIME_DISTANCE_PATTERN is only used
 * afterwards, as a fallback for deriving a display name if the device
 * registry lookup fails. Since a departed hamster's lifetime_distance
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
      <div class="hfc-plain-header">
        <span class="hfc-plain-title">🏆 ${this._config.title || "Hamster-Ranking"}</span>
      </div>
      <div class="hfc-ranking" style="padding: 0 12px 12px">
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
