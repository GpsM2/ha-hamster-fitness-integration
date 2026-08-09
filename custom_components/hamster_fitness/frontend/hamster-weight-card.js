/**
 * Hamster Fitness: Track Weight
 *
 * An input for `number.<hamster>_weight` that looks like something you'd
 * want to use: the hamster sits in the pan of an old household kitchen
 * scale, and the numbered drum below turns to bring the reading up to
 * the marker. The point is that a weight in grams means very little on
 * its own - seeing where the needle lands between the healthy and the
 * worrying bands tells you more at a glance than "97".
 *
 * Weighing is the one thing this integration cannot measure by itself,
 * so it has always been a bare number box behind a more-info dialog.
 *
 * With no value recorded the +/- buttons give way to a plain input
 * field: climbing from zero to a Syrian hamster's ~100 g one tap at a
 * time is no way to enter a first weight. The field stays reachable
 * afterwards behind the pencil button.
 *
 * Config:
 *   type: custom:hamster-weight-card
 *   entity: sensor.hamster_taco_health_score   # required - same as the other cards
 *   title: Taco                                 # optional - defaults to the device name
 *   step: 1                                     # optional - grams per tap
 *
 * The dial's range and its healthy/unhealthy bands come from the
 * hamster's breed, not from the card config - a Roborovski and a Syrian
 * differ by a factor of five, so one fixed scale would be useless for
 * one of them. See WEIGHT_CLASSES in const.py.
 */

import {
  HEADER_STYLES,
  applyFur,
  coatColor,
  daysBetween,
  deviceDisplayName,
  fmtDate,
  fmtNumber,
  renderCardHeader,
  siblingEntityId,
  t,
} from "./hamster-fitness-shared.js?v=10";

const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

const DEFAULTS = {
  step: 1,
};

// Dial geometry. The ring covers 300 degrees rather than a full circle,
// so zero and the maximum never meet under the marker.
const DIAL_CX = 150;
const DIAL_CY = 206;
const DIAL_R = 80;
const DIAL_SWEEP = 300;
// Fallback range when the breed is unknown - wide enough for any species.
const DEFAULT_DIAL_MAX = 250;

const LOGO_SCALE = `
<svg viewBox="0 0 48 48" width="34" height="34" aria-hidden="true">
  <path d="M24 8v28" stroke="#B8860B" stroke-width="3" stroke-linecap="round"/>
  <path d="M8 14h32" stroke="#B8860B" stroke-width="3" stroke-linecap="round"/>
  <circle cx="24" cy="8" r="3" fill="#FFD166" stroke="#B8860B" stroke-width="1.5"/>
  <path d="M4 20a8 5 0 0 0 8 0Z" fill="#FFD166" stroke="#B8860B" stroke-width="1.5"/>
  <path d="M36 20a8 5 0 0 0 8 0Z" fill="#FFD166" stroke="#B8860B" stroke-width="1.5"/>
  <path d="M8 14v6M40 14v6" stroke="#B8860B" stroke-width="1.5"/>
  <rect x="16" y="36" width="16" height="4" rx="2" fill="#FFD166" stroke="#B8860B" stroke-width="1.5"/>
</svg>
`;

class HamsterWeightCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error(t(null, "common.needEntity", { card: "hamster-weight-card" }));
    }
    if (!config.entity.match(ENTITY_PATTERN)) {
      throw new Error(t(null, "common.wrongEntity", { card: "hamster-weight-card" }));
    }
    this._config = { ...DEFAULTS, ...config };
    this._ensureSkeleton();
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
    return document.createElement("hamster-weight-card-editor");
  }

  static getStubConfig(hass, entities) {
    const match = (entities || []).find((id) => ENTITY_PATTERN.test(id));
    return { entity: match || "sensor.hamster_taco_health_score", ...DEFAULTS };
  }

  _ensureSkeleton() {
    if (this._root) return;

    this.innerHTML = `
      <ha-card>
        <div class="hwc-root">
          <div class="hwc-banner"></div>
          <div class="hwc-error" hidden></div>
          <div class="hwc-body" hidden>
            <div class="hwc-scene"></div>
            <div class="hwc-readout"></div>
            <div class="hwc-controls"></div>
            <div class="hwc-note"></div>
          </div>
        </div>
      </ha-card>
      <style>${HamsterWeightCard.styles}</style>
    `;

    this._root = this.querySelector(".hwc-root");
    this._bannerEl = this.querySelector(".hwc-banner");
    this._errorEl = this.querySelector(".hwc-error");
    this._bodyEl = this.querySelector(".hwc-body");
    this._sceneEl = this.querySelector(".hwc-scene");
    this._readoutEl = this.querySelector(".hwc-readout");
    this._controlsEl = this.querySelector(".hwc-controls");
    this._noteEl = this.querySelector(".hwc-note");

    this._root.addEventListener("click", (ev) => {
      const step = ev.target.closest("[data-step]");
      if (step) {
        this._nudge(Number(step.dataset.step));
        return;
      }
      if (ev.target.closest("[data-action='edit']")) {
        this._setEditing(true);
        return;
      }
      if (ev.target.closest("[data-action='cancel']")) {
        this._setEditing(false);
        return;
      }
      if (ev.target.closest("[data-action='save']")) {
        this._commitInput();
        return;
      }
      const target = ev.target.closest("[data-entity]");
      if (target) {
        this.dispatchEvent(
          new CustomEvent("hass-more-info", {
            detail: { entityId: target.dataset.entity },
            bubbles: true,
            composed: true,
          })
        );
      }
    });

    // Enter saves, Escape backs out - the shortcuts anyone typing a
    // number into a field will reach for without being told.
    this._root.addEventListener("keydown", (ev) => {
      if (!ev.target.matches(".hwc-input")) return;
      if (ev.key === "Enter") {
        ev.preventDefault();
        this._commitInput();
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        this._setEditing(false);
      }
    });
  }

  _setEditing(editing) {
    this._editing = editing;
    this._render();
    if (editing) {
      const input = this.querySelector(".hwc-input");
      if (input) {
        input.focus();
        input.select();
      }
    }
  }

  /** Writes whatever is in the input field, if it's a usable number. */
  _commitInput() {
    const input = this.querySelector(".hwc-input");
    const weight = this._entity("weight");
    if (!input || !weight || !this._hass) return;

    const value = Number(input.value);
    if (input.value === "" || Number.isNaN(value)) return;

    const min = Number(weight.attributes.min ?? 0);
    const max = Number(weight.attributes.max ?? DEFAULT_DIAL_MAX);
    this._hass.callService("number", "set_value", {
      entity_id: this._entityId("weight"),
      value: Math.min(max, Math.max(min, value)),
    });
    this._setEditing(false);
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

  /**
   * Applies a relative change to the weight, clamped to the number
   * entity's own min/max so the card can never push a value the entity
   * would reject.
   */
  _nudge(delta) {
    const weight = this._entity("weight");
    if (!weight || !this._hass) return;

    const current = Number(weight.state);
    const base = Number.isNaN(current) ? 0 : current;
    const min = Number(weight.attributes.min ?? 0);
    const max = Number(weight.attributes.max ?? DEFAULT_DIAL_MAX);
    const next = Math.min(max, Math.max(min, base + delta));
    if (next === base) return;

    this._hass.callService("number", "set_value", {
      entity_id: this._entityId("weight"),
      value: next,
    });
  }

  /**
   * The scale's thresholds, taken from the hamster's breed (see
   * WEIGHT_CLASSES in const.py) and surfaced as attributes on the
   * health-score sensor. All null for an unknown breed - the dial then
   * shows a plain range with no healthy/unhealthy zones, because 40 g is
   * fine for a Roborovski and alarming for a Syrian.
   */
  _limits(healthScore) {
    const a = healthScore.attributes;
    return {
      max: Number(a.weight_dial_max_g) || DEFAULT_DIAL_MAX,
      underweight: a.weight_underweight_g ?? null,
      normalMin: a.weight_normal_min_g ?? null,
      normalMax: a.weight_normal_max_g ?? null,
      overweight: a.weight_overweight_g ?? null,
    };
  }

  /** Angle on the dial for a weight, in degrees from the top marker. */
  _angle(grams, max) {
    const clamped = Math.min(max, Math.max(0, grams));
    return (clamped / max) * DIAL_SWEEP;
  }

  /**
   * Arc path between two weights, for the coloured zone bands.
   *
   * Shares `_angle`'s origin with the tick marks - both measure from the
   * top of the dial - so a band always lies under the numbers it
   * describes, whichever way the drum has turned.
   */
  _zonePath(from, to, max, radius) {
    const a1 = this._angle(from, max) * (Math.PI / 180);
    const a2 = this._angle(to, max) * (Math.PI / 180);
    const point = (angle) => [
      DIAL_CX + radius * Math.sin(angle),
      DIAL_CY - radius * Math.cos(angle),
    ];
    const [x1, y1] = point(a1);
    const [x2, y2] = point(a2);
    const large = Math.abs(a2 - a1) > Math.PI ? 1 : 0;
    return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${radius} ${radius} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  }

  /**
   * A household scale in the style of the old cast-iron kitchen ones: a
   * pan on top for the hamster, an ornate case below, and a circular
   * dial whose numbered ring turns behind a fixed marker. The reading
   * sits in the middle of the dial, where the maker's name used to be.
   *
   * Turning the ring rather than sweeping a needle is what the real
   * mechanism does, and it keeps the current number upright at the top
   * instead of upside down at the bottom of a sweep.
   */
  _scene(grams, hasWeight, limits, status) {
    const max = limits.max;
    const rotation = hasWeight ? -this._angle(grams, max) : 0;

    // Numbered ticks around the ring. A round step keeps the labels
    // legible whatever the breed's range happens to be.
    const step = max <= 60 ? 10 : max <= 100 ? 20 : 50;
    const labelY = DIAL_CY - DIAL_R + 30;
    const ticks = [];
    for (let value = 0; value <= max + 0.001; value += step / 5) {
      const major = Math.abs(value % step) < 0.001;
      const angle = this._angle(value, max);
      const inner = major ? DIAL_R - 15 : DIAL_R - 8;
      // The numbers are printed on the drum, so they ride round with it
      // rather than staying upright - which is what the real scale does,
      // and the reading that matters is upright under the marker anyway.
      ticks.push(`
        <g transform="rotate(${angle.toFixed(2)} ${DIAL_CX} ${DIAL_CY})">
          <line x1="${DIAL_CX}" y1="${DIAL_CY - DIAL_R + 2}" x2="${DIAL_CX}" y2="${DIAL_CY - inner}"
                stroke="#5c4a3a" stroke-width="${major ? 2.2 : 1}" opacity="${major ? 0.9 : 0.5}"/>
          ${
            major
              ? `<text x="${DIAL_CX}" y="${labelY}" text-anchor="middle"
                       class="hwc-tick-label">${Math.round(value)}</text>`
              : ""
          }
        </g>`);
    }

    // Healthy/unhealthy bands, only when the breed is known.
    const zones =
      limits.normalMin === null
        ? ""
        : `
          <path d="${this._zonePath(0, limits.underweight, max, DIAL_R - 4)}"
                class="hwc-zone hwc-zone-low"/>
          <path d="${this._zonePath(limits.normalMin, limits.normalMax, max, DIAL_R - 4)}"
                class="hwc-zone hwc-zone-ok"/>
          <path d="${this._zonePath(limits.overweight, max, max, DIAL_R - 4)}"
                class="hwc-zone hwc-zone-high"/>`;

    return `
      <svg class="hwc-svg" viewBox="0 0 300 330" aria-hidden="true">
        <!-- pan on top, hamster sitting in it -->
        <ellipse cx="150" cy="46" rx="88" ry="17" fill="#c9ccd1" stroke="#8A929A" stroke-width="2"/>
        <path d="M62 46 a88 17 0 0 0 176 0 a88 26 0 0 1 -176 0 Z" fill="#b6babf"/>
        ${
          hasWeight
            ? `<g class="hwc-hamster">
                 <ellipse cx="150" cy="24" rx="34" ry="22" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
                 <ellipse cx="152" cy="30" rx="20" ry="12" fill="var(--hf-belly)" opacity="0.7"/>
                 <circle cx="180" cy="12" r="15" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
                 <circle cx="171" cy="1" r="5.5" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2"/>
                 <circle cx="186" cy="9" r="2.3" fill="#3a2a1a"/>
                 <ellipse cx="194" cy="15" rx="4" ry="3" fill="#f4d9c6"/>
                 <path d="M120 28 q-10 4 -14 11" stroke="var(--hf-fur-dark)" stroke-width="3.5"
                       fill="none" stroke-linecap="round"/>
               </g>`
            : `<text x="150" y="34" text-anchor="middle" class="hwc-empty-pan">?</text>`
        }

        <!-- neck -->
        <rect x="144" y="56" width="12" height="34" fill="#8A929A"/>

        <!-- case, loosely after the cast-iron originals -->
        <path d="M40 96 q110 -26 220 0 l-14 16 H54 Z" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
        <rect x="46" y="110" width="208" height="192" rx="10" fill="#A0703F" stroke="#5c4a3a" stroke-width="2"/>
        <rect x="46" y="110" width="16" height="192" fill="#8B5A2B" opacity="0.55"/>
        <rect x="238" y="110" width="16" height="192" fill="#8B5A2B" opacity="0.55"/>
        <rect x="58" y="298" width="184" height="14" rx="6" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
        <circle cx="72" cy="318" r="8" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
        <circle cx="228" cy="318" r="8" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>

        <!-- dial face -->
        <circle cx="${DIAL_CX}" cy="${DIAL_CY}" r="${DIAL_R + 12}" fill="#5c4a3a"/>
        <circle cx="${DIAL_CX}" cy="${DIAL_CY}" r="${DIAL_R + 6}" fill="#fdfbf5" stroke="#8B5A2B" stroke-width="3"/>

        <!-- the ring turns; the marker above it does not -->
        <g class="hwc-dial" transform="rotate(${rotation.toFixed(2)} ${DIAL_CX} ${DIAL_CY})">
          ${zones}
          ${ticks.join("")}
        </g>

        <circle cx="${DIAL_CX}" cy="${DIAL_CY}" r="${DIAL_R - 38}" fill="#fdfbf5"/>
        <text x="${DIAL_CX}" y="${DIAL_CY + 4}" text-anchor="middle"
              class="hwc-dial-value hwc-status-${status || "unknown"}">${
                hasWeight ? Math.round(grams) : "–"
              }</text>
        <text x="${DIAL_CX}" y="${DIAL_CY + 24}" text-anchor="middle" class="hwc-dial-unit">g</text>

        <!-- fixed marker at the top of the dial -->
        <path d="M${DIAL_CX - 8} ${DIAL_CY - DIAL_R - 10} L${DIAL_CX + 8} ${DIAL_CY - DIAL_R - 10} L${DIAL_CX} ${DIAL_CY - DIAL_R + 6} Z"
              fill="#c0392b" stroke="#7d2519" stroke-width="1.5"/>
      </svg>
    `;
  }

  _render() {
    if (!this._hass || !this._root || !this._config) return;

    const healthScore = this._entity("health_score");
    const weight = this._entity("weight");

    if (!healthScore || !weight) {
      this._errorEl.hidden = false;
      this._errorEl.textContent = t(this._hass, "common.notFound", {
        entity: this._config.entity,
      });
      this._bodyEl.hidden = true;
      return;
    }
    this._errorEl.hidden = true;
    this._bodyEl.hidden = false;

    applyFur(this._root, coatColor(healthScore));

    const title =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._capitalize(this._config.entity.match(ENTITY_PATTERN)[1]);

    const grams = Number(weight.state);
    const hasWeight = !Number.isNaN(grams) && weight.state !== "unknown";
    const limits = this._limits(healthScore);
    // Classified server-side, so the card and the health score can never
    // disagree about whether a hamster is too heavy.
    const status = hasWeight ? healthScore.attributes.weight_status : null;

    const lastWeighed = weight.attributes.last_weighed_at;
    const daysAgo = lastWeighed ? daysBetween(lastWeighed, null) : null;

    this._bannerEl.innerHTML = renderCardHeader({
      logoSvg: LOGO_SCALE,
      title: title.toUpperCase(),
      subtitle: t(this._hass, "weight.subtitle"),
      badgeHtml: hasWeight
        ? `<span class="hf-badge">${fmtNumber(this._hass, grams, 0, "g")}</span>`
        : "",
    });

    this._sceneEl.innerHTML = this._scene(grams, hasWeight, limits, status);

    // The dial already shows the number, so this line says what it means
    // rather than repeating it.
    this._readoutEl.innerHTML = status
      ? `<span class="hwc-verdict hwc-status-${status} hwc-clickable"
               data-entity="${this._entityId("weight")}" tabindex="0" role="button">${t(
                 this._hass,
                 `weight.status.${status}`
               )}</span>`
      : hasWeight
        ? `<span class="hwc-verdict hwc-status-unknown">${t(this._hass, "weight.noBreedRange")}</span>`
        : "";

    // Nothing recorded yet means the +/- buttons would have to climb all
    // the way from zero - roughly a hundred taps for a Syrian hamster.
    // So the first value is typed, and typing stays reachable afterwards.
    const editing = this._editing || !hasWeight;

    if (editing) {
      const min = Number(weight.attributes.min ?? 0);
      const max = Number(weight.attributes.max ?? DEFAULT_DIAL_MAX);
      const step = weight.attributes.step ?? 1;
      // `hass` is reassigned on every state change anywhere in Home
      // Assistant, not just this card's own entities, so _render() runs
      // many times a minute. Rebuilding the input on every one of those
      // yanks focus out from under whatever the user is mid-typing -
      // wiping the digits and, on mobile, dismissing the keyboard. None
      // of that content actually needs to change between keystrokes, so
      // skip the rebuild unless the form would genuinely look different.
      const signature = `${min}:${max}:${step}:${hasWeight}`;
      if (
        this._controlsEl.dataset.hwcMode !== "edit" ||
        this._controlsEl.dataset.hwcSignature !== signature
      ) {
        this._controlsEl.dataset.hwcMode = "edit";
        this._controlsEl.dataset.hwcSignature = signature;
        this._controlsEl.innerHTML = `
          <input class="hwc-input" type="number" inputmode="numeric"
                 min="${min}" max="${max}" step="${step}"
                 value="${hasWeight ? grams : ""}"
                 aria-label="${t(this._hass, "weight.enterWeight")}"
                 placeholder="${min}–${max} g">
          <button class="hwc-step hwc-primary" data-action="save" type="button">
            ${t(this._hass, "weight.save")}
          </button>
          ${
            hasWeight
              ? `<button class="hwc-step hwc-step-big" data-action="cancel" type="button">
                   ${t(this._hass, "weight.cancel")}
                 </button>`
              : ""
          }
        `;
      }
    } else {
      this._controlsEl.dataset.hwcMode = "view";
      const step = Number(this._config.step) || 1;
      this._controlsEl.innerHTML =
        [-step * 5, -step, step, step * 5]
          .map(
            (delta) => `
              <button class="hwc-step${Math.abs(delta) > step ? " hwc-step-big" : ""}"
                      data-step="${delta}" type="button">
                ${delta > 0 ? "+" : "−"}${Math.abs(delta)}
              </button>
            `
          )
          .join("") +
        `<button class="hwc-step hwc-step-big" data-action="edit" type="button"
                 title="${t(this._hass, "weight.typeIt")}"
                 aria-label="${t(this._hass, "weight.typeIt")}">✎</button>`;
    }

    this._noteEl.innerHTML = hasWeight
      ? `<span>${
          daysAgo === null
            ? ""
            : daysAgo === 0
              ? t(this._hass, "weight.weighedToday")
              : t(this._hass, "weight.weighedDaysAgo", { count: daysAgo })
        }${
          lastWeighed
            ? ` <span class="hwc-note-date">(${fmtDate(this._hass, lastWeighed)})</span>`
            : ""
        }</span>`
      : `<span>${t(this._hass, "weight.neverWeighed")}</span>`;
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
}

HamsterWeightCard.styles = `
  ${HEADER_STYLES}

  ha-card {
    padding: 0;
    overflow: hidden;
  }
  .hwc-root {
    --hf-fur: #D48C46;
    --hf-fur-light: #e0a869;
    --hf-fur-dark: #7f5429;
    --hf-belly: #f2ddc4;
  }
  .hwc-banner {
    padding: 14px 16px;
    background: linear-gradient(135deg, #8B5A2B, #C19A6B);
  }
  .hwc-error {
    color: var(--secondary-text-color);
    font-size: 0.9em;
    padding: 16px;
  }
  .hwc-body {
    padding: 6px 16px 18px;
    text-align: center;
  }
  .hwc-svg {
    display: block;
    width: 100%;
    height: auto;
    max-height: 260px;
    margin: 0 auto;
  }
  /* Everything that moves shares one easing, so the beam, the pans and
     the hamster settle together rather than arriving separately. */

  .hwc-empty-pan {
    font-size: 30px;
    font-weight: 800;
    fill: var(--secondary-text-color);
    opacity: 0.6;
  }
  .hwc-tick-label {
    font-size: 11px;
    font-weight: 700;
    fill: #5c4a3a;
  }
  .hwc-zone {
    fill: none;
    stroke-width: 7;
    stroke-linecap: butt;
    opacity: 0.75;
  }
  .hwc-zone-low { stroke: #4EA8DE; }
  .hwc-zone-ok { stroke: #4caf50; }
  .hwc-zone-high { stroke: #e45c5c; }
  .hwc-dial {
    transition: transform 0.8s cubic-bezier(0.32, 1.14, 0.6, 1);
  }
  .hwc-dial-value {
    font-size: 30px;
    font-weight: 900;
    fill: var(--primary-text-color, #212121);
  }
  .hwc-dial-unit {
    font-size: 13px;
    font-weight: 700;
    fill: #8A929A;
  }
  .hwc-status-underweight { fill: #4EA8DE; color: #4EA8DE; }
  .hwc-status-normal { fill: #4caf50; color: #4caf50; }
  .hwc-status-overweight { fill: #e45c5c; color: #e45c5c; }
  .hwc-status-unknown { color: var(--secondary-text-color); }
  .hwc-verdict {
    display: inline-block;
    margin-top: 2px;
    font-size: 1.05em;
    font-weight: 800;
  }
  .hwc-clickable {
    cursor: pointer;
  }
  .hwc-clickable:focus-visible {
    outline: 2px solid var(--primary-color, #03a9f4);
    outline-offset: 3px;
    border-radius: 8px;
  }
  .hwc-controls {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-top: 12px;
  }
  .hwc-step {
    min-width: 56px;
    padding: 10px 12px;
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 12px;
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.1));
    color: var(--primary-text-color);
    font-family: inherit;
    font-size: 0.95em;
    font-weight: 700;
    cursor: pointer;
    transition: background-color 0.15s ease, transform 0.1s ease;
  }
  .hwc-step:hover,
  .hwc-step:focus-visible {
    background: var(--primary-color, #03a9f4);
    color: #fff;
    outline: none;
  }
  .hwc-step:active {
    transform: translateY(1px);
  }
  .hwc-step-big {
    opacity: 0.85;
    font-size: 0.85em;
  }
  .hwc-primary {
    background: var(--primary-color, #03a9f4);
    border-color: var(--primary-color, #03a9f4);
    color: #fff;
  }
  .hwc-input {
    width: 110px;
    padding: 10px 12px;
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 12px;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    font-family: inherit;
    font-size: 1.05em;
    font-weight: 700;
    text-align: center;
  }
  .hwc-input:focus {
    outline: 2px solid var(--primary-color, #03a9f4);
    outline-offset: 1px;
  }
  /* The spinners duplicate the +/- buttons and only make the field
     narrower, so they go. */
  .hwc-input::-webkit-outer-spin-button,
  .hwc-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .hwc-input {
    -moz-appearance: textfield;
    appearance: textfield;
  }
  .hwc-note {
    margin-top: 12px;
    font-size: 0.82em;
    color: var(--secondary-text-color);
  }
  .hwc-note-date {
    opacity: 0.75;
  }

  @media (prefers-reduced-motion: reduce) {
    .hwc-dial {
      transition: none;
    }
  }

  @media (max-width: 400px) {
    .hwc-step {
      min-width: 46px;
      padding: 9px 8px;
    }
    .hwc-verdict {
      font-size: 0.95em;
    }
  }
`;

customElements.define("hamster-weight-card", HamsterWeightCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-weight-card",
  name: t(null, "weight.pickerName"),
  description: t(null, "weight.pickerDescription"),
});

const WEIGHT_EDITOR_SCHEMA = [
  {
    name: "entity",
    required: true,
    selector: { entity: { filter: { integration: "hamster_fitness", domain: "sensor" } } },
  },
  { name: "title", selector: { text: {} } },
  { name: "step", selector: { number: { min: 1, max: 50, step: 1, mode: "box" } } },
];

const WEIGHT_EDITOR_LABELS = {
  entity: "common.entityPicker",
  title: "common.optionalTitle",
  step: "weight.step",
};

class HamsterWeightCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
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
      this._form.computeLabel = (schema) =>
        WEIGHT_EDITOR_LABELS[schema.name]
          ? t(this._hass, WEIGHT_EDITOR_LABELS[schema.name])
          : schema.name;
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
    this._form.schema = WEIGHT_EDITOR_SCHEMA;
    this._form.data = this._config;
  }
}

customElements.define("hamster-weight-card-editor", HamsterWeightCardEditor);
