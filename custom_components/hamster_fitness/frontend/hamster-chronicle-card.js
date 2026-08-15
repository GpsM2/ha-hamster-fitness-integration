/**
 * Hamster Fitness: Chronicle
 *
 * Every hamster that ever lived in this Home Assistant, in one list -
 * the ones currently set up and the ones long gone, each in its own coat
 * colour with move-in and move-out dates.
 *
 * The two halves come from different places, because they have to:
 *
 * - Current hamsters (including departed ones whose config entry still
 *   exists) are discovered through the entity registry, the same way the
 *   ranking card does it - platform "hamster_fitness", translation_key
 *   "lifetime_distance" - so it works whatever language the entity_ids
 *   ended up in, and needs no configuration.
 * - Hamsters whose config entry has since been deleted have no entities
 *   left to find. Those come from the lifetime archive, fetched once via
 *   the `hamster_fitness/history` WebSocket command (see archive.py).
 *   If that command is unavailable, the card simply shows the live half.
 *
 * Config:
 *   type: custom:hamster-chronicle-card
 *   title: Hamster-Chronik    # optional
 *   columns:                  # optional - which stats to show per row
 *     - distance
 *     - top_speed
 *     - days
 *     - score
 */

import {
  DEFAULT_FUR,
  HEADER_STYLES,
  daysBetween,
  fmtDate,
  fmtNumber,
  isValidHex,
  renderCardHeader,
  shade,
  siblingEntityId,
  deviceDisplayName,
  t,
  HAMSTER_PREFIX,
} from "./hamster-fitness-shared.js?v=13";

const LIFETIME_DISTANCE_PATTERN = /^sensor\.(.+)_lifetime_distance$/;

const ALL_COLUMNS = ["distance", "top_speed", "days", "score"];
const DEFAULT_COLUMNS = ["distance", "days"];

// Translation keys (see hamster-fitness-shared.js), resolved per render.
const COLUMN_LABELS = {
  distance: "chronicle.colDistance",
  top_speed: "chronicle.colTopSpeed",
  days: "chronicle.colDays",
  score: "chronicle.colScore",
};

// Mirrors const.py's BREEDS. Breeds the integration doesn't know show no
// label at all rather than a raw key.
const BREED_KEYS = new Set([
  "golden",
  "teddy",
  "winter_white",
  "campbell",
  "roborovski",
  "chinese",
  "other",
]);
const BREEDS = [...BREED_KEYS];
const BREED_OTHER = "other";

// Mirrors const.py's COAT_COLORS/COAT_COLOR_HEX.
const COAT_COLORS = ["golden_brown", "silver_grey", "cream_sand", "black"];

// Small hamster silhouette, tinted per row with that hamster's own colour.
const HAMSTER_MARK = `
<svg viewBox="0 0 48 48" width="30" height="30" aria-hidden="true">
  <ellipse cx="24" cy="30" rx="14" ry="11" fill="var(--row-fur)" stroke="var(--row-fur-dark)" stroke-width="1.2"/>
  <ellipse cx="15" cy="34" rx="4" ry="2.8" fill="var(--row-fur)" stroke="var(--row-fur-dark)" stroke-width="1"/>
  <ellipse cx="33" cy="34" rx="4" ry="2.8" fill="var(--row-fur)" stroke="var(--row-fur-dark)" stroke-width="1"/>
  <circle cx="24" cy="17" r="9.5" fill="var(--row-fur-light)" stroke="var(--row-fur-dark)" stroke-width="1.2"/>
  <circle cx="17" cy="10" r="2.8" fill="var(--row-fur)" stroke="var(--row-fur-dark)" stroke-width="1"/>
  <circle cx="31" cy="10" r="2.8" fill="var(--row-fur)" stroke="var(--row-fur-dark)" stroke-width="1"/>
  <circle cx="20" cy="16" r="1.4" fill="#3a2a1a"/>
  <circle cx="28" cy="16" r="1.4" fill="#3a2a1a"/>
  <ellipse cx="24" cy="20" rx="2.2" ry="1.6" fill="#f4d9c6"/>
</svg>
`;

