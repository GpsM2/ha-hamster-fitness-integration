/**
 * Shared helpers for the Hamster Fitness card family
 * (hamster-fitness-card.js, hamster-day-night-card.js). Split out so the
 * entity/device lookup logic - fixed once already for non-English Home
 * Assistant installs (see siblingEntityId() below) - exists in exactly
 * one place instead of being duplicated across card files.
 */

export const HAMSTER_PREFIX = /^hamster_/;

export const DEFAULT_FUR = "#D48C46";

/**
 * The card header, shared verbatim by the Day & Night and health-score
 * cards so the two genuinely match instead of drifting apart. Both render
 * it on a coloured banner, hence the light-on-dark styling.
 */
export function renderCardHeader({ logoSvg, title, subtitle, badgeHtml = "" }) {
  return `
    <div class="hf-header">
      <span class="hf-logo">${logoSvg}</span>
      <div class="hf-header-text">
        <span class="hf-title">${title}</span>
        <span class="hf-subtitle">${subtitle}</span>
      </div>
      ${badgeHtml}
    </div>
  `;
}

export const HEADER_STYLES = `
  .hf-header {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 2;
  }
  .hf-logo {
    display: flex;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
  }
  .hf-header-text {
    display: flex;
    flex-direction: column;
    line-height: 1.1;
    min-width: 0;
  }
  .hf-title {
    font-size: 1.55em;
    font-weight: 900;
    letter-spacing: 0.06em;
    color: #ffffff;
    text-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hf-subtitle {
    font-size: 0.78em;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.82);
  }
  .hf-badge {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 11px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.16);
    backdrop-filter: blur(4px);
    font-size: 0.72em;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #ffffff;
    flex-shrink: 0;
  }
  .hf-badge-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  @media (max-width: 460px) {
    .hf-title {
      font-size: 1.3em;
    }
  }
`;

/** Lightens (amount > 0) or darkens (amount < 0) a hex colour. */
export function shade(hex, amount) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((channel) => {
    const target = amount > 0 ? 255 : 0;
    return Math.round(channel + (target - channel) * Math.abs(amount));
  });
  return `rgb(${rgb.join(", ")})`;
}

export function isValidHex(value) {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}

/** Resolves the hamster's coat colour from the health-score attributes. */
export function coatColor(healthScoreState) {
  const hex = healthScoreState && healthScoreState.attributes.coat_color_hex;
  return isValidHex(hex) ? hex : DEFAULT_FUR;
}

/** Applies the coat colour as CSS custom properties on `el`. */
export function applyFur(el, fur) {
  el.style.setProperty("--hf-fur", fur);
  el.style.setProperty("--hf-fur-light", shade(fur, 0.18));
  el.style.setProperty("--hf-fur-dark", shade(fur, -0.4));
  el.style.setProperty("--hf-belly", shade(fur, 0.62));
}

/**
 * Finds a sibling entity on the same device by its translation_key.
 * translation_key is a fixed English string set in the integration's
 * Python code (e.g. "daily_distance") and never changes - unlike
 * entity_id, which Home Assistant generates once from the *translated*
 * name active when the entity was first created, so it can end up in
 * German, French, etc. instead of English. Returns null if the entity/
 * device registry data isn't available yet or there's no match.
 */
export function siblingEntityId(hass, entityId, translationKey) {
  const entities = hass && hass.entities;
  const self = entities && entities[entityId];
  const deviceId = self && self.device_id;
  if (!deviceId) return null;
  for (const [id, entry] of Object.entries(entities)) {
    if (entry.device_id === deviceId && entry.translation_key === translationKey) {
      return id;
    }
  }
  return null;
}

/**
 * Resolves the display title from the device's own name, which is set
 * once from the hamster's actual name and never translated (see
 * hamster_device_info() in coordinator.py) - unlike the entity_id slug,
 * which may be in any language.
 */
export function deviceDisplayName(hass, entityId) {
  const entities = hass && hass.entities;
  const devices = hass && hass.devices;
  const self = entities && entities[entityId];
  const device = self && devices && devices[self.device_id];
  const name = device && (device.name_by_user || device.name);
  return name ? name.replace(/^Hamster\s+/, "") : null;
}
