/**
 * Shared helpers for the Hamster Fitness card family
 * (hamster-fitness-card.js, hamster-day-night-card.js). Split out so the
 * entity/device lookup logic - fixed once already for non-English Home
 * Assistant installs (see siblingEntityId() below) - exists in exactly
 * one place instead of being duplicated across card files.
 */

export const HAMSTER_PREFIX = /^hamster_/;

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
