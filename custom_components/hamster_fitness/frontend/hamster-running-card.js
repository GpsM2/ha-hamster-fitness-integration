/**
 * Hamster Fitness: Running
 *
 * One bar per night for the last week, so a run can be read against the
 * nights around it rather than on its own. The Day & Night card shows
 * what is happening now; this one shows whether that is normal.
 *
 * Everything comes from attributes on the health-score sensor, the same
 * entity every other per-hamster card takes:
 *
 * - `night_history`   one entry per completed night (see coordinator.py's
 *                     _record_night). Climate values are averages across
 *                     that night, not closing snapshots.
 * - `night_window_date` which date the window still running belongs to.
 *                     That night is by definition absent from the
 *                     history, so the card appends it as a provisional
 *                     bar built from night_distance_km and friends.
 * - `best_night_km` / `lifetime_max_speed_kmh` and their dates - personal
 *                     bests, deliberately not capped to the seven nights.
 * - `min_distance_km` the health score's own activity threshold, reused
 *                     here as the goal line so the card cannot disagree
 *                     with the score about what "enough" means.
 *
 * Config:
 *   type: custom:hamster-running-card
 *   entity: sensor.hamster_<name>_health_score
 *   title: Laufleistung     # optional
 */

import {
  HEADER_STYLES,
  applyFur,
  coatColor,
  fmtDate,
  fmtNumber,
  fmtWeekday,
  healthScoreEntityFor,
  healthScoreEntitySelector,
  bindShareButton,
  SHARE_STYLES,
  shareFilename,
  memoizedEditorSchema,
  renderCardHeader,
  deviceDisplayName,
  t,
} from "./hamster-fitness-shared.js?v=17";

const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

// Chart geometry, in SVG user units - layout proportions, not pixels.
//
// The viewBox ratio is deliberately wide (3:1). The SVG scales
// UNIFORMLY (no preserveAspectRatio="none"), because the overlay dots
// are circles and the axis labels are real text: stretching the
// coordinate system would turn the dots into ellipses and squash the
// lettering, the same trap the Day & Night sky decoration fell into.
// Uniform scaling means the height follows the width, so a wide ratio
// is what keeps the chart from becoming absurdly tall on a wide card -
// with a max-height in the CSS as the backstop.
const CHART_W = 360;
const CHART_H = 120;
const PAD_LEFT = 30;
const PAD_RIGHT = 8;
const PAD_TOP = 10;
const PAD_BOTTOM = 18;
const PLOT_W = CHART_W - PAD_LEFT - PAD_RIGHT;
const PLOT_H = CHART_H - PAD_TOP - PAD_BOTTOM;

// Seven closed nights (NIGHT_HISTORY_NIGHTS in const.py) plus the one
// still running.
const NIGHTS_ON_CHART = 8;

// Which optional overlays exist, and how each reads its value out of a
// night entry. Adding one here is enough to get its toggle, its line and
// its colour - nothing else in the card enumerates them.
const OVERLAYS = {
  speed: { key: "avg_speed_kmh", color: "#4EA8DE", label: "running.avgSpeed", unit: "km/h" },
  temperature: { key: "temperature_c", color: "#F4A261", label: "running.temperature", unit: "°C" },
  humidity: { key: "humidity_pct", color: "#84DCC6", label: "running.humidity", unit: "%" },
};

const LOGO_RUNNING_SVG = `
<svg viewBox="0 0 200 200" width="34" height="34" aria-hidden="true">
  <circle cx="100" cy="100" r="72" fill="none" stroke="#AEB6BF" stroke-width="9"/>
  <circle cx="100" cy="100" r="60" fill="none" stroke="#C19A6B" stroke-width="8" opacity="0.75"/>
  <g stroke="#AEB6BF" stroke-width="5" stroke-linecap="round">
    <line x1="100" y1="32" x2="100" y2="168"/>
    <line x1="32" y1="100" x2="168" y2="100"/>
    <line x1="52" y1="52" x2="148" y2="148"/>
    <line x1="148" y1="52" x2="52" y2="148"/>
  </g>
  <circle cx="100" cy="100" r="11" fill="#8A929A"/>
  <ellipse cx="104" cy="132" rx="27" ry="19" fill="var(--hf-fur)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
  <circle cx="126" cy="120" r="13" fill="var(--hf-fur-light)" stroke="var(--hf-fur-dark)" stroke-width="3"/>
  <circle cx="130" cy="116" r="2.6" fill="#3a2a1a"/>
</svg>
`;

class HamsterRunningCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error(t(null, "common.needEntity", { card: "Running" }));
    }
    if (!ENTITY_PATTERN.test(config.entity)) {
      throw new Error(t(null, "common.wrongEntity", { card: "Running" }));
    }
    this._config = { ...config };

    if (!this._root) {
      this.innerHTML = `
        <ha-card>
          <div class="hrc-root">
            <div class="hrc-error" hidden></div>
            <div class="hrc-banner"></div>
            <div class="hrc-body"></div>
          </div>
        </ha-card>
        <style>${HamsterRunningCard.styles}</style>
      `;
      this._root = this.querySelector(".hrc-root");
      this._errorEl = this.querySelector(".hrc-error");
      this._bannerEl = this.querySelector(".hrc-banner");
      this._bodyEl = this.querySelector(".hrc-body");

      // Which overlays are switched on. Card-local UI state on purpose:
      // it is a way of looking at the data, not a property of the
      // hamster, so it does not belong in the dashboard config.
      this._overlays = { speed: true, temperature: false, humidity: false };

      this._bodyEl.addEventListener("click", (ev) => {
        const toggle = ev.target.closest("[data-overlay]");
        if (!toggle) return;
        const name = toggle.dataset.overlay;
        this._overlays[name] = !this._overlays[name];
        this._render();
      });

      bindShareButton(this._root, () => this._sharePayload());
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
    return document.createElement("hamster-running-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {}).find((id) =>
      ENTITY_PATTERN.test(id)
    );
    return { entity: entity || "sensor.hamster_health_score" };
  }

  /**
   * What this card offers the share image.
   *
   * Built when the button is pressed rather than kept alongside the
   * render, so the picture carries the values on screen at that moment.
   */
  _sharePayload() {
    const state = this._hass && this._hass.states[this._config.entity];
    if (!state) return null;
    const attrs = state.attributes || {};
    const nights = this._nights(attrs);
    const closed = nights.filter((n) => !n.live);
    const last = closed[closed.length - 1];
    const weekTotal = nights.reduce(
      (sum, n) => sum + (Number.isFinite(n.distance) ? n.distance : 0),
      0
    );
    const name =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._config.entity.match(ENTITY_PATTERN)[1].replace(/_/g, " ");

    const stats = [
      {
        key: "week",
        label: t(this._hass, "share.statWeek"),
        value: fmtNumber(this._hass, weekTotal, 1, "km"),
      },
      {
        key: "best",
        label: t(this._hass, "running.bestNight"),
        value: fmtNumber(this._hass, _num(attrs.best_night_km), 2, "km"),
      },
      {
        key: "fastest",
        label: t(this._hass, "running.fastest"),
        value: fmtNumber(this._hass, _num(attrs.lifetime_max_speed_kmh), 1, "km/h"),
      },
    ];
    if (last) {
      stats.push({
        key: "last",
        label: t(this._hass, "share.statLastNight"),
        value: fmtNumber(this._hass, last.distance, 2, "km"),
        default: false,
      });
    }

    return {
      hass: this._hass,
      entity: this._config.entity,
      title: name,
      subtitle: t(this._hass, "running.subtitle"),
      fur: coatColor(state),
      stats,
      filename: shareFilename(name, "running"),
    };
  }

  /**
   * Nights oldest first, with everything coerced to numbers.
   *
   * night_history holds only nights that have CLOSED - an entry is
   * written once at the window reset and never revisited, which is what
   * makes it safe to compare against personal bests. So the night
   * currently running is not in there, and without the provisional entry
   * appended below the card would show nothing at all on its first day
   * and yesterday's news on every other, while night_distance_km has
   * been counting up live the whole time.
   *
   * The window's date comes from the integration rather than from the
   * clock here: at 07:00 the window that opened at 20:00 yesterday is
   * still running, and re-deriving that rule in JavaScript would mean
   * two copies of NIGHT_WINDOW_START_HOUR to keep in step.
   */
  _nights(attrs) {
    const history = Array.isArray(attrs.night_history) ? attrs.night_history : [];
    const nights = history.map((item) => ({
      date: item.date,
      distance: Number(item.distance_km),
      avg_speed_kmh: _num(item.avg_speed_kmh),
      temperature_c: _num(item.temperature_c),
      humidity_pct: _num(item.humidity_pct),
      // Absent on nights recorded before session counting existed - the
      // history survives upgrades, so old entries simply have no number
      // rather than a misleading zero.
      sessions: _num(item.sessions),
      live: false,
    }));

    const liveDate = attrs.night_window_date;
    // Guard against the double bar in the seconds between the reset
    // writing the closing night and the new window's date arriving.
    if (liveDate && !nights.some((n) => n.date === liveDate)) {
      nights.push({
        date: liveDate,
        distance: Number(attrs.night_distance_km),
        avg_speed_kmh: _num(attrs.night_avg_speed_kmh),
        temperature_c: _num(attrs.temperature),
        humidity_pct: _num(attrs.humidity),
        sessions: _num(attrs.night_sessions),
        live: true,
      });
    }
    return nights.slice(-NIGHTS_ON_CHART);
  }

  /**
   * The distance axis: 0 up to a rounded ceiling above both the longest
   * bar and the goal line.
   *
   * The goal is included deliberately - a week that never reached it
   * would otherwise draw the line off the top of the chart, which is
   * exactly the week where seeing how far short it fell matters most.
   */
  _distanceMax(nights, goal) {
    const values = nights.map((n) => n.distance).filter(Number.isFinite);
    const peak = Math.max(...values, goal || 0, 0.1);
    const step = peak <= 2 ? 0.5 : peak <= 10 ? 1 : 5;
    return Math.ceil(peak / step) * step;
  }

  _bars(nights, max) {
    const slot = PLOT_W / nights.length;
    const width = Math.min(26, slot * 0.55);
    return nights
      .map((night, i) => {
        const x = PAD_LEFT + slot * (i + 0.5);
        const valid = Number.isFinite(night.distance);
        const h = valid ? (night.distance / max) * PLOT_H : 0;
        const y = PAD_TOP + PLOT_H - h;
        // The night in progress is drawn hollow: three hours into a
        // night is not the same as a short night, and a solid bar next
        // to seven finished ones would invite exactly that reading.
        const label = night.live
          ? t(this._hass, "running.tonight")
          : fmtWeekday(this._hass, night.date);
        return `
          <rect class="hrc-bar${night.live ? " hrc-bar-live" : ""}"
                x="${(x - width / 2).toFixed(1)}" y="${y.toFixed(1)}"
                width="${width.toFixed(1)}" height="${Math.max(h, valid ? 1.5 : 0).toFixed(1)}"
                rx="${Math.min(3, width / 2).toFixed(1)}"/>
          <text class="hrc-xlabel${night.live ? " hrc-xlabel-live" : ""}"
                x="${x.toFixed(1)}" y="${CHART_H - 5}"
                text-anchor="middle">${label}</text>
        `;
      })
      .join("");
  }

  /**
   * The per-night session counts, drawn inside the top of each bar.
   *
   * A count, not a measurement - so it rides in the bar rather than
   * earning a fourth axis for a single-digit integer. Rendered after the
   * overlay lines on purpose: the speed line runs right across the bar
   * tops and was striking the digits through.
   */
  _sessionLabels(nights, max) {
    const slot = PLOT_W / nights.length;
    return nights
      .map((night, i) => {
        const h = Number.isFinite(night.distance) ? (night.distance / max) * PLOT_H : 0;
        // Skip bars too short to hold the digit inside them.
        if (!Number.isFinite(night.sessions) || night.sessions <= 0 || h <= 16) return "";
        const x = PAD_LEFT + slot * (i + 0.5);
        const y = PAD_TOP + PLOT_H - h + 11;
        // White reads well against a filled bar, but the live bar is
        // hollow - white on the card background leaves only the outline
        // showing. That one takes the coat colour as its fill instead.
        const cls = night.live ? "hrc-sessions hrc-sessions-live" : "hrc-sessions";
        return `<text class="${cls}" x="${x.toFixed(1)}" y="${y.toFixed(1)}"
                      text-anchor="middle">${night.sessions}</text>`;
      })
      .join("");
  }

  /** A dashed rule across the plot, used for the goal and the average. */
  _rule(value, max, className) {
    if (!Number.isFinite(value) || value <= 0 || value > max) return "";
    const y = PAD_TOP + PLOT_H - (value / max) * PLOT_H;
    return `<line class="${className}" x1="${PAD_LEFT}" y1="${y.toFixed(1)}"
                  x2="${CHART_W - PAD_RIGHT}" y2="${y.toFixed(1)}"/>`;
  }

  /**
   * One overlay as a polyline on its own scale.
   *
   * Each overlay is normalised against its own maximum rather than the
   * distance axis: they are different units entirely, and forcing
   * humidity onto a kilometre scale would flatten it into a straight
   * line at the bottom. The shape is what these lines are for - whether
   * the hamster ran faster on the colder nights - not the absolute
   * value, which the tooltip gives exactly.
   */
  /**
   * One overlay as a line over the bars, scaled to its own range.
   *
   * A single reading still gets its dot. Returning nothing at all below
   * two points - which is what this did - meant that on the first night
   * all three toggles looked like dead buttons: they flipped their own
   * state correctly and the chart never changed.
   */
  _overlayLine(nights, name) {
    const spec = OVERLAYS[name];
    const values = nights.map((n) => n[spec.key]);
    const known = values.filter(Number.isFinite);
    if (!known.length) return "";

    const min = Math.min(...known);
    const max = Math.max(...known);
    const span = max - min || 1;
    const slot = PLOT_W / nights.length;
    // Inset so a flat line doesn't sit exactly on the axis or the top.
    const top = PAD_TOP + PLOT_H * 0.12;
    const height = PLOT_H * 0.76;
    // With one reading there is no range to place it in, and (v-min)/span
    // would put it on the floor - reading as "the lowest yet" when it is
    // simply the only one. Centre it instead.
    const yFor = (value) =>
      known.length < 2
        ? top + height / 2
        : top + height - ((value - min) / span) * height;

    const points =
      known.length < 2
        ? ""
        : values
            .map((value, i) =>
              Number.isFinite(value)
                ? `${(PAD_LEFT + slot * (i + 0.5)).toFixed(1)},${yFor(value).toFixed(1)}`
                : null
            )
            .filter(Boolean)
            .join(" ");

    const dots = values
      .map((value, i) =>
        Number.isFinite(value)
          ? `<circle cx="${(PAD_LEFT + slot * (i + 0.5)).toFixed(1)}" cy="${yFor(
              value
            ).toFixed(1)}" r="${known.length < 2 ? 3.4 : 2.4}" fill="${spec.color}"/>`
          : ""
      )
      .join("");

    const line = points
      ? `<polyline class="hrc-overlay" points="${points}" stroke="${spec.color}"/>`
      : "";
    return `${line}${dots}`;
  }

  _yAxis(max) {
    return [0, max / 2, max]
      .map((value) => {
        const y = PAD_TOP + PLOT_H - (value / max) * PLOT_H;
        return `
          <line class="hrc-grid" x1="${PAD_LEFT}" y1="${y.toFixed(1)}"
                x2="${CHART_W - PAD_RIGHT}" y2="${y.toFixed(1)}"/>
          <text class="hrc-ylabel" x="${PAD_LEFT - 5}" y="${(y + 3).toFixed(1)}"
                text-anchor="end">${_axisLabel(value)}</text>
        `;
      })
      .join("");
  }

  _chart(nights, goal) {
    const max = this._distanceMax(nights, goal);
    const average =
      nights.reduce((sum, n) => sum + (Number.isFinite(n.distance) ? n.distance : 0), 0) /
      nights.length;

    const lines = Object.keys(OVERLAYS)
      .filter((name) => this._overlays[name])
      .map((name) => this._overlayLine(nights, name))
      .join("");

    return `
      <svg class="hrc-chart" viewBox="0 0 ${CHART_W} ${CHART_H}" role="img"
           aria-label="${t(this._hass, "running.distance")}">
        ${this._yAxis(max)}
        ${this._bars(nights, max)}
        ${this._rule(average, max, "hrc-rule-avg")}
        ${this._rule(goal, max, "hrc-rule-goal")}
        ${lines}
        ${this._sessionLabels(nights, max)}
      </svg>
    `;
  }

  _legend(goal, nights) {
    const goalText =
      goal > 0
        ? `<span class="hrc-legend-item"><i class="hrc-swatch hrc-swatch-goal"></i>${t(
            this._hass,
            "running.goal"
          )} ${fmtNumber(this._hass, goal, 1, "km")}</span>`
        : "";
    // Only explained when a number is actually on a bar - nights recorded
    // before session counting existed carry none.
    const sessionsText = nights.some((n) => Number.isFinite(n.sessions) && n.sessions > 0)
      ? `<span class="hrc-legend-item"><i class="hrc-swatch hrc-swatch-sessions"></i>${t(
          this._hass,
          "running.sessions"
        )}</span>`
      : "";
    return `
      <div class="hrc-legend">
        <span class="hrc-legend-item"><i class="hrc-swatch hrc-swatch-avg"></i>${t(
          this._hass,
          "running.average"
        )}</span>
        ${goalText}
        ${sessionsText}
      </div>
    `;
  }

  _toggles() {
    return `
      <div class="hrc-toggles">
        ${Object.entries(OVERLAYS)
          .map(
            ([name, spec]) => `
            <button class="hrc-toggle${this._overlays[name] ? " hrc-toggle-on" : ""}"
                    data-overlay="${name}" type="button"
                    aria-pressed="${this._overlays[name] ? "true" : "false"}">
              <i class="hrc-swatch" style="background: ${spec.color}"></i>
              ${t(this._hass, spec.label)}
            </button>`
          )
          .join("")}
      </div>
    `;
  }

  /**
   * Says so while the week is still filling up.
   *
   * A chart with two bars and a couple of lone dots is the correct
   * rendering of two nights of data, but it looks identical to a broken
   * one. The card only earns its keep at seven bars, and until then it
   * should say which of the two it is.
   */
  _collecting(nights) {
    const closed = nights.filter((n) => !n.live).length;
    if (closed >= NIGHTS_ON_CHART - 1) return "";
    return `<div class="hrc-collecting">${t(this._hass, "running.collecting", {
      count: closed,
    })}</div>`;
  }

  _records(attrs) {
    const bestKm = _num(attrs.best_night_km);
    const fastest = _num(attrs.lifetime_max_speed_kmh);
    const none = t(this._hass, "running.noRecord");

    const cell = (labelKey, value, dateIso) => `
      <div class="hrc-record">
        <span class="hrc-record-label">${t(this._hass, labelKey)}</span>
        <span class="hrc-record-value">${value}</span>
        <span class="hrc-record-date">${dateIso ? fmtDate(this._hass, dateIso) : ""}</span>
      </div>
    `;

    return `
      <div class="hrc-section-label">${t(this._hass, "running.records")}</div>
      <div class="hrc-records">
        ${cell(
          "running.bestNight",
          bestKm === null ? none : fmtNumber(this._hass, bestKm, 2, "km"),
          bestKm === null ? null : attrs.best_night_date
        )}
        ${cell(
          "running.fastest",
          fastest === null ? none : fmtNumber(this._hass, fastest, 1, "km/h"),
          fastest === null ? null : attrs.lifetime_max_speed_date
        )}
      </div>
    `;
  }

  _render() {
    if (!this._hass || !this._root || !this._config) return;

    const state = this._hass.states[this._config.entity];
    if (!state) {
      this._errorEl.textContent = t(this._hass, "common.notFound", {
        entity: this._config.entity,
      });
      this._errorEl.hidden = false;
      this._bodyEl.innerHTML = "";
      return;
    }
    this._errorEl.hidden = true;

    const attrs = state.attributes || {};
    applyFur(this._root, coatColor(state));

    const nights = this._nights(attrs);
    const goal = _num(attrs.min_distance_km) || 0;
    const weekTotal = nights.reduce(
      (sum, n) => sum + (Number.isFinite(n.distance) ? n.distance : 0),
      0
    );

    const title =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._config.entity.match(ENTITY_PATTERN)[1].replace(/_/g, " ");

    this._bannerEl.innerHTML = renderCardHeader({
      logoSvg: LOGO_RUNNING_SVG,
      title: String(title).toUpperCase(),
      subtitle: t(this._hass, "running.subtitle"),
      share: { buttonLabel: t(this._hass, "share.button") },
      badgeHtml: nights.length
        ? `<span class="hf-badge">${t(this._hass, "running.weekTotal", {
            value: fmtNumber(this._hass, weekTotal, 1, "km"),
          })}</span>`
        : "",
    });

    this._bodyEl.innerHTML = nights.length
      ? `
        ${this._chart(nights, goal)}
        ${this._legend(goal, nights)}
        ${this._toggles()}
        ${this._collecting(nights)}
        ${this._records(attrs)}
      `
      : `
        <div class="hrc-empty">${t(this._hass, "running.empty")}</div>
        ${this._records(attrs)}
      `;
  }
}

