/**
 * Hamster Fitness: Day & Night Card
 *
 * Bundled with the Hamster Fitness integration, auto-registered as a
 * Lovelace resource (see frontend/__init__.py) - no HACS frontend install
 * needed. One big illustrated scene: the hamster runs in its wheel
 * (animated, speed-coupled) while it is actually active, or sleeps in its
 * nest while it is not - layered on a sun-position-driven sky. The
 * readings sit as pill-shaped chips inside that scene rather than in a
 * separate stats block underneath.
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
 *   show_light: true
 *
 * Sibling entities (night_active_duration, day_rest_duration,
 * current_speed, night_distance, humidity, light_automation, ...) are
 * resolved by translation_key - see hamster-fitness-shared.js.
 *
 * Rendering note: the DOM is built once and then patched in place. An
 * earlier version rebuilt innerHTML on every `hass` update, which
 * restarted the wheel's CSS animation from 0deg several times a second -
 * that is what made it stutter. Only the chip block, which has no
 * animation, is still re-rendered wholesale.
 */

import {
  DEFAULT_FUR,
  HEADER_STYLES,
  applyFur,
  coatColor,
  deviceDisplayName,
  fmtDuration,
  fmtNumber,
  fmtTime,
  renderCardHeader,
  siblingEntityId,
  t,
} from "./hamster-fitness-shared.js?v=11";

const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

// Seconds for one full revolution, at the fastest/slowest speed we still
// animate. Below STOP_SPEED_KMH the wheel is parked instead of crawling.
const MIN_SPIN_S = 0.45;
const MAX_SPIN_S = 5;
const MAX_SPEED_KMH = 20;
const STOP_SPEED_KMH = 0.15;
// Reference length of one revolution. The wheel always runs at exactly
// this duration and is sped up or slowed down via playbackRate instead -
// see _applyWheelSpin() for why that matters.
const SPIN_BASE_MS = 2000;

const NIGHT_GRADIENT = ["#0B132B", "#1C2541"];
const DAY_GRADIENT_HORIZON = ["#F4A261", "#E9C46A"];
const DAY_GRADIENT_MIDDAY = ["#4EA8DE", "#90E0EF"];
const DAY_ELEVATION_FULL_AT = 30; // degrees - gradient stops shifting past this

// Ambient-light thresholds, only used once an illuminance sensor is
// configured (coordinator.py's ambient_light_lx attribute; None means
// "keep using sun.sun", the card's existing behaviour). At/below
// AMBIENT_NIGHT_LX counts as night; at/above AMBIENT_DAY_LX the gradient
// is fully "day". Deliberately a plain two-stop fade straight to
// DAY_GRADIENT_MIDDAY, not a three-stop one through DAY_GRADIENT_HORIZON
// like the sun-elevation path: lux says how bright the room is, not
// where the sun sits, so there is no honest "just past the horizon" hue
// to interpolate through.
const AMBIENT_NIGHT_LX = 5;
const AMBIENT_DAY_LX = 150;
// How bright the lux reading may push the sky once the real sun is below
// the horizon. A lit room at 10pm is still a lit room - but rendering it
// as full midday reads as broken, however accurate the lux value is. This
// caps it at dusk instead: clearly still evening, just not pitch black.
const AMBIENT_NIGHT_CEILING = 0.3;

/**
 * Every weather state Home Assistant defines, mapped to what the scene
 * should show. Covered individually rather than lumped into a few
 * buckets - "pouring" really should look wetter than "rainy", and
 * "hail" isn't snow.
 *
 * Each entry picks: a precipitation type (with how heavy), how much
 * cloud drifts past, whether lightning flashes, and how much the sky is
 * dimmed. `clear` states draw nothing at all, which is also the fallback
 * for any state a future Home Assistant might add.
 */
const WEATHER_SCENES = {
  "clear-night": { clouds: 0, dim: 0 },
  sunny: { clouds: 0, dim: 0 },
  partlycloudy: { clouds: 2, dim: 0.05 },
  cloudy: { clouds: 4, dim: 0.16 },
  fog: { clouds: 0, dim: 0.3, fog: true },
  windy: { clouds: 2, dim: 0.05, wind: true },
  "windy-variant": { clouds: 3, dim: 0.1, wind: true },
  rainy: { clouds: 4, dim: 0.24, drops: 26, dropKind: "rain" },
  pouring: { clouds: 5, dim: 0.34, drops: 54, dropKind: "rain" },
  snowy: { clouds: 4, dim: 0.2, drops: 30, dropKind: "snow" },
  "snowy-rainy": { clouds: 4, dim: 0.26, drops: 34, dropKind: "sleet" },
  hail: { clouds: 5, dim: 0.28, drops: 30, dropKind: "hail" },
  lightning: { clouds: 4, dim: 0.3, lightning: true },
  "lightning-rainy": {
    clouds: 5,
    dim: 0.36,
    drops: 46,
    dropKind: "rain",
    lightning: true,
  },
  // "Exceptional" means severe weather of an unspecified kind, so it
  // gets the most dramatic treatment rather than a guess at which.
  exceptional: { clouds: 5, dim: 0.4, lightning: true, wind: true },
};

/**
 * Home Assistant's eight moon-phase states (the built-in Moon
 * integration), as an illuminated fraction plus which limb is lit.
 *
 * `lit` is the fraction of the disc that is bright; `waxing` says whether
 * that bright part is on the right (growing towards full) or the left
 * (shrinking towards new). Both are what _moonPath() needs to draw the
 * terminator - the curved edge between light and shadow.
 *
 * Orientation is the northern-hemisphere one, matching the fixed crescent
 * this card has always drawn. Below the equator the moon appears mirrored;
 * Home Assistant's sensor doesn't report that, and guessing it from the
 * configured latitude is a separate question from reading the phase.
 */
const MOON_PHASES = {
  new_moon: { lit: 0, waxing: true },
  waxing_crescent: { lit: 0.25, waxing: true },
  first_quarter: { lit: 0.5, waxing: true },
  waxing_gibbous: { lit: 0.75, waxing: true },
  full_moon: { lit: 1, waxing: true },
  waning_gibbous: { lit: 0.75, waxing: false },
  last_quarter: { lit: 0.5, waxing: false },
  waning_crescent: { lit: 0.25, waxing: false },
};

// Centre and radius of the moon disc, matched to the fixed crescent this
// card has always drawn so every phase lands in exactly the same spot.
// Measured from that path's own bounding box rather than read off its
// "M272 30": in an arc-based path that is the starting point on the rim,
// not the centre - the disc actually sits 17 units lower.
const MOON_CX = 272.3;
const MOON_CY = 47;
const MOON_R = 17;

/**
 * The night sky's stars: fixed positions, each with its own brightness
 * and its own twinkle timing.
 *
 * Positions are hardcoded rather than scattered randomly so they don't
 * jump to new spots whenever the sky is redrawn. The durations are
 * deliberately unrelated to each other (no common divisor to speak of),
 * so the eight never drift into blinking in unison, and the negative
 * delays start each one part-way through its cycle - otherwise the whole
 * sky would visibly fade up together the moment the card renders.
 */
