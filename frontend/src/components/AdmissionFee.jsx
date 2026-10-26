import { useI18n } from "../i18n.js";

export default function AdmissionFee({ place }) {
  const { locale, t } = useI18n();
  if (place.category !== "관광명소") return null;
  const status = place.admission_fee_status;
  let text;
  if (status === "free") text = t("admissionFree");
  else if (status === "conditional") text = t("admissionConfirm");
  else if (status === "paid" && typeof place.admission_fee_krw === "number" && Number.isFinite(place.admission_fee_krw)) {
    const amount = new Intl.NumberFormat(locale).format(place.admission_fee_krw);
    text = t("admissionAdult", { amount });
  }
  return text ? <span className="estimated-spend">{text}</span> : null;
}
