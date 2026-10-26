import { useI18n } from "../i18n.js";

export default function PlaceNameSupplement({ place, className }) {
  const { locale, t } = useI18n();
  if (locale === "ko") return null;
  const official = place.official_names?.[locale] ?? (!place.official_names ? place.official_name : "");
  const name = official || place.romanized_name;
  if (!name || name === place.name) return null;
  return <span className={className}>{name}{!official && <small> · {t("romanizedName")}</small>}</span>;
}