const STARS = [
  { cx: 26, cy: 30, r: 1.7, max: 0.85, dur: 4.2, delay: -0.4 },
  { cx: 64, cy: 16, r: 1.1, max: 0.6, dur: 5.6, delay: -2.9 },
  { cx: 104, cy: 34, r: 1.5, max: 0.75, dur: 3.8, delay: -1.6 },
  { cx: 148, cy: 14, r: 1.0, max: 0.5, dur: 6.1, delay: -4.3 },
  { cx: 186, cy: 30, r: 1.3, max: 0.7, dur: 4.7, delay: -0.9 },
  { cx: 44, cy: 52, r: 1.0, max: 0.5, dur: 5.2, delay: -3.5 },
  { cx: 92, cy: 10, r: 1.2, max: 0.6, dur: 3.4, delay: -2.1 },
  { cx: 222, cy: 48, r: 1.2, max: 0.55, dur: 5.9, delay: -1.2 },
];

const STATUS_ONLINE = { key: "common.online", color: "#06D6A0" };
const STATUS_OFFLINE = { key: "common.offline", color: "#EF476F" };
const STATUS_UNAVAILABLE = { key: "common.unavailable", color: "#8D99AE" };

const DEFAULT_TOGGLES = {
  show_speed: true,
  show_distance: true,
  show_active_duration: true,
  show_rest_duration: true,
  show_climate: true,
  show_light: true,
};

// Hamster with dumbbells, side view - compact version of
// design/hamster-dumbbell-logo.svg, for the card header. Same
// illustration family as the main card's headband-hamster logo.
const LOGO_DUMBBELL_SVG = `
<svg viewBox="0 0 200 200" width="34" height="34" aria-hidden="true">
  <ellipse cx="70" cy="150" rx="13" ry="9" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="3" transform="rotate(15 70 150)"/>
  <ellipse cx="128" cy="150" rx="13" ry="9" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="3" transform="rotate(-15 128 150)"/>
  <circle cx="52" cy="122" r="8" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
  <ellipse cx="100" cy="122" rx="48" ry="38" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
  <circle cx="112" cy="70" r="30" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
  <circle cx="90" cy="48" r="9" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
  <circle cx="128" cy="46" r="9" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
  <circle cx="122" cy="66" r="4.5" fill="#3a2a1a"/>
  <ellipse cx="134" cy="76" rx="6.5" ry="5" fill="#f4d9c6" stroke="var(--hf-fur-dark)" stroke-width="1.5"/>
  <circle cx="137" cy="76" r="2" fill="#5c4030"/>
  <path d="M138 108 Q158 96 168 74" fill="none" stroke="var(--hf-fur-light)" stroke-width="14" stroke-linecap="round"/>
  <path d="M78 132 Q66 148 60 162" fill="none" stroke="var(--hf-fur)" stroke-width="13" stroke-linecap="round"/>
  <g transform="rotate(-28 168 74)">
    <rect x="150" y="70" width="36" height="8" rx="4" fill="#5c4a3a"/>
    <rect x="144" y="62" width="12" height="24" rx="4" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
    <rect x="180" y="62" width="12" height="24" rx="4" fill="#8B5A2B" stroke="#5c4a3a" stroke-width="2"/>
  </g>
</svg>
`;

// The one patch of sky nothing else covers: the frosted header strip
// runs across the top, the reading chips down the right. Shifting the
// sun and the moon down and left puts them over open background instead
// of half-hidden behind either.
// Applied to an OUTER group, never to .hdn-sun itself: that element's
// pulse animation sets `transform` in CSS, and a CSS transform replaces
// the SVG presentation attribute outright rather than composing with it.
const CELESTIAL_X = -198;
const CELESTIAL_Y = 46;
const CELESTIAL_OFFSET = `translate(${CELESTIAL_X}, ${CELESTIAL_Y})`;

// The sun's height tracks sun.sun's elevation: low near sunrise and
// sunset, high around solar noon. Only the sun moves - the moon keeps the
// fixed offset above, since its own elevation isn't something sun.sun
// reports.
//
// SUN_ELEVATION_ZENITH_AT is deliberately larger than
// DAY_ELEVATION_FULL_AT (which fades the sky's colour and saturates much
// earlier): the point here is visible travel across the day. It also
// means the sun honestly stays low all day in midwinter at high
// latitudes, where it never climbs anywhere near 50 degrees.
// The travel range is anchored so that solar noon reproduces the position
// the sun always had, and low elevations sink it from there - rather than
// lifting it above where the layout was ever designed for. Measured
// against the real card: from y=54 down the disc clears the frosted
// header strip completely, and at the long-standing y=46 only about 5% of
// it sits behind that (translucent) strip, which is what the card has
// always looked like. Pushing the zenith higher hid the disc behind the
// header outright, which looked broken rather than sunny.
const SUN_ELEVATION_ZENITH_AT = 50;
const SUN_Y_HORIZON = 76;
const SUN_Y_ZENITH = CELESTIAL_Y;

const ICONS = {
  speed: "M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2Zm1 4v7h-2V6h2Z",
  distance:
    "M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5Z",
  timer:
    "M15 1H9v2h6V1Zm-4 13h2V8h-2v6Zm8.03-6.61 1.42-1.42a11 11 0 0 0-1.41-1.41l-1.42 1.42A9 9 0 1 0 21 13a8.94 8.94 0 0 0-1.97-5.61Z",
  climate:
    "M15 13V5a3 3 0 0 0-6 0v8a5 5 0 1 0 6 0Zm-3-9a1 1 0 0 1 1 1v3h-2V5a1 1 0 0 1 1-1Z",
  light:
    "M9 21h6v-1H9v1Zm3-19a7 7 0 0 0-4 12.74V17h8v-2.26A7 7 0 0 0 12 2Z",
};