const LOGO_CHRONICLE = `
<svg viewBox="0 0 48 48" width="34" height="34" aria-hidden="true">
  <rect x="8" y="7" width="32" height="34" rx="4" fill="#ffffff" opacity="0.92"/>
  <rect x="8" y="7" width="9" height="34" rx="4" fill="#C19A6B"/>
  <g stroke="#8B5A2B" stroke-width="2" stroke-linecap="round" opacity="0.65">
    <line x1="22" y1="16" x2="35" y2="16"/>
    <line x1="22" y1="23" x2="35" y2="23"/>
    <line x1="22" y1="30" x2="31" y2="30"/>
  </g>
</svg>
`;

class HamsterChronicleCard extends HTMLElement {
  setConfig(config) {
    const columns = Array.isArray(config && config.columns)
      ? config.columns.filter((name) => ALL_COLUMNS.includes(name))
      : DEFAULT_COLUMNS;
    this._config = { ...(config || {}), columns };

    if (!this._root) {
      this.innerHTML = `
        <ha-card>
          <div class="hch-root">
            <div class="hch-banner"></div>
            <div class="hch-body"></div>
            <div class="hch-modal-host"></div>
          </div>
        </ha-card>
        <style>${HamsterChronicleCard.styles}</style>
      `;
      this._root = this.querySelector(".hch-root");
      this._bannerEl = this.querySelector(".hch-banner");
      this._bodyEl = this.querySelector(".hch-body");
      this._modalHost = this.querySelector(".hch-modal-host");

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
        if (ev.target.closest(".hch-modal-host")) return;
        if (ev.target.closest("[data-action='add-past']")) {
          this._openPastDialog();
          return;
        }
        const manualTarget = ev.target.closest("[data-manual-entry]");
        if (manualTarget) {
          this._openPastDialog(manualTarget.dataset.manualEntry);
          return;
        }
        const target = ev.target.closest("[data-entity]");
        if (target) openMoreInfo(target);
      });
      this._root.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        if (ev.target.closest(".hch-modal-host")) return;
        if (ev.target.closest("[data-action='add-past']")) {
          ev.preventDefault();
          this._openPastDialog();
          return;
        }
        const manualTarget = ev.target.closest("[data-manual-entry]");
        if (manualTarget) {
          ev.preventDefault();
          this._openPastDialog(manualTarget.dataset.manualEntry);
          return;
        }
        const target = ev.target.closest("[data-entity]");
        if (!target) return;
        ev.preventDefault();
        openMoreInfo(target);
      });

      // Same overlay pattern as the health-score card's pillar modal: a
      // plain absolutely-positioned div rather than <ha-dialog>, so the
      // card keeps working in the dashboard editor preview.
      this._modalHost.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-action='save-past']")) {
          this._savePastEntry();
          return;
        }
        if (ev.target.closest("[data-action='delete-past']")) {
          this._confirmingDelete = true;
          this._renderPastDialogFooter();
          return;
        }
        if (ev.target.closest("[data-action='cancel-delete-past']")) {
          this._confirmingDelete = false;
          this._renderPastDialogFooter();
          return;
        }
        if (ev.target.closest("[data-action='confirm-delete-past']")) {
          this._deletePastEntry();
          return;
        }
        if (
          ev.target.closest("[data-close]") ||
          ev.target === this._modalHost.firstElementChild
        ) {
          this._closePastDialog();
        }
      });
      this._onKeyDown = (ev) => {
        if (ev.key === "Escape" && this._modalHost.hasChildNodes()) {
          this._closePastDialog();
        }
      };
    }
    this._render();
  }

  connectedCallback() {
    if (this._onKeyDown) document.addEventListener("keydown", this._onKeyDown);
  }

  disconnectedCallback() {
    if (this._onKeyDown) document.removeEventListener("keydown", this._onKeyDown);
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._loadArchive();
    // The add-past dialog's <ha-form> needs a live hass reference of its
    // own to render at all - see _openAddPastDialog().
    if (this._addPastForm) this._addPastForm.hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("hamster-chronicle-card-editor");
  }

  static getStubConfig() {
    return { title: t(null, "chronicle.title"), columns: DEFAULT_COLUMNS };
  }

  /**
   * Fetches archived hamsters once per card instance. Deliberately
   * tolerant: an older integration version (or a Home Assistant that has
   * not registered the command yet) just means the archived half stays
   * empty, rather than the whole card failing.
   */
  async _loadArchive() {
    if (!this._hass || typeof this._hass.callWS !== "function") return;
    try {
      const result = await this._hass.callWS({ type: "hamster_fitness/history" });
      this._archive = (result && result.hamsters) || [];
    } catch (err) {
      this._archive = [];
      this._archiveFailed = true;
    }
    this._render();
  }

  _capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  /** Hamsters that still have entities in this Home Assistant. */
  _liveHamsters() {
    const entities = this._hass.entities || {};
    return Object.entries(entities)
      .filter(
        ([, entry]) =>
          entry.platform === "hamster_fitness" &&
          entry.translation_key === "lifetime_distance"
      )
      .map(([id]) => {
        const state = this._hass.states[id];
        const scoreId = siblingEntityId(this._hass, id, "health_score");
        const score = scoreId && this._hass.states[scoreId];
        const speedId = siblingEntityId(this._hass, id, "max_speed_tonight");
        const departureId = siblingEntityId(this._hass, id, "departure_date");
        const departure = departureId && this._hass.states[departureId];
        const departureDate =
          departure && departure.state && departure.state !== "unknown"
            ? departure.state
            : null;
        const attrs = (score && score.attributes) || {};
        const match = id.match(LIFETIME_DISTANCE_PATTERN);
        const slug = match ? match[1].replace(HAMSTER_PREFIX, "") : id;

        return {
          entityId: scoreId || id,
          name: deviceDisplayName(this._hass, id) || this._capitalize(slug),
          breed: attrs.breed,
          breedOther: attrs.breed_other,
          coatHex: isValidHex(attrs.coat_color_hex) ? attrs.coat_color_hex : DEFAULT_FUR,
          acquisitionDate: attrs.acquisition_date,
          departureDate,
          distance: state ? Number(state.state) : NaN,
          topSpeed: speedId && this._hass.states[speedId]
            ? Number(this._hass.states[speedId].state)
            : NaN,
          score: score ? Number(score.state) : NaN,
          archived: false,
        };
      });
  }

  /** Hamsters whose config entry is gone, read from the archive file. */
  _archivedHamsters(liveNames) {
    return (this._archive || [])
      // A hamster that is both archived and still configured would show
      // up twice; the live entry wins, since its numbers keep updating.
      .filter((record) => !liveNames.has(record.name))
      .map((record) => ({
        id: record.id,
        manual: typeof record.id === "string" && record.id.startsWith("manual_"),
        entityId: null,
        name: record.name,
        breed: record.breed,
        breedOther: record.breed_other,
        coatHex: isValidHex(record.coat_color_hex) ? record.coat_color_hex : DEFAULT_FUR,
        acquisitionDate: record.acquisition_date,
        departureDate: record.departure_date,
        distance: Number(record.lifetime_distance_km),
        topSpeed: Number(record.lifetime_max_speed_kmh),
        score: Number(record.final_health_score),
        days: record.days_with_you,
        archived: true,
      }));
  }

  _breedLabel(row) {
    if (row.breed === "other" && row.breedOther) return row.breedOther;
    return BREED_KEYS.has(row.breed) ? t(this._hass, `breed.${row.breed}`) : null;
  }

  _columnValue(row, column) {
    switch (column) {
      case "distance":
        return fmtNumber(this._hass, row.distance, 1, "km");
      case "top_speed":
        return fmtNumber(this._hass, row.topSpeed, 1, "km/h");
      case "days": {
        const days =
          row.days !== undefined && row.days !== null
            ? row.days
            : daysBetween(row.acquisitionDate, row.departureDate);
        return days === null ? "–" : `${days}`;
      }
      case "score":
        return fmtNumber(this._hass, row.score, 0, "%");
      default:
        return "–";
    }
  }

  _row(row) {
    const from = fmtDate(this._hass, row.acquisitionDate);
    const until = fmtDate(this._hass, row.departureDate);
    const periodText = from
      ? until
        ? `${from} \u2013 ${until}`
        : t(this._hass, "chronicle.since", { date: from })
      : row.archived
        ? t(this._hass, "chronicle.unknownPeriod")
        : "";

    const stats = this._config.columns
      .map(
        (column) => `
          <div class="hch-stat">
            <span class="hch-stat-label">${t(this._hass, COLUMN_LABELS[column])}</span>
            <span class="hch-stat-value">${this._columnValue(row, column)}</span>
          </div>
        `
      )
      .join("");

    const clickable = row.entityId
      ? `data-entity="${row.entityId}" tabindex="0" role="button"`
      : row.manual
      ? `data-manual-entry="${row.id}" tabindex="0" role="button" aria-label="${t(this._hass, "chronicle.editPast")}"`
      : "";
    const breed = this._breedLabel(row);

    return `
      <div class="hch-row${row.entityId || row.manual ? " hch-clickable" : ""}${row.departureDate ? " hch-past" : ""}"
           style="--row-fur: ${row.coatHex}; --row-fur-light: ${shade(row.coatHex, 0.18)}; --row-fur-dark: ${shade(row.coatHex, -0.4)}"
           ${clickable}>
        <span class="hch-mark">${HAMSTER_MARK}</span>
        <div class="hch-ident">
          <span class="hch-name">
            <span class="hch-name-text">${row.name}</span>
            ${row.departureDate ? `<span class="hch-tag">${t(this._hass, "chronicle.movedOut")}</span>` : ""}
            ${row.archived ? `<span class="hch-tag hch-tag-archive">${t(this._hass, "chronicle.archived")}</span>` : ""}
          </span>
          <span class="hch-meta">${[breed, periodText].filter(Boolean).join(" · ")}</span>
        </div>
        <div class="hch-stats">${stats}</div>
      </div>
    `;
  }

  /** The raw archive record behind a manually-added row's data-manual-entry id. */
  _findArchiveRecord(entryId) {
    return (this._archive || []).find((record) => record.id === entryId) || null;
  }

  /**
   * A hamster from before this integration existed: no sensors, no
   * device, so no config flow can create it. This is the only way in -
   * a form that writes straight to the lifetime archive via the
   * `hamster_fitness/add_historical_hamster` WebSocket command (see
   * __init__.py), the same store live departures land in.
   *
   * Doubles as the editor for an entry added this way: pass the id from
   * its `data-manual-entry` attribute and the form pre-fills from the
   * matching archive record instead of starting blank.
   */
  _openPastDialog(editEntryId = null) {
    const editRecord = editEntryId ? this._findArchiveRecord(editEntryId) : null;
    this._editingEntryId = editRecord ? editEntryId : null;
    this._confirmingDelete = false;

    const breedOptions = BREEDS.map((value) => ({
      value,
      label: t(this._hass, `breed.${value}`),
    }));
    const coatOptions = COAT_COLORS.map((value) => ({
      value,
      label: t(this._hass, `coatColor.${value}`),
    }));
    const fieldLabels = {
      name: "chronicle.fieldName",
      breed: "chronicle.fieldBreed",
      breed_other: "chronicle.fieldBreedOther",
      coat_color: "chronicle.fieldCoatColor",
      acquisition_date: "chronicle.fieldAcquisitionDate",
      departure_date: "chronicle.fieldDepartureDate",
    };
    const schema = [
      { name: "name", required: true, selector: { text: {} } },
      {
        name: "breed",
        required: true,
        selector: { select: { mode: "dropdown", options: breedOptions } },
      },
      { name: "breed_other", selector: { text: {} } },
      {
        name: "coat_color",
        required: true,
        selector: { select: { mode: "dropdown", options: coatOptions } },
      },
      { name: "acquisition_date", required: true, selector: { date: {} } },
      { name: "departure_date", required: true, selector: { date: {} } },
    ];

    const titleKey = this._editingEntryId ? "chronicle.editPastTitle" : "chronicle.addPastTitle";
    const descKey = this._editingEntryId
      ? "chronicle.editPastDescription"
      : "chronicle.addPastDescription";

    // A card with only a row or two is shorter than this six-field form
    // wants - grow it for the duration of the dialog rather than cram
    // the form into a tiny scrollable box. See _closePastDialog().
    this._root.classList.add("hch-dialog-open");

    this._modalHost.innerHTML = `
      <div class="hch-overlay">
        <div class="hch-modal" role="dialog" aria-modal="true"
             aria-label="${t(this._hass, titleKey)}">
          <div class="hch-modal-head">
            <span class="hch-modal-title">${t(this._hass, titleKey)}</span>
            <button class="hch-modal-close" data-close type="button"
                    aria-label="${t(this._hass, "chronicle.cancel")}">×</button>
          </div>
          <div class="hch-modal-body">
            <p class="hch-modal-desc">${t(this._hass, descKey)}</p>
            <div class="hch-form-host"></div>
            <div class="hch-form-error" hidden></div>
            <div class="hch-modal-footer"></div>
          </div>
        </div>
      </div>
    `;

    this._pastErrorEl = this._modalHost.querySelector(".hch-form-error");
    this._pastData = editRecord
      ? {
          name: editRecord.name,
          breed: editRecord.breed || BREEDS[0],
          breed_other: editRecord.breed_other || "",
          coat_color: editRecord.coat_color || COAT_COLORS[0],
          acquisition_date: editRecord.acquisition_date,
          departure_date: editRecord.departure_date,
        }
      : { breed: BREEDS[0], coat_color: COAT_COLORS[0] };

    this._pastForm = document.createElement("ha-form");
    this._pastForm.hass = this._hass;
    this._pastForm.schema = schema;
    this._pastForm.data = this._pastData;
    this._pastForm.computeLabel = (item) =>
      t(this._hass, fieldLabels[item.name] || item.name);
    this._pastForm.addEventListener("value-changed", (ev) => {
      ev.stopPropagation();
      this._pastData = ev.detail.value;
      this._pastForm.data = this._pastData;
    });
    this._modalHost.querySelector(".hch-form-host").appendChild(this._pastForm);

    this._renderPastDialogFooter();

    const closeButton = this._modalHost.querySelector(".hch-modal-close");
    if (closeButton) closeButton.focus();
  }

  /**
   * Rebuilt on its own (rather than re-running _openPastDialog) so toggling
   * the delete confirmation doesn't tear down and recreate the <ha-form>,
   * which would lose whatever the user has typed.
   */
  _renderPastDialogFooter() {
    const footerEl = this._modalHost.querySelector(".hch-modal-footer");
    if (!footerEl) return;

    // Hidden rather than removed while confirming, so cancelling just
    // un-hides the form with everything the user already typed intact.
    const descEl = this._modalHost.querySelector(".hch-modal-desc");
    const formHostEl = this._modalHost.querySelector(".hch-form-host");
    if (descEl) descEl.hidden = this._confirmingDelete;
    if (formHostEl) formHostEl.hidden = this._confirmingDelete;

    if (this._confirmingDelete) {
      footerEl.innerHTML = `
        <p class="hch-modal-desc">${t(this._hass, "chronicle.deleteConfirmBody")}</p>
        <div class="hch-modal-actions">
          <button class="hch-modal-cancel" data-action="cancel-delete-past" type="button">
            ${t(this._hass, "chronicle.cancel")}
          </button>
          <button class="hch-modal-save hch-modal-danger" data-action="confirm-delete-past" type="button">
            ${t(this._hass, "chronicle.deleteConfirmYes")}
          </button>
        </div>
      `;
      return;
    }

    footerEl.innerHTML = `
      <div class="hch-modal-actions">
        ${
          this._editingEntryId
            ? `<button class="hch-modal-delete" data-action="delete-past" type="button">
                 ${t(this._hass, "chronicle.delete")}
               </button>`
            : ""
        }
        <button class="hch-modal-cancel" data-close type="button">
          ${t(this._hass, "chronicle.cancel")}
        </button>
        <button class="hch-modal-save hch-modal-primary" data-action="save-past" type="button">
          ${t(this._hass, "chronicle.save")}
        </button>
      </div>
    `;
  }

  _closePastDialog() {
    this._root.classList.remove("hch-dialog-open");
    this._modalHost.innerHTML = "";
    this._pastForm = null;
    this._pastData = null;
    this._pastErrorEl = null;
    this._editingEntryId = null;
    this._confirmingDelete = false;
  }

  _showPastError(message) {
    if (!this._pastErrorEl) return;
    this._pastErrorEl.textContent = message;
    this._pastErrorEl.hidden = false;
  }

  async _savePastEntry() {
    if (!this._hass || !this._pastData) return;
    const data = this._pastData;
    const name = (data.name || "").trim();
    const breed = data.breed || BREEDS[0];
    const breedOther = (data.breed_other || "").trim();

    if (!name) {
      this._showPastError(t(this._hass, "chronicle.nameRequired"));
      return;
    }
    if (breed === BREED_OTHER && !breedOther) {
      this._showPastError(t(this._hass, "chronicle.breedOtherRequired"));
      return;
    }
    if (!data.acquisition_date || !data.departure_date) {
      this._showPastError(t(this._hass, "chronicle.datesRequired"));
      return;
    }

    const payload = {
      name,
      breed,
      breed_other: breedOther,
      coat_color: data.coat_color || COAT_COLORS[0],
      acquisition_date: data.acquisition_date,
      departure_date: data.departure_date,
    };

    try {
      const result = await this._hass.callWS(
        this._editingEntryId
          ? {
              type: "hamster_fitness/update_historical_hamster",
              entry_id: this._editingEntryId,
              ...payload,
            }
          : { type: "hamster_fitness/add_historical_hamster", ...payload }
      );
      this._archive = (result && result.hamsters) || this._archive;
      this._closePastDialog();
      this._render();
    } catch (err) {
      this._showPastError(t(this._hass, "chronicle.addPastFailed"));
    }
  }

  async _deletePastEntry() {
    if (!this._hass || !this._editingEntryId) return;
    try {
      const result = await this._hass.callWS({
        type: "hamster_fitness/remove_historical_hamster",
        entry_id: this._editingEntryId,
      });
      this._archive = (result && result.hamsters) || this._archive;
      this._closePastDialog();
      this._render();
    } catch (err) {
      this._confirmingDelete = false;
      this._showPastError(t(this._hass, "chronicle.deleteFailed"));
      this._renderPastDialogFooter();
    }
  }

  _render() {
    if (!this._hass || !this._root || !this._config) return;

    const live = this._liveHamsters();
    const liveNames = new Set(live.map((row) => row.name));
    const rows = [...live, ...this._archivedHamsters(liveNames)].sort((a, b) => {
      // Current hamsters first, then by move-in date, newest first.
      if (!!a.departureDate !== !!b.departureDate) return a.departureDate ? 1 : -1;
      return String(b.acquisitionDate || "").localeCompare(String(a.acquisitionDate || ""));
    });

    this._bannerEl.innerHTML = renderCardHeader({
      logoSvg: LOGO_CHRONICLE,
      title: (this._config.title || t(this._hass, "chronicle.title")).toUpperCase(),
      subtitle: t(this._hass, "chronicle.subtitle"),
      badgeHtml: `
        <span class="hf-badge">${t(this._hass, "chronicle.count", { count: rows.length })}</span>
        <button class="hch-add-btn" data-action="add-past" type="button"
                title="${t(this._hass, "chronicle.addPast")}"
                aria-label="${t(this._hass, "chronicle.addPast")}">+</button>
      `,
    });

    if (rows.length === 0) {
      this._bodyEl.innerHTML = `
        <div class="hch-empty">${t(this._hass, "chronicle.empty")}</div>
      `;
      return;
    }

    this._bodyEl.innerHTML = `
      <div class="hch-rows">${rows.map((row) => this._row(row)).join("")}</div>
      ${
        this._archiveFailed
          ? `<div class="hch-note">${t(this._hass, "chronicle.archiveFailed")}</div>`
          : ""
      }
    `;
  }
}

