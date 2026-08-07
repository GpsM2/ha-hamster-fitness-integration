/**
 * Hamster Fitness: Weighing
 *
 * An input for `number.<hamster>_weight` that looks like something you'd
 * want to use: the hamster sits on an old-fashioned two-pan balance,
 * counterweights stack up on the other pan as the number rises, and the
 * hamster itself gets visibly rounder. The point is that a weight in
 * grams means very little on its own - seeing the balance tip tells you
 * more at a glance than "97".
 *
 * Weighing is the one thing this integration cannot measure by itself,
 * so it has always been a bare number box behind a more-info dialog.
 *
 * Config:
 *   type: custom:hamster-weight-card
 *   entity: sensor.hamster_taco_health_score   # required - same as the other cards
 *   title: Taco                                 # optional - defaults to the device name
 *   scale_min: 20                               # optional - grams, low end of the drawn scale
 *   scale_max: 200                              # optional - grams, high end
 *   step: 1                                     # optional - grams per tap
 *
 * scale_min/scale_max only drive the illustration, never validation -
 * the number entity's own limits still apply. Defaults span a dwarf
 * hamster to a large Syrian; narrow them for a more expressive tilt.
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
} from "./hamster-fitness-shared.js?v=5";

const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

const DEFAULTS = {
  scale_min: 20,
  scale_max: 200,
  step: 1,
};

// How many counterweight discs the right-hand pan can stack. Enough to
// read as "more" or "fewer" at a glance without turning into a tower.
const MAX_WEIGHTS = 6;
// How far either pan may travel, in SVG units.
const MAX_PAN_TRAVEL = 26;

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
    const max = Number(weight.attributes.max ?? 2000);
    const next = Math.min(max, Math.max(min, base + delta));
    if (next === base) return;

    this._hass.callService("number", "set_value", {
      entity_id: this._entityId("weight"),
      value: next,
    });
  }

  /** 0..1 position of `grams` within the drawn scale. */
  _fraction(grams) {
    const min = Number(this._config.scale_min);
    const max = Number(this._config.scale_max);
    if (!(max > min) || grams === null || Number.isNaN(grams)) return 0.5;
    return Math.min(1, Math.max(0, (grams - min) / (max - min)));
  }

  /**
   * The balance itself. `fraction` tips the beam and decides how many
   * counterweights the right pan carries and how round the hamster is.
   */
  _scene(fraction, hasWeight) {
    // Left pan (the hamster) sinks as the weight rises; the beam follows.
    const travel = (fraction - 0.5) * 2 * MAX_PAN_TRAVEL;
    const tilt = (fraction - 0.5) * 2 * 9; // degrees
    const leftY = travel;
    const rightY = -travel;

    // No weight recorded means an empty scale, not a half-loaded one -
    // the beam rests level and both pans stay bare.
    const discs = hasWeight ? Math.round(fraction * MAX_WEIGHTS) : 0;
    const counterweights = Array.from({ length: discs }, (_, index) => {
      const width = 30 - index * 3;
      return `<rect x="${215 - width / 2}" y="${150 - index * 9}" width="${width}" height="8"
                    rx="3" fill="#8A929A" stroke="#5c6570" stroke-width="1.5"/>`;
    }).join("");

    // Body swells with weight - the most immediately readable cue.
    const bodyRx = 30 + fraction * 12;
    const bodyRy = 22 + fraction * 10;

    return `
      <svg class="hwc-svg" viewBox="0 0 300 230" aria-hidden="true">
        <!-- stand -->
        <rect x="130" y="196" width="40" height="8" rx="4" fill="#B8860B"/>
        <rect x="146" y="70" width="8" height="128" fill="#C19A6B"/>
        <circle cx="150" cy="66" r="6" fill="#FFD166" stroke="#B8860B" stroke-width="2"/>

        <!-- beam -->
        <g transform="rotate(${tilt.toFixed(2)} 150 70)" class="hwc-beam">
          <rect x="60" y="66" width="180" height="7" rx="3.5" fill="#FFD166" stroke="#B8860B" stroke-width="2"/>
          <circle cx="85" cy="70" r="4" fill="#B8860B"/>
          <circle cx="215" cy="70" r="4" fill="#B8860B"/>
        </g>

        <!-- left pan: the hamster -->
        <g class="hwc-pan" transform="translate(0 ${leftY.toFixed(2)})">
          <path d="M85 74 L62 128 M85 74 L108 128" stroke="#B8860B" stroke-width="2" fill="none"/>
          <path d="M55 128 a30 12 0 0 0 60 0 Z" fill="#FFD166" stroke="#B8860B" stroke-width="2"/>
          ${
            hasWeight
              ? `<g class="hwc-hamster">
                   <ellipse cx="85" cy="${118 - bodyRy * 0.35}" rx="${bodyRx.toFixed(1)}" ry="${bodyRy.toFixed(1)}"
                            fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
                   <ellipse cx="85" cy="${122 - bodyRy * 0.2}" rx="${(bodyRx * 0.6).toFixed(1)}" ry="${(bodyRy * 0.55).toFixed(1)}"
                            fill="var(--hf-belly)" opacity="0.75"/>
                   <circle cx="${(85 + bodyRx * 0.62).toFixed(1)}" cy="${(104 - bodyRy * 0.5).toFixed(1)}" r="14"
                           fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
                   <circle cx="${(85 + bodyRx * 0.42).toFixed(1)}" cy="${(93 - bodyRy * 0.5).toFixed(1)}" r="5"
                           fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2"/>
                   <circle cx="${(85 + bodyRx * 0.86).toFixed(1)}" cy="${(102 - bodyRy * 0.5).toFixed(1)}" r="2.2" fill="#3a2a1a"/>
                   <ellipse cx="${(85 + bodyRx * 1.02).toFixed(1)}" cy="${(107 - bodyRy * 0.5).toFixed(1)}" rx="4" ry="3" fill="#f4d9c6"/>
                 </g>`
              : `<text class="hwc-empty-pan" x="85" y="118" text-anchor="middle">?</text>`
          }
        </g>

        <!-- right pan: counterweights -->
        <g class="hwc-pan" transform="translate(0 ${rightY.toFixed(2)})">
          <path d="M215 74 L192 128 M215 74 L238 128" stroke="#B8860B" stroke-width="2" fill="none"/>
          <path d="M185 128 a30 12 0 0 0 60 0 Z" fill="#FFD166" stroke="#B8860B" stroke-width="2"/>
          <g transform="translate(0 -28)">${counterweights}</g>
        </g>
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
    const fraction = this._fraction(hasWeight ? grams : null);

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

    this._sceneEl.innerHTML = this._scene(fraction, hasWeight);

    this._readoutEl.innerHTML = `
      <span class="hwc-value hwc-clickable" data-entity="${this._entityId("weight")}"
            tabindex="0" role="button">${
              hasWeight ? fmtNumber(this._hass, grams, 0, "g") : "–"
            }</span>
    `;

    const step = Number(this._config.step) || 1;
    const buttons = [-step * 5, -step, step, step * 5]
      .map(
        (delta) => `
          <button class="hwc-step${Math.abs(delta) > step ? " hwc-step-big" : ""}"
                  data-step="${delta}" type="button">
            ${delta > 0 ? "+" : "−"}${Math.abs(delta)}
          </button>
        `
      )
      .join("");
    this._controlsEl.innerHTML = buttons;

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
  .hwc-beam,
  .hwc-pan,
  .hwc-hamster ellipse,
  .hwc-hamster circle {
    transition: transform 0.55s cubic-bezier(0.34, 1.2, 0.64, 1),
                rx 0.55s ease, ry 0.55s ease, cx 0.55s ease, cy 0.55s ease;
  }
  .hwc-empty-pan {
    font-size: 30px;
    font-weight: 800;
    fill: var(--secondary-text-color);
    opacity: 0.6;
  }
  .hwc-value {
    font-size: 2.4em;
    font-weight: 900;
    color: var(--primary-text-color);
    line-height: 1;
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
  .hwc-note {
    margin-top: 12px;
    font-size: 0.82em;
    color: var(--secondary-text-color);
  }
  .hwc-note-date {
    opacity: 0.75;
  }

  @media (prefers-reduced-motion: reduce) {
    .hwc-beam,
    .hwc-pan,
    .hwc-hamster ellipse,
    .hwc-hamster circle {
      transition: none;
    }
  }

  @media (max-width: 400px) {
    .hwc-step {
      min-width: 46px;
      padding: 9px 8px;
    }
    .hwc-value {
      font-size: 2em;
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
  { name: "scale_min", selector: { number: { min: 0, max: 500, step: 1, mode: "box" } } },
  { name: "scale_max", selector: { number: { min: 1, max: 2000, step: 1, mode: "box" } } },
  { name: "step", selector: { number: { min: 1, max: 50, step: 1, mode: "box" } } },
];

const WEIGHT_EDITOR_LABELS = {
  entity: "common.entityPicker",
  title: "common.optionalTitle",
  scale_min: "weight.scaleMin",
  scale_max: "weight.scaleMax",
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