function hexToRgb(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
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
        t(null, "common.needEntity", { card: "hamster-day-night-card" })
      );
    }
    if (!config.entity.match(ENTITY_PATTERN)) {
      throw new Error(
        t(null, "common.wrongEntity", { card: "hamster-day-night-card" })
      );
    }
    this._config = { ...DEFAULT_TOGGLES, ...config };
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
    return document.createElement("hamster-day-night-card-editor");
  }

  static getStubConfig(hass, entities) {
    const match = (entities || []).find((id) => ENTITY_PATTERN.test(id));
    return { entity: match || "sensor.hamster_taco_health_score", ...DEFAULT_TOGGLES };
  }

  /**
   * Builds the persistent DOM exactly once. Everything the render pass
   * touches afterwards is either a CSS custom property or one of the
   * cached child nodes below - crucially never the wheel's own element,
   * whose running animation must not be interrupted.
   */
  _ensureSkeleton() {
    if (this._root) return;

    this.innerHTML = `
      <ha-card>
        <div class="hdn-root">
          <div class="hdn-error" hidden></div>
          <div class="hdn-sky">
            <div class="hdn-decor"></div>
            <div class="hdn-weather"></div>
            ${renderCardHeader({
              logoSvg: LOGO_DUMBBELL_SVG,
              title: "",
              subtitle: t(null, "dayNight.subtitle"),
              badgeHtml: `<span class="hf-badge">
                <span class="hf-badge-dot"></span>
                <span class="hdn-status-label"></span>
              </span>`,
            })}
            <div class="hdn-body">
              <div class="hdn-scene"></div>
              <div class="hdn-chips"></div>
            </div>
          </div>
        </div>
      </ha-card>
      <style>${HamsterDayNightCard.styles}</style>
    `;

    this._root = this.querySelector(".hdn-root");
    this._errorEl = this.querySelector(".hdn-error");
    this._skyEl = this.querySelector(".hdn-sky");
    this._decorEl = this.querySelector(".hdn-decor");
    this._weatherEl = this.querySelector(".hdn-weather");
    this._titleEl = this.querySelector(".hf-title");
    this._statusDotEl = this.querySelector(".hf-badge-dot");
    this._statusLabelEl = this.querySelector(".hdn-status-label");
    this._sceneEl = this.querySelector(".hdn-scene");
    this._chipsEl = this.querySelector(".hdn-chips");

    this._sceneMode = null;
    this._decorKey = null;

    const openMoreInfo = (target) => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: target.dataset.entity },
          bubbles: true,
          composed: true,
        })
      );
    };

    this._root.addEventListener("click", (ev) => {
      const pauseButton = ev.target.closest("[data-action='pause-light']");
      if (pauseButton) {
        this._pauseLight(pauseButton.dataset.switch);
        return;
      }
      // Order matters: the light chip's label carries data-entity and
      // sits inside the chip body that carries data-action. Matching the
      // label first is what keeps it opening more-info instead of
      // flipping the lamp.
      const target = ev.target.closest("[data-entity]");
      if (target) {
        openMoreInfo(target);
        return;
      }
      const lightToggle = ev.target.closest("[data-action='toggle-light']");
      if (lightToggle) this._toggleLight(lightToggle.dataset.light);
    });
    this._root.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      const pauseButton = ev.target.closest("[data-action='pause-light']");
      if (pauseButton) {
        ev.preventDefault();
        this._pauseLight(pauseButton.dataset.switch);
        return;
      }
      const target = ev.target.closest("[data-entity]");
      if (target) {
        ev.preventDefault();
        openMoreInfo(target);
        return;
      }
      const lightToggle = ev.target.closest("[data-action='toggle-light']");
      if (!lightToggle) return;
      ev.preventDefault();
      this._toggleLight(lightToggle.dataset.light);
    });
  }

  /**
   * Toggles the cage light itself, not the automation switch.
   *
   * The automation decides when the light *should* be on; this is the
   * manual override you reach for when you just want light in the cage
   * now. Toggling the automation instead would silently change the rule
   * rather than the lamp.
   */
  _toggleLight(lightEntityId) {
    if (!this._hass || !lightEntityId) return;
    const light = this._hass.states[lightEntityId];
    if (!light) return;
    this._hass.callService(
      "light",
      light.state === "on" ? "turn_off" : "turn_on",
      { entity_id: lightEntityId }
    );
  }

  _pauseLight(switchEntityId) {
    if (!this._hass || !switchEntityId) return;
    this._hass.callService(
      "hamster_fitness",
      "pause_light_automation",
      {},
      { entity_id: switchEntityId }
    );
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
   * The room's actual brightness when an illuminance sensor is
   * configured (see coordinator.py's ambient_light_lx), or null to fall
   * back to sun.sun. null both when nothing was configured and when a
   * sensor was configured but has no usable reading yet - either way
   * there is nothing better than the sun to go on.
   */
  _ambientLightLx(healthScore) {
    const raw = healthScore.attributes.ambient_light_lx;
    if (raw === null || raw === undefined) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }

  /**
   * Whether sun.sun reports the sun below the horizon, or null when there
   * is no sun entity to ask - Home Assistant can run without one, and
   * "no answer" has to stay distinguishable from "no, it's up".
   */
  _sunBelowHorizon() {
    const sun = this._hass.states["sun.sun"];
    if (!sun) return null;
    return sun.state === "below_horizon";
  }

  /** sun.sun's elevation in degrees, or null if unavailable. */
  _sunElevation() {
    const sun = this._hass.states["sun.sun"];
    const elevation = Number(sun && sun.attributes && sun.attributes.elevation);
    return Number.isFinite(elevation) ? elevation : null;
  }

  /**
   * Where the sun sits inside the decoration viewBox, following the real
   * one's elevation. Falls back to the fixed offset (which is also where
   * the moon always sits) when there is no elevation to read.
   */
  _sunTransform() {
    const elevation = this._sunElevation();
    if (elevation === null) return CELESTIAL_OFFSET;
    const t = Math.min(1, Math.max(0, elevation / SUN_ELEVATION_ZENITH_AT));
    const y = SUN_Y_HORIZON + (SUN_Y_ZENITH - SUN_Y_HORIZON) * t;
    return `translate(${CELESTIAL_X}, ${y.toFixed(1)})`;
  }

  _backgroundGradient(ambientLx) {
    if (ambientLx !== null) {
      let t = Math.min(
        1,
        Math.max(0, (ambientLx - AMBIENT_NIGHT_LX) / (AMBIENT_DAY_LX - AMBIENT_NIGHT_LX))
      );
      // The real sun outranks the lux reading: once it has set, no amount
      // of room light may render the sky as daytime.
      if (this._sunBelowHorizon()) t = Math.min(t, AMBIENT_NIGHT_CEILING);
      const from = lerpColor(NIGHT_GRADIENT[0], DAY_GRADIENT_MIDDAY[0], t);
      const to = lerpColor(NIGHT_GRADIENT[1], DAY_GRADIENT_MIDDAY[1], t);
      return `linear-gradient(180deg, ${from}, ${to})`;
    }

    const sun = this._hass.states["sun.sun"];
    if (!sun || sun.state === "below_horizon") {
      return `linear-gradient(180deg, ${NIGHT_GRADIENT[0]}, ${NIGHT_GRADIENT[1]})`;
    }
    const elevation = this._sunElevation();
    const t =
      elevation === null
        ? 1
        : Math.min(1, Math.max(0, elevation / DAY_ELEVATION_FULL_AT));
    const from = lerpColor(DAY_GRADIENT_HORIZON[0], DAY_GRADIENT_MIDDAY[0], t);
    const to = lerpColor(DAY_GRADIENT_HORIZON[1], DAY_GRADIENT_MIDDAY[1], t);
    return `linear-gradient(180deg, ${from}, ${to})`;
  }

  /**
   * The current weather scene, or null to draw no overlay at all.
   *
   * Reads the weather entity chosen during setup (published as an
   * attribute by the coordinator, the same way the climate chip gets its
   * thermometer). No entity, an unavailable one, or a state Home
   * Assistant adds in future that this doesn't know about, all mean "no
   * overlay" rather than a guess.
   */
  _weatherScene(healthScore) {
    const entityId = healthScore.attributes.weather_entity;
    if (!entityId) return null;
    const state = this._hass.states[entityId];
    if (!state) return null;
    return WEATHER_SCENES[state.state] || null;
  }

  /**
   * Builds the overlay markup for one weather scene.
   *
   * Deliberately rebuilt only when the weather actually changes (see
   * _weatherKey in _render): every element here is CSS-animated, and
   * re-rendering identical markup would restart all of it mid-drift -
   * the same mistake that once made the wheel stutter.
   */
  _weatherOverlay(scene) {
    if (!scene) return "";

    // Deterministic pseudo-random placement: a fixed seed keeps drops
    // and clouds in the same spots between renders, so nothing visibly
    // jumps when an unrelated attribute updates.
    let seed = 7;
    const rand = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };

    const clouds = Array.from({ length: scene.clouds || 0 }, (_, i) => {
      const top = 6 + rand() * 44;
      const scale = 0.55 + rand() * 0.75;
      const duration = (scene.wind ? 14 : 38) + rand() * 16;
      const delay = -rand() * duration;
      return `
        <div class="hdn-cloud" style="
          top: ${top.toFixed(1)}%;
          --s: ${scale.toFixed(2)};
          animation-duration: ${duration.toFixed(1)}s;
          animation-delay: ${delay.toFixed(1)}s;
        "></div>`;
    }).join("");

    const drops = Array.from({ length: scene.drops || 0 }, () => {
      const left = rand() * 100;
      const duration = (scene.dropKind === "snow" ? 4.5 : 1.1) + rand() * 0.9;
      const delay = -rand() * duration;
      return `
        <div class="hdn-drop hdn-drop-${scene.dropKind}" style="
          left: ${left.toFixed(1)}%;
          animation-duration: ${duration.toFixed(2)}s;
          animation-delay: ${delay.toFixed(2)}s;
        "></div>`;
    }).join("");

    return `
      ${scene.dim ? `<div class="hdn-weather-dim" style="opacity: ${scene.dim}"></div>` : ""}
      ${scene.fog ? `<div class="hdn-fog"></div>` : ""}
      ${clouds}
      ${drops}
      ${scene.lightning ? `<div class="hdn-lightning"></div>` : ""}
    `;
  }

  /**
   * Night decides which sky decoration and scene are drawn.
   *
   * The real sun wins outright once it has set: a lit room at 10pm used
   * to keep the sun icon in the sky, which reads as broken however
   * accurate the lux reading is. While the sun is up, the lux sensor
   * still decides - that is the whole point of configuring one, so a
   * covered or blacked-out cage reads as night even at noon.
   */
  _isNight(ambientLx) {
    const belowHorizon = this._sunBelowHorizon();
    if (belowHorizon) return true;
    if (ambientLx !== null) return ambientLx <= AMBIENT_NIGHT_LX;
    // No lux sensor and no sun entity either: nothing says otherwise, so
    // keep the card's long-standing "assume night" fallback.
    return belowHorizon === null;
  }

  /**
   * Seconds per revolution for the current speed, or null when the wheel
   * should be standing still. Returning null (rather than a very long
   * duration) is what lets a hamster pause mid-session - the activity
   * sensor still counts, but the wheel visibly stops.
   */
  _spinDurationS(currentSpeed) {
    const speed = currentSpeed ? Number(currentSpeed.state) : NaN;
    if (!Number.isFinite(speed) || speed <= STOP_SPEED_KMH) return null;
    const clamped = Math.min(speed, MAX_SPEED_KMH);
    const raw = (MIN_SPIN_S * MAX_SPEED_KMH) / clamped;
    return Math.min(MAX_SPIN_S, Math.max(MIN_SPIN_S, raw));
  }

  /**
   * Spins the wheel at `spinSeconds` per revolution, or parks it when
   * that is null.
   *
   * Uses the Web Animations API rather than a CSS animation on purpose.
   * A CSS animation whose `animation-duration` is rewritten restarts from
   * 0deg - and the speed sensor changes constantly, so the wheel visibly
   * snapped back on nearly every update. `playbackRate` retimes the very
   * same running animation instead, keeping the wheel exactly where it
   * is, which is what makes it track the real speed smoothly.
   */
  _applyWheelSpin(spinSeconds) {
    const el = this._wheelEl;
    if (!el || typeof el.animate !== "function") return;

    if (!this._wheelAnim) {
      const reduceMotion =
        window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduceMotion) return;
      this._wheelAnim = el.animate(
        [{ transform: "rotate(0deg)" }, { transform: "rotate(360deg)" }],
        { duration: SPIN_BASE_MS, iterations: Infinity, easing: "linear" }
      );
    }

    if (spinSeconds === null) {
      // Standing still mid-session: the hamster is having a breather, but
      // the activity sensor is still counting the session.
      this._wheelAnim.pause();
      this._sceneEl.classList.add("hdn-scene-idle");
      return;
    }
    this._wheelAnim.playbackRate = SPIN_BASE_MS / (spinSeconds * 1000);
    this._wheelAnim.play();
    this._sceneEl.classList.remove("hdn-scene-idle");
  }

  _connectionStatus(currentSpeedEntityId) {
    const state = this._hass.states[currentSpeedEntityId];
    if (!state) return STATUS_ONLINE; // no speed sensor configured - no reliable signal either way
    if (state.state === "unavailable") return STATUS_OFFLINE;
    if (state.state === "unknown") return STATUS_UNAVAILABLE;
    return STATUS_ONLINE;
  }

  _wheelScene() {
    return `
      <svg class="hdn-scene-svg" viewBox="0 0 220 200" aria-hidden="true">
        <ellipse cx="110" cy="188" rx="78" ry="7" fill="rgba(0,0,0,0.18)"/>
        <g class="hdn-wheel-stand" stroke="#9AA3AD" stroke-width="6" stroke-linecap="round" fill="none">
          <path d="M40 186 L110 130 L180 186"/>
          <path d="M62 186 H158"/>
        </g>
        <g class="hdn-wheel-spin">
          <circle cx="110" cy="100" r="80" fill="none" stroke="#AEB6BF" stroke-width="10"/>
          <circle cx="110" cy="100" r="68" fill="none" stroke="#C19A6B" stroke-width="9" opacity="0.75"/>
          <g stroke="#AEB6BF" stroke-width="5" stroke-linecap="round">
            <line x1="110" y1="24" x2="110" y2="176"/>
            <line x1="34" y1="100" x2="186" y2="100"/>
            <line x1="56" y1="46" x2="164" y2="154"/>
            <line x1="164" y1="46" x2="56" y2="154"/>
          </g>
          <circle cx="110" cy="100" r="12" fill="#8A929A"/>
        </g>
        <g class="hdn-hamster-run">
          <ellipse cx="96" cy="164" rx="11" ry="6" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2"/>
          <ellipse cx="124" cy="164" rx="11" ry="6" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="2"/>
          <ellipse cx="108" cy="146" rx="30" ry="21" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
          <ellipse cx="104" cy="152" rx="18" ry="12" fill="var(--hf-belly)" opacity="0.75"/>
          <circle cx="134" cy="130" r="17" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="2.5"/>
          <circle cx="126" cy="116" r="6" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2"/>
          <circle cx="141" cy="127" r="2.6" fill="#3a2a1a"/>
          <ellipse cx="149" cy="134" rx="4.5" ry="3.5" fill="#f4d9c6"/>
          <path d="M80 142 q-12 4 -18 12" fill="none" stroke="var(--hf-fur-dark)" stroke-width="4" stroke-linecap="round"/>
        </g>
      </svg>
    `;
  }

  _restScene() {
    return `
      <svg class="hdn-scene-svg" viewBox="0 0 220 200" aria-hidden="true">
        <g opacity="0.28" stroke="#AEB6BF" fill="none">
          <circle cx="176" cy="70" r="36" stroke-width="6"/>
          <line x1="176" y1="34" x2="176" y2="106" stroke-width="3"/>
          <line x1="140" y1="70" x2="212" y2="70" stroke-width="3"/>
          <path d="M148 108 L176 84 L204 108" stroke-width="4"/>
        </g>
        <text class="hdn-zzz hdn-zzz-1" x="104" y="74">z</text>
        <text class="hdn-zzz hdn-zzz-2" x="118" y="56">Z</text>
        <text class="hdn-zzz hdn-zzz-3" x="136" y="38">Z</text>
        <ellipse cx="100" cy="164" rx="76" ry="26" fill="#e6cfa0"/>
        <ellipse cx="100" cy="158" rx="60" ry="20" fill="#f0e0bb"/>
        <g stroke="#cbab72" stroke-width="2.5" stroke-linecap="round" fill="none">
          <path d="M34 164 q10 -8 20 0"/>
          <path d="M50 172 q10 -8 20 0"/>
          <path d="M126 172 q10 -8 20 0"/>
          <path d="M146 164 q10 -8 20 0"/>
        </g>
        <g class="hdn-hamster-sleep">
          <ellipse cx="100" cy="150" rx="42" ry="30" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
          <ellipse cx="104" cy="158" rx="26" ry="16" fill="var(--hf-belly)" opacity="0.7"/>
          <circle cx="68" cy="136" r="22" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
          <circle cx="55" cy="122" r="8" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="2"/>
          <path d="M58 136 q5 4 10 0" fill="none" stroke="#3a2a1a" stroke-width="2.4" stroke-linecap="round"/>
          <ellipse cx="79" cy="143" rx="5" ry="4" fill="#f4d9c6"/>
        </g>
      </svg>
    `;
  }

  /**
   * The moon's phase name, or null to keep the fixed crescent.
   *
   * Same treatment as the weather entity: no entity configured, an
   * unavailable one, or a state this doesn't recognise all mean "draw the
   * default" rather than an error in the sky.
   */
  _moonPhase(healthScore) {
    const entityId = healthScore.attributes.moon_entity;
    if (!entityId) return null;
    const state = this._hass.states[entityId];
    if (!state) return null;
    return MOON_PHASES[state.state] ? state.state : null;
  }

  /**
   * The lit part of the moon as an SVG path.
   *
   * Two arcs: the outer limb (a half circle, on whichever side is lit),
   * then the terminator back to the start. The terminator is an ellipse
   * flattened by how full the moon is - at exactly half it collapses to a
   * straight line, which is what makes a quarter moon a clean half disc.
   *
   * Only the bright part is ever drawn. Painting a shadow over a full disc
   * would need it to match the sky behind it, which changes with the
   * gradient, the weather overlay and the cage light.
   */
  _moonPath(lit, waxing) {
    const top = `${MOON_CX} ${MOON_CY - MOON_R}`;
    const bottom = `${MOON_CX} ${MOON_CY + MOON_R}`;
    // Sweep 1 from top to bottom traces the right half, 0 the left.
    const outerSweep = waxing ? 1 : 0;
    // Below half the terminator curves towards the lit limb (a thin
    // crescent); above half it bulges the other way (a fat gibbous).
    const innerSweep = lit < 0.5 ? (waxing ? 0 : 1) : waxing ? 1 : 0;
    const rx = (MOON_R * Math.abs(1 - 2 * lit)).toFixed(2);
    return (
      `M ${top}` +
      ` A ${MOON_R} ${MOON_R} 0 1 ${outerSweep} ${bottom}` +
      ` A ${rx} ${MOON_R} 0 1 ${innerSweep} ${top} Z`
    );
  }

  /** The moon body for a phase, or the long-standing crescent as default. */
  _moonShape(phase) {
    if (phase === null) {
      return `<path d="M272 30 a17 17 0 1 0 0.6 0 a13 13 0 1 1 -0.6 0" fill="#F4E285" opacity="0.95"/>`;
    }
    const { lit, waxing } = MOON_PHASES[phase];
    if (lit >= 1) {
      return `<circle cx="${MOON_CX}" cy="${MOON_CY}" r="${MOON_R}" fill="#F4E285" opacity="0.95"/>`;
    }
    // New moon: earthshine only. Drawing nothing at all would read as a
    // rendering failure rather than as the sky actually looking like that.
    if (lit <= 0) {
      return `<circle cx="${MOON_CX}" cy="${MOON_CY}" r="${MOON_R}" fill="#F4E285" opacity="0.13"/>`;
    }
    return `<path d="${this._moonPath(lit, waxing)}" fill="#F4E285" opacity="0.95"/>`;
  }

  /**
   * The stars, each carrying its own twinkle range and timing.
   *
   * The `opacity` attribute keeps the star's bright value, so it is what
   * shows if the animation never runs - which is exactly what happens
   * under prefers-reduced-motion, where the keyframes are switched off.
   */
  _starsSvg() {
    return STARS.map(
      (s) =>
        `<circle class="hdn-star" cx="${s.cx}" cy="${s.cy}" r="${s.r}" fill="#fff"` +
        ` opacity="${s.max}"` +
        ` style="--tw-max: ${s.max}; --tw-min: ${(s.max * 0.35).toFixed(2)};` +
        ` animation-duration: ${s.dur}s; animation-delay: ${s.delay}s"/>`
    ).join("\n        ");
  }

  _moonSvg(phase = null) {
    return `
      <svg class="hdn-decor-svg" viewBox="0 0 300 120" preserveAspectRatio="xMaxYMin meet" aria-hidden="true">
        ${this._starsSvg()}
        <g transform="${CELESTIAL_OFFSET}">
          ${this._moonShape(phase)}
        </g>
      </svg>
    `;
  }

  _sunSvg() {
    return `
      <svg class="hdn-decor-svg" viewBox="0 0 300 120" preserveAspectRatio="xMaxYMin meet" aria-hidden="true">
        <g class="hdn-celestial" transform="${this._sunTransform()}">
        <g class="hdn-sun">
          <circle cx="266" cy="32" r="16" fill="#FFD166"/>
          <g stroke="#FFD166" stroke-width="3" stroke-linecap="round" opacity="0.85">
            <line x1="266" y1="6" x2="266" y2="0"/>
            <line x1="266" y1="64" x2="266" y2="58"/>
            <line x1="240" y1="32" x2="234" y2="32"/>
            <line x1="298" y1="32" x2="292" y2="32"/>
            <line x1="248" y1="14" x2="244" y2="10"/>
            <line x1="284" y1="50" x2="288" y2="54"/>
            <line x1="284" y1="14" x2="288" y2="10"/>
            <line x1="248" y1="50" x2="244" y2="54"/>
          </g>
        </g>
        </g>
        <g fill="#ffffff" opacity="0.5">
          <ellipse cx="60" cy="34" rx="30" ry="11"/>
          <ellipse cx="46" cy="28" rx="17" ry="10"/>
          <ellipse cx="150" cy="58" rx="24" ry="9"/>
        </g>
      </svg>
    `;
  }

  _chip({ icon, label, value, entity, tone, badge }) {
    const wide = badge ? " hdn-chip-wide" : "";
    const attrs = entity
      ? `data-entity="${entity}" tabindex="0" role="button" class="hdn-chip hdn-clickable${wide}${tone ? ` hdn-chip-${tone}` : ""}"`
      : `class="hdn-chip${wide}${tone ? ` hdn-chip-${tone}` : ""}"`;
    return `
      <div ${attrs}>
        <svg class="hdn-chip-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${icon}"/></svg>
        <span class="hdn-chip-text">
          <span class="hdn-chip-label">${label}</span>
          <span class="hdn-chip-value">${value}</span>
        </span>
        ${badge ? `<span class="hdn-chip-badge">${badge}</span>` : ""}
      </div>
    `;
  }

  _lightChip() {
    const switchId = this._entityId("light_automation");
    const automation = this._hass.states[switchId];
    if (!automation) return ""; // no cage light configured for this hamster

    const lightId = automation.attributes.light_entity;
    const light = lightId ? this._hass.states[lightId] : undefined;
    const lightOn = light && light.state === "on";
    const paused = automation.attributes.pause_active;
    const pausedUntil = automation.attributes.paused_until;

    let statusText;
    if (automation.state === "off") {
      statusText = t(this._hass, "dayNight.automationOff");
    } else if (paused) {
      statusText = t(this._hass, "dayNight.pausedUntil", {
        time: fmtTime(this._hass, pausedUntil),
      });
    } else {
      statusText = t(this._hass, lightOn ? "dayNight.lightOn" : "dayNight.lightOff");
    }

    const button =
      automation.state === "on" && !paused
        ? `<button class="hdn-chip-button" data-action="pause-light" data-switch="${switchId}" type="button">${t(this._hass, "dayNight.pauseButton")}</button>`
        : "";

    // The chip body toggles the lamp; the label still opens the
    // automation's more-info dialog, and the pause button still pauses.
    // Three targets in one chip, so each one is matched before the
    // generic handler in _ensureSkeleton().
    const toggleAttrs = light
      ? `data-action="toggle-light" data-light="${lightId}" tabindex="0" role="button"
         aria-pressed="${lightOn ? "true" : "false"}"`
      : "";

    return `
      <div class="hdn-chip hdn-chip-wide${lightOn ? " hdn-chip-lit" : ""}${light ? " hdn-clickable" : ""}"
           ${toggleAttrs}>
        <svg class="hdn-chip-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS.light}"/></svg>
        <span class="hdn-chip-text">
          <span class="hdn-chip-label hdn-clickable" data-entity="${switchId}" tabindex="0" role="button">${t(this._hass, "dayNight.cageLight")}</span>
          <span class="hdn-chip-value"><span>${statusText}</span></span>
        </span>
        ${button}
      </div>
    `;
  }

  _render() {
    if (!this._hass || !this._root || !this._config) return;

    const healthScore = this._entity("health_score");
    if (!healthScore) {
      this._errorEl.hidden = false;
      this._errorEl.textContent = t(this._hass, "common.notFound", {
        entity: this._config.entity,
      });
      this._skyEl.hidden = true;
      return;
    }
    this._errorEl.hidden = true;
    this._skyEl.hidden = false;

    const nightActive = this._entity("night_active_duration");
    const dayRest = this._entity("day_rest_duration");
    const currentSpeed = this._entity("current_speed");
    const nightDistance = this._entity("night_distance");
    const humidity = this._entity("humidity");
    const temperature = healthScore.attributes.temperature;

    const activeMinutes = nightActive ? Number(nightActive.state) : 0;
    const isActive = Number.isFinite(activeMinutes) && activeMinutes > 0;

    // Fur colour comes from the hamster's profile (config flow), so two
    // hamsters on one dashboard don't look like the same animal.
    applyFur(this._root, coatColor(healthScore));

    const ambientLx = this._ambientLightLx(healthScore);
    this._skyEl.style.background = this._backgroundGradient(ambientLx);

    const title =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._capitalize(this._config.entity.match(ENTITY_PATTERN)[1]);
    this._titleEl.textContent = title.toUpperCase();

    // The badge used to show whether the hamster was active or resting -
    // but the wheel scene already makes that obvious at a glance, while
    // "is the sensor actually reporting" has no other indicator on this
    // card at all.
    const status = this._connectionStatus(this._entityId("current_speed"));
    this._statusDotEl.style.background = status.color;
    this._statusLabelEl.textContent = t(this._hass, status.key);

    // Sky decoration and scene are only rebuilt when they actually change
    // mode - rebuilding them every update is what used to restart the
    // wheel animation mid-spin.
    // Same reasoning as the decoration below: every element in the
    // weather overlay is CSS-animated, so rebuilding identical markup
    // would restart clouds and rain mid-drift.
    const weatherKey =
      (healthScore.attributes.weather_entity &&
        this._hass.states[healthScore.attributes.weather_entity]?.state) ||
      "none";
    if (weatherKey !== this._weatherKey) {
      this._weatherEl.innerHTML = this._weatherOverlay(
        this._weatherScene(healthScore)
      );
      this._weatherKey = weatherKey;
    }

    const decorMode = this._isNight(ambientLx) ? "night" : "day";
    // The phase is part of the key, so a moon that has moved on to the
    // next phase is redrawn - at most once a day, which is also why
    // rebuilding rather than patching the path is fine here.
    const moonPhase = this._moonPhase(healthScore);
    const decorKey = decorMode === "night" ? `night:${moonPhase}` : "day";
    if (decorKey !== this._decorKey) {
      this._decorEl.innerHTML =
        decorMode === "night" ? this._moonSvg(moonPhase) : this._sunSvg();
      this._decorKey = decorKey;
      this._celestialEl = this._decorEl.querySelector(".hdn-celestial");
    }
    // Moved by attribute rather than by re-rendering the SVG: the sun's
    // pulse is a CSS animation on a child element, and rebuilding the
    // markup every time the elevation ticks would restart it mid-beat.
    if (decorMode === "day" && this._celestialEl) {
      this._celestialEl.setAttribute("transform", this._sunTransform());
    }

    const sceneMode = isActive ? "run" : "rest";
    if (sceneMode !== this._sceneMode) {
      this._sceneEl.innerHTML = isActive ? this._wheelScene() : this._restScene();
      this._sceneMode = sceneMode;
      this._wheelEl = this._sceneEl.querySelector(".hdn-wheel-spin");
      this._wheelAnim = null; // the old animation went out with the old node
    }

    if (this._sceneMode === "run") {
      this._applyWheelSpin(this._spinDurationS(currentSpeed));
    }

    const chips = [];
    if (this._config.show_active_duration && isActive) {
      chips.push(
        this._chip({
          icon: ICONS.timer,
          label: t(this._hass, "dayNight.runningFor"),
          value: `<span>${fmtDuration(this._hass, activeMinutes)}</span>`,
          entity: this._entityId("night_active_duration"),
        })
      );
    }
    if (this._config.show_rest_duration && !isActive) {
      // An open lid belongs next to the rest timer: opening it is exactly
      // what interrupts the hamster's rest, and disturbances during the
      // main sleep phase are what the sleep pillar scores.
      const door = this._entity("door");
      chips.push(
        this._chip({
          icon: ICONS.timer,
          label: t(this._hass, "dayNight.restingFor"),
          value: `<span>${fmtDuration(this._hass, dayRest && dayRest.state)}</span>`,
          entity: this._entityId("day_rest_duration"),
          badge:
            door && door.state === "on" ? t(this._hass, "dayNight.lidOpen") : "",
        })
      );
    }
    if (this._config.show_speed) {
      chips.push(
        this._chip({
          icon: ICONS.speed,
          label: t(this._hass, "dayNight.speed"),
          value: `<span>${fmtNumber(this._hass, currentSpeed && currentSpeed.state, 1, "km/h")}</span>`,
          entity: this._entityId("current_speed"),
        })
      );
    }
    if (this._config.show_distance) {
      // The average, not the distance alone, says something about HOW the
      // hamster ran tonight - distance over the time it actually spent
      // running (see coordinator.py's night_avg_speed_kmh), not over
      // wall-clock hours, so a hamster that slept most of the night isn't
      // read as "slow". Missing until at least a minute of that running
      // time has piled up - a fresher average than that is really just
      // the current speed again.
      const nightAvgSpeed = healthScore.attributes.night_avg_speed_kmh;
      const distanceText = fmtNumber(this._hass, nightDistance && nightDistance.state, 2, "km");
      const value =
        nightAvgSpeed === null || nightAvgSpeed === undefined
          ? `<span>${distanceText}</span>`
          : `<span>${distanceText} ·</span> <span>${fmtNumber(this._hass, nightAvgSpeed, 1, "km/h")}</span>`;
      chips.push(
        this._chip({
          icon: ICONS.distance,
          label: t(this._hass, "dayNight.thisNight"),
          value,
          entity: this._entityId("night_distance"),
        })
      );
    }
    if (this._config.show_climate) {
      const climate = humidity
        ? `<span>${fmtNumber(this._hass, temperature, 1, "°C")} ·</span> <span>${fmtNumber(this._hass, humidity.state, 0, "%")}</span>`
        : `<span>${fmtNumber(this._hass, temperature, 1, "°C")}</span>`;
      // Tapping this chip used to open the health score, because the
      // card renders the temperature from an attribute and had no
      // reference to the sensor behind it. The coordinator now publishes
      // the configured source entity, so the tap lands on the thermometer
      // whose reading is actually being shown.
      chips.push(
        this._chip({
          icon: ICONS.climate,
          label: t(this._hass, "dayNight.climate"),
          value: climate,
          entity:
            healthScore.attributes.temperature_entity ||
            this._entityId("health_score"),
        })
      );
    }
    if (this._config.show_light) {
      chips.push(this._lightChip());
    }

    this._chipsEl.innerHTML = chips.join("");
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
}