HamsterChronicleCard.styles = `
  ${HEADER_STYLES}

  ha-card {
    padding: 0;
    overflow: hidden;
    container-type: inline-size;
  }
  .hch-root {
    /* The dialog overlay below is absolutely positioned with inset 0
       and needs this to size against the card, not against whatever
       positioned ancestor happens to sit further up the page. */
    position: relative;
  }
  .hch-root.hch-dialog-open {
    /* A card with only one or two rows is short enough that, without
       this, the six-field "add/edit past hamster" form has to scroll
       inside a cramped box. Growing the card while the dialog is open
       gives it room instead; it shrinks back the moment the dialog
       closes. */
    min-height: 560px;
  }
  .hch-banner {
    padding: 14px 16px;
    background: linear-gradient(135deg, #5c4a3a, #8B5A2B);
  }
  .hch-add-btn {
    flex-shrink: 0;
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.18);
    color: #ffffff;
    font-size: 1.1em;
    line-height: 1;
    cursor: pointer;
    transition: background-color 0.15s ease;
  }
  .hch-add-btn:hover,
  .hch-add-btn:focus-visible {
    background: rgba(255, 255, 255, 0.32);
    outline: none;
  }
  .hch-body {
    padding: 10px 12px 14px;
  }

  /* "Add a past hamster" dialog - same plain-overlay pattern as the
     health-score card's pillar modal (see hamster-fitness-card.js),
     kept local rather than shared since only these two cards need it. */
  .hch-overlay {
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
  .hch-modal {
    width: 100%;
    max-width: 420px;
    max-height: 100%;
    overflow: auto;
    border-radius: 18px;
    background: var(--card-background-color, #fff);
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.32);
    animation: hchModalIn 0.16s ease-out;
  }
  @keyframes hchModalIn {
    from { opacity: 0; transform: translateY(8px) scale(0.98); }
    to { opacity: 1; transform: none; }
  }
  .hch-modal-head {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 12px 14px;
    color: #fff;
    background: linear-gradient(135deg, #5c4a3a, #8B5A2B);
  }
  .hch-modal-title {
    font-weight: 800;
  }
  .hch-modal-close {
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
  .hch-modal-body {
    padding: 14px;
  }
  .hch-modal-desc {
    margin: 0 0 12px;
    font-size: 0.85em;
    color: var(--secondary-text-color);
    line-height: 1.4;
  }
  .hch-form-error {
    margin-top: 10px;
    padding: 8px 10px;
    border-radius: 10px;
    background: rgba(228, 92, 92, 0.14);
    color: #c0392b;
    font-size: 0.85em;
  }
  .hch-modal-actions {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .hch-modal-cancel,
  .hch-modal-save,
  .hch-modal-delete {
    padding: 9px 16px;
    border-radius: 999px;
    border: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    font-family: inherit;
    font-weight: 700;
    font-size: 0.88em;
    cursor: pointer;
  }
  .hch-modal-primary {
    border-color: var(--primary-color, #03a9f4);
    background: var(--primary-color, #03a9f4);
    color: #fff;
  }
  .hch-modal-delete {
    /* Pushes Cancel/Save to the trailing edge while this stays leading,
       without a second flex row just for one button. */
    margin-right: auto;
    border-color: rgba(211, 47, 47, 0.4);
    color: #d32f2f;
  }
  .hch-modal-danger {
    border-color: #d32f2f;
    background: #d32f2f;
    color: #fff;
  }
  .hch-empty,
  .hch-note {
    font-size: 0.85em;
    color: var(--secondary-text-color);
    padding: 8px 4px;
  }
  .hch-rows {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .hch-row {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 9px 8px;
    border-radius: 12px;
    transition: background-color 0.15s ease;
  }
  .hch-past {
    opacity: 0.72;
  }
  .hch-clickable {
    cursor: pointer;
  }
  .hch-clickable:hover,
  .hch-clickable:focus-visible {
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.12));
    outline: none;
  }
  .hch-mark {
    display: flex;
    flex-shrink: 0;
  }
  .hch-ident {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .hch-name {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 6px;
    font-weight: 700;
    color: var(--primary-text-color);
  }
  .hch-name-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
    flex-shrink: 1;
  }
  .hch-tag {
    font-size: 0.62em;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 999px;
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.16));
    color: var(--secondary-text-color);
    flex-shrink: 0;
  }
  .hch-tag-archive {
    background: rgba(139, 90, 43, 0.18);
  }
  .hch-meta {
    font-size: 0.76em;
    color: var(--secondary-text-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hch-stats {
    display: flex;
    gap: 14px;
    flex-shrink: 0;
  }
  .hch-stat {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    line-height: 1.15;
  }
  .hch-stat-label {
    font-size: 0.62em;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .hch-stat-value {
    font-size: 0.98em;
    font-weight: 700;
    color: var(--primary-text-color);
    white-space: nowrap;
  }

  /* A dashboard column is often narrower than the browser window, so this
     has to react to the card's own rendered width, not the viewport's -
     a plain @media query would stay dormant in exactly the layouts where
     the row actually needs to wrap. */
  @container (max-width: 460px) {
    .hch-row {
      flex-wrap: wrap;
    }
    .hch-stats {
      width: 100%;
      justify-content: flex-start;
      gap: 16px;
      padding-left: 41px;
    }
    .hch-stat {
      align-items: flex-start;
    }
  }
`;

