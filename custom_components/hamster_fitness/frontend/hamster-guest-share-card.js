/**
 * Hamster Fitness: Guest Access
 *
 * Turns `switch.<hamster>_guest_share` on or off and, while it's on,
 * shows the resulting link as a QR code plus a copy button - the point
 * of a share link is handing it to someone else, and a bare URL string
 * is a bad way to do that from a phone (see #147).
 *
 * The switch entity is the actual state - this card is a friendlier
 * surface for it, not a second source of truth. Its `guest_path`
 * attribute is just the path - this card builds the actual URL from
 * window.location.origin, deliberately not from anything Home Assistant
 * itself thinks its address is (see switch.py for why).
 *
 * Config:
 *   type: custom:hamster-guest-share-card
 *   entity: sensor.hamster_taco_health_score   # required - same as the other cards
 *   title: Taco                                 # optional - defaults to the device name
 */

import {
  applyFur,
  coatColor,
  deviceDisplayName,
  healthScoreEntityFor,
  healthScoreEntitySelector,
  memoizedEditorSchema,
  siblingEntityId,
  t,
} from "./hamster-fitness-shared.js?v=22";

const HEALTH_SCORE_SUFFIX = "_health_score";
const ENTITY_PATTERN = /^sensor\.(.+)_health_score$/;

class HamsterGuestShareCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error(
        t(null, "common.needEntity", { card: "hamster-guest-share-card" })
      );
    }
    if (!config.entity.match(ENTITY_PATTERN)) {
      throw new Error(
        t(null, "common.wrongEntity", { card: "hamster-guest-share-card" })
      );
    }
    this._config = { ...config };
    this._ensureSkeleton();
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
    return document.createElement("hamster-guest-share-card-editor");
  }

  static getStubConfig(hass, entities) {
    const match = (entities || []).find((id) => ENTITY_PATTERN.test(id));
    return { entity: match || "sensor.hamster_taco_health_score" };
  }

  _ensureSkeleton() {
    if (this._root) return;

    this.innerHTML = `
      <ha-card>
        <div class="hgs-root">
          <div class="hgs-error" hidden></div>
          <div class="hgs-body" hidden>
            <div class="hgs-head">
              <div class="hgs-icon">🔗</div>
              <div class="hgs-head-text">
                <div class="hgs-title"></div>
                <div class="hgs-subtitle"></div>
              </div>
              <button class="hgs-switch" type="button" role="switch" aria-label=""></button>
            </div>
            <div class="hgs-panel"></div>
          </div>
        </div>
      </ha-card>
      <style>${HamsterGuestShareCard.styles}</style>
    `;

    this._root = this.querySelector(".hgs-root");
    this._errorEl = this.querySelector(".hgs-error");
    this._bodyEl = this.querySelector(".hgs-body");
    this._titleEl = this.querySelector(".hgs-title");
    this._subtitleEl = this.querySelector(".hgs-subtitle");
    this._switchEl = this.querySelector(".hgs-switch");
    this._panelEl = this.querySelector(".hgs-panel");

    this._switchEl.addEventListener("click", () => this._toggle());
    this._panelEl.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-action='copy']")) this._copyLink();
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

  _toggle() {
    if (!this._hass) return;
    const share = this._entity("guest_share");
    const isOn = share && share.state === "on";
    this._hass.callService("switch", isOn ? "turn_off" : "turn_on", {
      entity_id: this._entityId("guest_share"),
    });
  }

  _shareUrl() {
    const share = this._entity("guest_share");
    const path = share && share.attributes.guest_path;
    // Built from wherever this card itself was loaded from, not a
    // server-computed URL - see HamsterGuestShareSwitch.extra_state_attributes
    // in switch.py for why (a stale/unused external_url reported live).
    return path ? window.location.origin + path : null;
  }

  async _copyLink() {
    const url = this._shareUrl();
    if (!url) return;

    const button = this._panelEl.querySelector("[data-action='copy']");
    const label = button.querySelector(".hgs-copy-label");
    const original = label.textContent;
    const flash = (text, ok) => {
      label.textContent = text;
      button.classList.toggle("hgs-copy-done", ok);
      setTimeout(() => {
        label.textContent = original;
        button.classList.remove("hgs-copy-done");
      }, 1600);
    };

    try {
      await navigator.clipboard.writeText(url);
      flash(t(this._hass, "guestShare.copied"), true);
    } catch {
      // No clipboard permission/secure context (e.g. plain HTTP) - select
      // the text so at least a manual copy still works.
      const urlEl = this._panelEl.querySelector(".hgs-url");
      if (urlEl) {
        const range = document.createRange();
        range.selectNodeContents(urlEl);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
      flash(original, false);
    }
  }

  /**
   * Encodes `url` as an SVG QR code and caches the result, keyed by URL -
   * `_render()` embeds the cache synchronously so the code never has a
   * moment on screen where it's missing (see below), and this is the
   * only place that fills the cache in.
   *
   * `_pendingQrUrl` guards against a slow first encode (the dynamic
   * `import()` below, one time only - the module itself is cached after
   * that) landing after the panel has moved on to a different URL, e.g.
   * the switch got flipped off and back on again before the first one
   * finished: only inject if this is still the URL anyone asked for.
   */
  async _renderQr(url) {
    this._pendingQrUrl = url;
    if (!this._qrModule) {
      this._qrModule = import("./vendor/qrcode.js");
    }
    const { default: qrcode } = await this._qrModule;
    const qr = qrcode(0, "H"); // 'H': ~30% error correction - room for the centre mark
    qr.addData(url);
    qr.make();
    const svg = qr.createSvgTag({ cellSize: 4, margin: 4, scalable: true });
    this._qrCache = { url, svg };
    if (this._pendingQrUrl === url) {
      const holder = this._panelEl.querySelector(".hgs-qr");
      if (holder) holder.innerHTML = svg;
    }
  }

  _sharePanelHtml(url, name) {
    const cachedSvg =
      this._qrCache && this._qrCache.url === url ? this._qrCache.svg : "";
    return `
      <div class="hgs-share">
        <div class="hgs-qr" aria-hidden="true">${cachedSvg}</div>
        <div class="hgs-share-text">
          <div class="hgs-link-row">
            <span class="hgs-url">${url}</span>
            <button class="hgs-copy" data-action="copy" type="button">
              <span class="hgs-copy-label">${t(this._hass, "guestShare.copy")}</span>
            </button>
          </div>
          <p class="hgs-hint">${t(this._hass, "guestShare.onHint", { name })}</p>
        </div>
      </div>
    `;
  }

  _render() {
    if (!this._hass || !this._root || !this._config) return;

    const healthScore = this._entity("health_score");
    const share = this._entity("guest_share");

    if (!healthScore || !share) {
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

    const name =
      this._config.title ||
      deviceDisplayName(this._hass, this._config.entity) ||
      this._config.entity.match(ENTITY_PATTERN)[1];

    this._titleEl.textContent = t(this._hass, "guestShare.title");
    this._subtitleEl.textContent = name;

    const isOn = share.state === "on";
    this._switchEl.setAttribute("aria-checked", String(isOn));
    this._switchEl.classList.toggle("hgs-switch-on", isOn);

    const url = this._shareUrl();

    // Home Assistant calls `set hass()` on every state change anywhere in
    // the instance, not just this hamster's - skipping a rebuild when
    // nothing this card actually shows has changed avoids two problems
    // at once: the copy button's "done" flash getting wiped by an
    // unrelated update mid-flash, and (the reported bug) the QR code
    // being visible for one render and gone on the very next, because
    // that next render rebuilt the panel's HTML from scratch with an
    // empty `.hgs-qr` div and had no reason to think the async encode
    // needed running again.
    const signature = `${isOn}|${url}|${name}`;
    if (this._lastSignature === signature) return;
    this._lastSignature = signature;

    if (!isOn || !url) {
      this._panelEl.innerHTML = `<p class="hgs-hint">${t(this._hass, "guestShare.offHint", { name })}</p>`;
      return;
    }

    this._panelEl.innerHTML = this._sharePanelHtml(url, name);
    if (!this._qrCache || this._qrCache.url !== url) {
      this._renderQr(url);
    }
  }

  static styles = `
    .hgs-root {
      padding: 16px 18px 18px;
      /* Fallbacks only - applyFur() (hamster-fitness-shared.js) always
         overrides these inline with the hamster's real fur colour. */
      --hf-fur: #D48C46;
      --hf-fur-light: #e0a869;
      --hf-fur-dark: #7f5429;
    }
    .hgs-error {
      padding: 12px 4px;
      color: var(--error-color, #db4437);
      font-size: 0.9em;
    }
    .hgs-head {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .hgs-icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: color-mix(in srgb, var(--hf-fur) 22%, transparent);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.1em;
      flex-shrink: 0;
    }
    .hgs-head-text { flex: 1; min-width: 0; }
    .hgs-title {
      font-weight: 700;
      font-size: 1.05em;
      color: var(--primary-text-color);
    }
    .hgs-subtitle {
      font-size: 0.8em;
      color: var(--secondary-text-color);
      margin-top: 1px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .hgs-switch {
      position: relative;
      width: 46px;
      height: 27px;
      flex-shrink: 0;
      border-radius: 999px;
      border: none;
      background: var(--divider-color, #e0e0e0);
      cursor: pointer;
      transition: background 0.2s ease;
      padding: 0;
    }
    .hgs-switch::after {
      content: "";
      position: absolute;
      top: 3px; left: 3px;
      width: 21px; height: 21px;
      border-radius: 50%;
      background: #fff;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
      transition: transform 0.2s ease;
    }
    .hgs-switch-on { background: var(--hf-fur); }
    .hgs-switch-on::after { transform: translateX(19px); }
    .hgs-panel {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .hgs-hint {
      margin: 0;
      font-size: 0.85em;
      color: var(--secondary-text-color);
      line-height: 1.5;
    }
    .hgs-share {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 16px;
      align-items: center;
    }
    @media (max-width: 380px) {
      .hgs-share { grid-template-columns: minmax(0, 1fr); }
    }
    .hgs-qr {
      width: 104px;
      height: 104px;
      flex-shrink: 0;
      border-radius: 12px;
      overflow: hidden;
      background: #fff;
      padding: 6px;
      box-sizing: border-box;
    }
    .hgs-qr svg { display: block; width: 100%; height: 100%; }
    .hgs-share-text { min-width: 0; }
    .hgs-link-row {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      background: var(--secondary-background-color, rgba(127, 127, 127, 0.1));
      border-radius: 10px;
      padding: 8px 10px;
    }
    .hgs-url {
      font-family: var(--code-font-family, ui-monospace, monospace);
      font-size: 0.78em;
      color: var(--secondary-text-color);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
      min-width: 0;
    }
    .hgs-copy {
      font-family: inherit;
      font-size: 0.82em;
      font-weight: 700;
      border: none;
      background: var(--hf-fur);
      color: #2b1e10;
      padding: 7px 12px;
      border-radius: 8px;
      cursor: pointer;
      white-space: nowrap;
      flex-shrink: 0;
      transition: background 0.15s ease, transform 0.1s ease;
    }
    .hgs-copy:hover { background: var(--hf-fur-light); }
    .hgs-copy:active { transform: scale(0.96); }
    /* Compound selector (not just .hgs-copy-done) so this ties :hover's
       specificity instead of losing to it - the cursor is still sitting
       on the button right after the click that triggered "done" in the
       first place, so :hover is essentially always active exactly when
       this needs to show. */
    .hgs-copy.hgs-copy-done,
    .hgs-copy.hgs-copy-done:hover {
      background: #4caf50;
      color: #fff;
    }
    .hgs-share-text .hgs-hint { margin-top: 10px; }
  `;
}

customElements.define("hamster-guest-share-card", HamsterGuestShareCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hamster-guest-share-card",
  name: t(null, "guestShare.pickerName"),
  description: t(null, "guestShare.pickerDescription"),
  preview: true,
  getEntitySuggestion: (hass, entityId) => {
    const entity = healthScoreEntityFor(hass, entityId);
    return entity
      ? { config: { type: "custom:hamster-guest-share-card", entity } }
      : null;
  },
});

const guestShareEditorSchema = memoizedEditorSchema((hass) => [
  { name: "entity", required: true, selector: healthScoreEntitySelector(hass) },
  { name: "title", selector: { text: {} } },
]);

const GUEST_SHARE_EDITOR_LABELS = {
  entity: "common.entityPicker",
  title: "common.optionalTitle",
};

class HamsterGuestShareCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
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
        GUEST_SHARE_EDITOR_LABELS[schema.name]
          ? t(this._hass, GUEST_SHARE_EDITOR_LABELS[schema.name])
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
    this._form.schema = guestShareEditorSchema(this._hass);
    this._form.data = this._config;
  }
}

customElements.define(
  "hamster-guest-share-card-editor",
  HamsterGuestShareCardEditor
);