HamsterDayNightCard.styles = `
  ${HEADER_STYLES}
  ha-card {
    padding: 0;
    overflow: hidden;
  }
  .hdn-root {
    --hf-fur: ${DEFAULT_FUR};
    --hf-fur-light: #e0a869;
    --hf-fur-dark: #7f5429;
    --hf-belly: #f2ddc4;
  }
  .hdn-error {
    color: var(--secondary-text-color);
    font-size: 0.9em;
    padding: 16px;
  }
  .hdn-sky {
    position: relative;
    padding: 14px 16px 18px;
    overflow: hidden;
    transition: background 0.8s ease;
  }
  /* Uniform scaling (preserveAspectRatio), so the sun stays a disc and
     the moon a crescent at every card width - "none" used to stretch
     them into eggs. "meet" fits the whole viewBox rather than cropping
     it, and the xMax anchor keeps the sun and moon, which sit at the
     right of the viewBox, pinned to the right of the card.

     The sun and the moon are placed low and left inside that viewBox
     (see CELESTIAL_OFFSET), which is the only part of the sky nothing
     else occupies: the header strip sits above them, the reading chips
     to their right. */
  .hdn-decor {
    position: absolute;
    inset: 0 0 auto 0;
    height: 130px;
    pointer-events: none;
  }
  .hdn-decor-svg {
    width: 100%;
    height: 100%;
    display: block;
  }
  .hdn-sun {
    transform-origin: 266px 32px;
    animation: sunPulse 6s ease-in-out infinite;
  }
  @keyframes sunPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.06); }
  }
  /* Each star fades between its own dim and bright ends rather than a
     shared pair, so the depth that the differing base opacities give the
     sky survives the animation - otherwise every star would pulse to the
     same white and the sky would flatten out. Duration and delay come
     from the element's own inline style (see _starsSvg). */
  .hdn-star {
    animation: hdnTwinkle 4s ease-in-out infinite;
  }
  @keyframes hdnTwinkle {
    0%, 100% { opacity: var(--tw-min); }
    50% { opacity: var(--tw-max); }
  }
  /* Weather overlay: sits above the sky gradient and the sun/moon, below
     the header and the reading chips (which carry z-index 1-2), so rain
     falls behind the text rather than over it. Never interactive. */
  .hdn-weather {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
  }
  .hdn-weather-dim {
    position: absolute;
    inset: 0;
    background: #0B132B;
  }
  .hdn-fog {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      180deg,
      rgba(255, 255, 255, 0.02),
      rgba(255, 255, 255, 0.22) 55%,
      rgba(255, 255, 255, 0.05)
    );
    animation: hdnFog 18s ease-in-out infinite;
  }
  @keyframes hdnFog {
    0%, 100% { opacity: 0.55; }
    50% { opacity: 0.95; }
  }
  .hdn-cloud {
    position: absolute;
    left: -30%;
    width: 120px;
    height: 38px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.42);
    filter: blur(6px);
    animation-name: hdnDrift;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
  }
  @keyframes hdnDrift {
    from { transform: translateX(0) scale(var(--s, 1)); }
    to { transform: translateX(360px) scale(var(--s, 1)); }
  }
  .hdn-drop {
    position: absolute;
    top: -12%;
    animation-name: hdnFall;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
  }
  .hdn-drop-rain,
  .hdn-drop-sleet {
    width: 2px;
    height: 13px;
    border-radius: 1px;
    background: linear-gradient(
      180deg,
      rgba(180, 220, 255, 0),
      rgba(180, 220, 255, 0.85)
    );
  }
  .hdn-drop-hail {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: rgba(226, 244, 255, 0.95);
  }
  .hdn-drop-snow {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.92);
  }
  @keyframes hdnFall {
    from { transform: translateY(0); }
    to { transform: translateY(560px); }
  }
  /* A double flash, then a long dark gap - lightning that strobed evenly
     would read as a broken screen rather than a storm. */
  .hdn-lightning {
    position: absolute;
    inset: 0;
    background: #ffffff;
    opacity: 0;
    animation: hdnFlash 7s linear infinite;
  }
  @keyframes hdnFlash {
    0%, 3%, 6%, 100% { opacity: 0; }
    1% { opacity: 0.5; }
    4.5% { opacity: 0.32; }
  }

  /* The other cards seat their header on a solid banner. This one sits
     straight on the live sky - gradient, stars, a sun - so it gets its
     own frosted strip instead, bled out to the card edges with negative
     margins that cancel .hdn-sky's padding. Without it the white title
     has nothing but a text-shadow between it and a bright noon sky. */
  .hdn-sky .hf-header {
    margin: -14px -16px 12px;
    padding: 14px 16px;
    background: rgba(0, 0, 0, 0.22);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
  }
  .hdn-body {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    margin-top: 6px;
  }
  .hdn-scene-svg {
    display: block;
    width: 100%;
    height: auto;
    max-height: 240px;
  }
  .hdn-chips {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .hdn-chip {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 12px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.16);
    backdrop-filter: blur(6px);
    color: #ffffff;
  }
  /* Only the light chip carries a trailing button (the pause button)
     alongside its label/value text - the other chips are just icon+text
     and never need this. At some widths "Cage light" + "Light off" +
     "Pause 30 min" no longer fit on one line; the value text is nowrap
     (see .hdn-chip-value below) and the button doesn't shrink either, so
     without somewhere to go the button used to sit on top of the text.
     Wrapping lets the button drop to its own line instead - the gap: 9px
     set above already doubles as the row-gap between the two lines once
     it wraps, so nothing else needs to change. */
  .hdn-chip-wide {
    flex-wrap: wrap;
  }
  .hdn-chip-icon {
    width: 19px;
    height: 19px;
    flex-shrink: 0;
    fill: rgba(255, 255, 255, 0.9);
  }
  .hdn-chip-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
    min-width: 0;
  }
  .hdn-chip-label {
    font-size: 0.66em;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.72);
  }
  .hdn-chip-value {
    font-size: 1.15em;
    font-weight: 800;
  }
  /* Chips that combine two readings ("2.84 km · 3.1 km/h", "21.4 °C ·
     52 %") outgrew their pill on any card narrower than ~560px once the
     night average was added. The value may now wrap between its parts -
     each part is its own nowrap span, so a number never separates from
     its unit. */
  .hdn-chip-value > span {
    white-space: nowrap;
  }
  .hdn-chip-lit {
    border-color: rgba(255, 209, 102, 0.75);
    box-shadow: 0 0 14px rgba(255, 209, 102, 0.3);
  }
  .hdn-chip-lit .hdn-chip-icon {
    fill: #FFD166;
  }
  /* Same shape as the pause button, but purely informational - amber
     rather than neutral, and not focusable, since there is nothing to
     press. */
  .hdn-chip-badge {
    margin-left: auto;
    border: 1px solid rgba(255, 209, 102, 0.55);
    background: rgba(255, 209, 102, 0.22);
    color: #FFD166;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 0.7em;
    font-weight: 700;
    white-space: nowrap;
  }
  .hdn-chip-button {
    margin-left: auto;
    border: 1px solid rgba(255, 255, 255, 0.35);
    background: rgba(255, 255, 255, 0.14);
    color: #ffffff;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 0.7em;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.15s ease;
  }
  .hdn-chip-button:hover,
  .hdn-chip-button:focus-visible {
    background: rgba(255, 255, 255, 0.3);
    outline: none;
  }
  /* The rotation itself is driven from JS (see _applyWheelSpin) so that a
     speed change retimes the running animation instead of restarting it. */
  .hdn-wheel-spin {
    transform-origin: 110px 100px;
  }
  .hdn-hamster-run {
    animation: runBob 0.5s ease-in-out infinite;
    transform-origin: 108px 164px;
  }
  /* Wheel parked mid-session: stop the hamster bobbing along with it. */
  .hdn-scene-idle .hdn-hamster-run {
    animation-play-state: paused;
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
    font-size: 20px;
    font-weight: 800;
    fill: #ffffff;
    opacity: 0;
    animation: floatZzz 3s ease-in infinite;
  }
  .hdn-zzz-1 { animation-delay: 0s; }
  .hdn-zzz-2 { animation-delay: 0.6s; }
  .hdn-zzz-3 { animation-delay: 1.2s; }
  @keyframes floatZzz {
    0% { opacity: 0; transform: translateY(8px); }
    15% { opacity: 0.9; }
    80% { opacity: 0.3; }
    100% { opacity: 0; transform: translateY(-16px); }
  }
  .hdn-clickable {
    cursor: pointer;
  }
  .hdn-clickable:focus-visible {
    outline: 2px solid rgba(255, 255, 255, 0.7);
    outline-offset: 2px;
    border-radius: 6px;
  }

  @media (prefers-reduced-motion: reduce) {
    .hdn-hamster-run,
    .hdn-hamster-sleep,
    .hdn-zzz,
    .hdn-sun,
    .hdn-star,
    .hdn-cloud,
    .hdn-drop,
    .hdn-fog {
      animation: none;
    }
    /* Dropped entirely rather than merely paused: a full-card white
       strobe is exactly the kind of flashing this setting exists to
       avoid, and a frozen one would just sit there as a bright pane. */
    .hdn-lightning {
      display: none;
    }
  }

  /* Narrow cards (sidebar columns, phones): stack the chips under the
     scene instead of squeezing both into two columns. */
  @media (max-width: 460px) {
    .hdn-body {
      grid-template-columns: 1fr;
    }
    .hdn-chips {
      flex-direction: row;
      flex-wrap: wrap;
    }
    .hdn-chip {
      flex: 1 1 45%;
    }
    /* Two chips per row leaves each about 45% of an already narrow card,
       which the two-part values (distance + average speed, temperature +
       humidity) still outgrow even when wrapped. A touch smaller here
       rather than clipped. */
    .hdn-chip-value {
      font-size: 1.02em;
    }
    .hdn-chip-wide {
      flex-basis: 100%;
    }
    .hdn-scene-svg {
      max-height: 190px;
    }
  }
`;