customElements.define("hamster-chronicle-card", HamsterChronicleCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-chronicle-card",
  name: t(null, "chronicle.pickerName"),
  description: t(null, "chronicle.pickerDescription"),
});

const CHRONICLE_EDITOR_SCHEMA = [
  { name: "title", selector: { text: {} } },
  {
    name: "columns",
    selector: {
      select: {
        multiple: true,
        mode: "list",
        options: [],
      },
    },
  },
];

const CHRONICLE_EDITOR_LABELS = {
  title: "common.optionalTitle",
  columns: "chronicle.columns",
};

class HamsterChronicleCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { columns: DEFAULT_COLUMNS, ...config };
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
        CHRONICLE_EDITOR_LABELS[schema.name]
          ? t(this._hass, CHRONICLE_EDITOR_LABELS[schema.name])
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

    // The column options carry translated labels, so the schema is built
    // here rather than at module load - `hass` only exists by now.
    const schema = CHRONICLE_EDITOR_SCHEMA.map((entry) =>
      entry.name === "columns"
        ? {
            ...entry,
            selector: {
              select: {
                ...entry.selector.select,
                options: ALL_COLUMNS.map((value) => ({
                  value,
                  label: t(this._hass, COLUMN_LABELS[value]),
                })),
              },
            },
          }
        : entry
    );

    this._form.hass = this._hass;
    this._form.schema = schema;
    this._form.data = this._config;
  }
}

customElements.define("hamster-chronicle-card-editor", HamsterChronicleCardEditor);
