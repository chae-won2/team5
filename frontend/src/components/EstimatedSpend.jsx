import { useI18n } from "../i18n.js";
import { formatEstimatedSpend } from "../locale.js";

export default function EstimatedSpend({ amount }) {
  const { locale } = useI18n();
  const text = formatEstimatedSpend(locale, amount);
  return text ? <span className="estimated-spend">{text}</span> : null;
}