customElements.define("hamster-day-night-card", HamsterDayNightCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-day-night-card",
  name: t(null, "dayNight.pickerName"),
  description: t(null, "dayNight.pickerDescription"),
});

/**
 * Visual editor ("Configure card" dialog), backed by <ha-form> - same
 * pattern as the other cards' editors.
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
  { name: "show_light", selector: { boolean: {} } },
];

// Translation keys, resolved per render - the editor is opened long
// after module load, so `hass` (and with it the user's language) exists.
const DAY_NIGHT_EDITOR_LABELS = {
  entity: "common.entityPicker",
  title: "common.optionalTitle",
  show_speed: "dayNight.showSpeed",
  show_distance: "dayNight.showDistance",
  show_active_duration: "dayNight.showActive",
  show_rest_duration: "dayNight.showRest",
  show_climate: "dayNight.showClimate",
  show_light: "dayNight.showLight",
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
      this._form.computeLabel = (schema) =>
        DAY_NIGHT_EDITOR_LABELS[schema.name]
          ? t(this._hass, DAY_NIGHT_EDITOR_LABELS[schema.name])
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
    this._form.schema = DAY_NIGHT_EDITOR_SCHEMA;
    this._form.data = this._config;
  }
}

customElements.define("hamster-day-night-card-editor", HamsterDayNightCardEditor);
