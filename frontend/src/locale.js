import resources from "./translations.json" with { type: "json" };

export const languages = { ko: "한국어", en: "English", ja: "日本語", "zh-TW": "繁體中文" };
const sourceKeys = Object.fromEntries(Object.values(resources).flatMap((messages) => Object.entries(messages).map(([key, value]) => [value, key])));
sourceKeys["카페·디저트"] = "cafe";

export function translate(locale, key, params = {}) {
  const id = Object.hasOwn(resources.ko, key) ? key : sourceKeys[key];
  let value = resources[locale]?.[id] ?? resources.ko[id] ?? key;
  if (locale === "en" && id === "placeCount" && params.count === 1) value = "{count} stop";
  for (const [name, replacement] of Object.entries(params)) value = value.replaceAll(`{${name}}`, String(replacement));
  return value;
}
export function formatDuration(locale, value) {
  const total = Math.max(0, Math.ceil(value));
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  const parts = [];
  if (hours) parts.push(translate(locale, "hours", { n: hours }));
  if (minutes || !hours) parts.push(translate(locale, "minutes", { n: minutes }));
  return parts.join(" ");
}
export function formatEstimatedSpend(locale, value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "";
  return translate(locale, "estimatedSpendPerPerson", {
    amount: new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value),
  });
}
export { resources };