/** Number or null - attributes arrive as strings, nulls and undefineds. */
function _num(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/** Axis labels stay short: "0", "2.5", "10" rather than "10.00". */
function _axisLabel(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

HamsterRunningCard.styles = `
  ${HEADER_STYLES}
  ${SHARE_STYLES}

  ha-card {
    padding: 0;
    overflow: hidden;
    container-type: inline-size;
  }
  .hrc-root {
    position: relative;
  }
  .hrc-banner {
    padding: 14px 16px;
    background: linear-gradient(135deg, #1f4e5f, #2a7f8f);
  }
  .hrc-body {
    padding: 12px 14px 14px;
  }
  .hrc-error {
    margin: 12px;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(228, 92, 92, 0.14);
    color: #c0392b;
    font-size: 0.9em;
  }
  .hrc-empty {
    padding: 14px 4px;
    font-size: 0.88em;
    line-height: 1.45;
    color: var(--secondary-text-color);
  }
  /* height: auto lets the viewBox's own ratio set the height, which is
     what keeps the scaling uniform - the dots stay round and the axis
     labels stay legible. max-height stops a very wide card from turning
     a 3:1 chart into a very tall one; past that point it simply centres
     itself instead of growing further. */
  .hrc-chart {
    width: 100%;
    height: auto;
    max-height: 190px;
    display: block;
    overflow: visible;
  }
  .hrc-bar {
    fill: var(--hf-fur, #D48C46);
  }
  /* The night still running: outlined rather than filled, so a window
     that is three hours old doesn't read as a short night. */
  .hrc-bar-live {
    fill: transparent;
    stroke: var(--hf-fur, #D48C46);
    stroke-width: 1.5;
    stroke-dasharray: 3 2;
  }
  .hrc-xlabel-live {
    font-weight: 700;
    fill: var(--primary-text-color);
  }
  .hrc-collecting {
    margin-top: 8px;
    font-size: 0.74em;
    line-height: 1.4;
    color: var(--secondary-text-color);
  }
  .hrc-grid {
    stroke: var(--divider-color, #e0e0e0);
    stroke-width: 1;
    opacity: 0.55;
  }
  .hrc-ylabel,
  .hrc-xlabel {
    fill: var(--secondary-text-color);
    font-size: 9px;
    font-family: inherit;
  }
  /* Sits on the bar itself, so it needs to read against the coat colour
     rather than against the card background. */
  .hrc-sessions {
    fill: #ffffff;
    font-size: 9px;
    font-weight: 700;
    font-family: inherit;
    /* Outlined in the bar's own colour and painted stroke-first, so a
       line crossing the bar top cannot cut the digit in half. */
    stroke: var(--hf-fur, #D48C46);
    stroke-width: 2.5;
    paint-order: stroke;
  }
  .hrc-sessions-live {
    fill: var(--hf-fur-dark, #8a5a24);
    stroke: var(--card-background-color, #fff);
  }
  .hrc-rule-goal {
    stroke: #2a9d8f;
    stroke-width: 1.5;
    stroke-dasharray: 5 3;
  }
  .hrc-rule-avg {
    stroke: var(--secondary-text-color);
    stroke-width: 1.2;
    stroke-dasharray: 2 3;
    opacity: 0.8;
  }
  .hrc-overlay {
    fill: none;
    stroke-width: 2;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .hrc-legend,
  .hrc-toggles {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 12px;
    margin-top: 8px;
  }
  .hrc-legend {
    font-size: 0.74em;
    color: var(--secondary-text-color);
  }
  .hrc-legend-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .hrc-swatch {
    width: 10px;
    height: 3px;
    border-radius: 2px;
    flex-shrink: 0;
    background: currentColor;
  }
  .hrc-swatch-goal {
    background: #2a9d8f;
  }
  .hrc-swatch-avg {
    background: var(--secondary-text-color);
  }
  .hrc-swatch-sessions {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    background: var(--hf-fur, #D48C46);
  }
  .hrc-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 999px;
    border: 1px solid var(--divider-color, #e0e0e0);
    background: transparent;
    color: var(--secondary-text-color);
    font-family: inherit;
    font-size: 0.74em;
    font-weight: 700;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
  }
  .hrc-toggle-on {
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.16));
    color: var(--primary-text-color);
  }
  .hrc-toggle:focus-visible {
    outline: 2px solid var(--primary-color, #03a9f4);
    outline-offset: 2px;
  }
  .hrc-section-label {
    margin-top: 14px;
    font-size: 0.68em;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .hrc-records {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 6px;
  }
  .hrc-record {
    flex: 1 1 130px;
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 8px 10px;
    border-radius: 12px;
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.1));
  }
  .hrc-record-label {
    font-size: 0.68em;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .hrc-record-value {
    font-size: 1.05em;
    font-weight: 800;
    color: var(--primary-text-color);
  }
  .hrc-record-date {
    font-size: 0.72em;
    color: var(--secondary-text-color);
  }

  @container (max-width: 380px) {
    /* Weekday labels and axis numbers are the first thing to get tight
       on a narrow card, and they scale with the chart rather than with
       the page, so they need their own nudge. */
    .hrc-ylabel,
    .hrc-xlabel {
      font-size: 10px;
    }
  }
`;

customElements.define("hamster-running-card", HamsterRunningCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-running-card",
  name: t(null, "running.pickerName"),
  description: t(null, "running.pickerDescription"),
  // Renders a live preview in the "Add card" picker using getStubConfig()
  // below, rather than a bundled static image - it can't go stale and
  // needs no asset in the repo.
  preview: true,
  // Offers this card when the user adds a card by entity (HA 2026.6+).
  // Older versions never call it, so no version gate is needed.
  getEntitySuggestion: (hass, entityId) => {
    const entity = healthScoreEntityFor(hass, entityId);
    return entity ? { config: { type: "custom:hamster-running-card", entity } } : null;
  },
});

const runningEditorSchema = memoizedEditorSchema((hass) => [
  {
    name: "entity",
    required: true,
    selector: healthScoreEntitySelector(hass),
  },
  { name: "title", selector: { text: {} } },
]);

class HamsterRunningCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (item) =>
        item.name === "entity"
          ? t(this._hass, "common.entityPicker")
          : t(this._hass, "common.optionalTitle");
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: ev.detail.value },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = runningEditorSchema(this._hass);
    this._form.data = this._config;
  }
}

customElements.define("hamster-running-card-editor", HamsterRunningCardEditor);
