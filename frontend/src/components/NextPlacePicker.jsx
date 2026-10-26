import { paymentTagKey } from "../locale.js";
import EstimatedSpend from "./EstimatedSpend";
import { useI18n } from "../i18n.js";
import { useEffect, useRef } from 'react';
import { recordImpression } from '../api';

export default function NextPlacePicker({ categories, selectedCategories, activeCategory, candidates, recommendationId, maxMinutes, busy, stops, remainingMinutes, onCategory, onSelect, onFinish }) {
  const { t, approx, walkTime, stayTime } = useI18n();
  const listRef = useRef(null);
  useEffect(() => {
    if (busy || !activeCategory || !recommendationId || !candidates.length) return;
    let sent = false;
    const send = () => {
      if (sent || document.visibilityState !== 'visible') return;
      sent = true;
      recordImpression(recommendationId).catch(() => {
        // Missing acknowledgements are not counted; selection stays available.
        console.warn('Recommendation impression could not be recorded.');
      });
    };
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) send();
    });
    const element = listRef.current;
    if (element) observer.observe(element);
    const onVisible = () => {
      if (element) { observer.unobserve(element); observer.observe(element); }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', onVisible); };
  }, [busy, activeCategory, recommendationId, candidates]);
  return <section className="next-place-picker" aria-label={t("buildCourse")}>
    <div className="panel-heading"><h2>{t("nextStop", { n: stops.length + 1 })}</h2></div>
    <p className="source-note">{t("chooseNextHint")}</p>
    <p className="remaining-time">{t("remainingTime", { time: approx(remainingMinutes) })}</p>
    <div className="next-category-tabs">{categories.map((category) => <button key={category} type="button" className={selectedCategories.includes(category) ? "trip-category-selected" : undefined} aria-pressed={activeCategory === category} disabled={busy} onClick={() => onCategory(category)}>{t(category)}</button>)}</div>
    <div ref={listRef} aria-live="polite" aria-busy={busy}>
      {busy ? <p className="source-note">{t("findingNext")}</p> : activeCategory && (candidates.length ? <ul className="alt-list next-candidates">{candidates.map((place) => <li key={place.id}><button type="button" onClick={() => onSelect(place)}>
        <span className="result-name">{place.name}</span>{place.official_name && <span className="result-official-name">{place.official_name}</span>}<span className="result-address">{place.address}</span>
        <span className="result-address">{stops.length ? t("fromLastStop") : t("start")}: {walkTime(place.leg_minutes)} · {stayTime(place.duration_min)}</span>
        <EstimatedSpend amount={place.estimated_spend} />
        <span className="result-address">{t("afterAdding", { time: approx(place.projected_total_minutes) })}</span>
        {place.over_budget && <span className="candidate-time-warning">{t("timeOverrun", { limit: approx(maxMinutes), extra: approx(Math.round((place.projected_total_minutes - maxMinutes) * 10) / 10) })}</span>}
        <span className="candidate-tags"><span className={place.payment_status === "merchant_listed" ? "payment-tag" : "payment-tag payment-tag-neutral"}>{t(paymentTagKey(place.payment_status))}</span>{place.is_busan_taste && <span className="taste-tag">{t("tasteTag")}</span>}{place.opening_status === "open" && <span className="open-tag">{t("openNow")}</span>}{place.opening_status === "closed" && <span className="closed-tag">{t("closedNow")}</span>}</span>
        <span className="confirm-place">{t("confirmPlace", { n: stops.length + 1 })}</span>
      </button></li>)}</ul> : <p className="source-note">{t("noNextPlaces")}</p>)}
    </div>
    <button type="button" className="submit-btn" disabled={busy || !stops.length} onClick={onFinish}>{t("finishCourse")}</button>
  </section>;
}
