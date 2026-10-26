import { buildSchedule, formatScheduleRange } from "../schedule.js";
import { paymentTagKey } from "../locale.js";
import EstimatedSpend from "./EstimatedSpend";
import { useI18n } from "../i18n.js";
import { useState } from "react";
import { sendRouteEmail } from "../api";
import RouteLoading from "./RouteLoading";
import Icon from "./Icon";
import Dialog from "./Dialog";

function EmailModal({ onClose, onSend, sending, sendResult }) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  return <Dialog title={t("emailTitle")} onClose={onClose}>
    <p className="dialog-intro">{t("emailIntro")}</p>
    <form onSubmit={(e) => { e.preventDefault(); if (consent && !sending) onSend(email); }}>
      <label className="field email-field"><span>{t("emailAddress")}</span><input type="email" required maxLength={254} autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} className="email-input" /></label>
      <div className="consent-details"><strong>{t("emailUse")}</strong><p>{t("emailUseBody")}</p><p>{t("emailOptional")}</p></div>
      <label className="consent-check"><input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} /><span>{t("emailConsent")}</span></label>
      <div className="modal-actions"><button type="button" className="secondary-btn" onClick={onClose} disabled={sending}>{t("close")}</button><button type="submit" className="submit-btn" disabled={!email || !consent || sending || sendResult === "success"}>{sending ? t("sending") : t("send")}<Icon name="mail" size={18} /></button></div>
    </form>
    <div role="status" aria-live="polite">
      {sendResult === "success" && <p className="email-send-note">{t("sent")}</p>}
      {sendResult === "pending" && <p className="email-send-note muted">{t("mailPending")}</p>}
      {sendResult === "error" && <p className="email-send-note error">{t("mailFailed")}</p>}
    </div>
  </Dialog>;
}

export default function RouteList({ stops, totalMinutes, maxMinutes, overBudget, phase, startPoint, returnLeg, building, busy, onRemoveStop, scheduleStart, automaticStart }) {
  const { t, approx, walkTime, stayTime, placeLabel, locale } = useI18n();
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  async function handleSendEmail(email) {
    setSending(true); setSendResult(null);
    try {
      const res = await sendRouteEmail({ email, stops, totalMinutes, maxMinutes, startPoint, emailConsent: true, returnLeg, language: locale, departureTime: scheduleStart });
      setSendResult(res.sent ? "success" : "pending");
    } catch { setSendResult("error"); }
    finally { setSending(false); }
  }
  if (phase === "loading") return <RouteLoading />;
  if (phase === "setup") return <div className="empty-state"><span className="empty-icon"><Icon name="route" size={25} /></span><div><strong>{t("results")}</strong><p>{t("resultsHint")}</p></div></div>;
  if (!stops.length && building) return null;
  if (!stops.length) return <div className="empty-state"><Icon name="search" /><p>{t("emptyResults")}<br />{t("changeConditions")}</p></div>;
  const walk = Math.round((stops.reduce((sum, s) => sum + s.leg_minutes, 0) + (returnLeg?.leg_minutes || 0)) * 10) / 10;
  const stay = stops.reduce((sum, s) => sum + s.duration_min, 0);
  const schedule = buildSchedule(stops, scheduleStart, returnLeg);
  const timeRange = (range) => formatScheduleRange(locale, range);
  return <section className="route-list" aria-label={t("results")}>
    <div className="panel-heading"><h2>{t("results")}</h2><span>{t("placeCount", { count: stops.length })}</span></div>
    <div className={overBudget ? "summary-bar over" : "summary-bar"}><div><span>{t("estimatedTotal")}</span><strong>{approx(totalMinutes)}</strong></div><p>{walkTime(walk)} + {stayTime(stay)}</p>{overBudget && <span className="over-badge" role="status">{t("timeOverrun", { limit: approx(maxMinutes), extra: approx(Math.round((totalMinutes - maxMinutes) * 10) / 10) })}</span>}</div>
    {schedule && <p className="schedule-start">{t(building && automaticStart ? "departurePreview" : "departureAt", { time: scheduleStart })}{!building && automaticStart && <small>{t("completionTimeBasis")}</small>}</p>}
    <div className="route-timeline">{stops.map((stop, idx) => {
      return <div key={stop.id} className="route-stop">
        <div className="timeline-col"><span className="order-badge">{stop.order}</span><span className="timeline-line" /></div>
        <div className="route-stop-body"><div className="leg-label"><Icon name="walk" size={14} />{walkTime(stop.leg_minutes)}{schedule && <span className="leg-time">({timeRange(schedule.visits[idx].walk)})</span>}</div>
          <article className="stop-card"><span className="category-tag">{t(stop.category)}</span><h3 className="stop-name">{stop.name}{schedule && <span className="stop-time">({timeRange(schedule.visits[idx].stay)})</span>}</h3>{stop.official_name && <p className="stop-official-name">{stop.official_name}</p>}<p className="stop-address">{stop.address}</p><EstimatedSpend amount={stop.estimated_spend} /><div className="stop-card-bottom"><span><Icon name="clock" size={13} />{stayTime(stop.duration_min)}</span>{building && <button type="button" className="edit-stop-btn" disabled={busy} onClick={() => onRemoveStop(idx)}>{t("removeStop")}</button>}</div><div className="place-tags"><span className={stop.payment_status === "merchant_listed" ? "payment-tag" : "payment-tag payment-tag-neutral"}>{t(paymentTagKey(stop.payment_status))}</span>{stop.is_busan_taste && <span className="taste-tag">{t("tasteTag")}</span>}{stop.opening_status === "open" && <span className="open-tag">{t("openNow")}</span>}{stop.opening_status === "closed" && <span className="closed-tag">{t("closedNow")}</span>}</div></article>

        </div>
      </div>;
    })}</div>
    {returnLeg && <div className="return-stop"><Icon name="pin" size={17} /><div><strong>{t("returnStart")}</strong><p>{placeLabel(startPoint)} · {walkTime(returnLeg.leg_minutes)}{schedule && <span className="leg-time"> ({timeRange(schedule.returnWalk)})</span>}</p></div></div>}
    {!building && <button type="button" className="submit-btn email-cta" onClick={() => { setSendResult(null); setShowEmailModal(true); }}><Icon name="mail" size={18} />{t("emailCTA")}<Icon name="arrow" size={18} /></button>}
    <p className="source-note">{t("sourceNote")}</p>
    {showEmailModal && <EmailModal onClose={() => { if (!sending) setShowEmailModal(false); }} onSend={handleSendEmail} sending={sending} sendResult={sendResult} />}
  </section>;
}
