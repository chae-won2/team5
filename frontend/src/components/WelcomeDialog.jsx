import { useState } from "react";
import { useI18n } from "../i18n.js";
import Dialog from "./Dialog";
import Icon from "./Icon";
export default function WelcomeDialog({ onClose }) {
  const { t, locale, setLocale, languages } = useI18n();
  const [hide, setHide] = useState(false);
  function close() { if (hide) { try { localStorage.setItem("busan-welcome-hidden", "1"); } catch { /* Planning remains available without browser storage. */ } } onClose(); }
  return <Dialog title={t("welcomeTitle")} onClose={close}>
    <div className="welcome-brand"><img src="/busan-full-course-logo.png" alt="BUSAN FULL COURSE" /></div>
    <div className="language-options" aria-label={t("language")}>{Object.entries(languages).map(([code,label]) => <button type="button" key={code} aria-pressed={locale===code} onClick={() => setLocale(code)}>{label}</button>)}</div>
    <p className="dialog-intro">{t("welcomeIntro")}</p>
    <ol className="welcome-steps">{["pin","route","mail"].map((icon,i) => <li key={icon}><span><Icon name={icon} size={20}/></span><div><strong>{t(`welcomeStep${i+1}`)}</strong><p>{t(`welcomeStep${i+1}Body`)}</p></div></li>)}</ol>
    <p className="welcome-note">{t("payNotice")}</p>
    <button type="button" className="submit-btn" onClick={close}>{t("welcomeStart")}</button>
    <label className="welcome-hide"><input type="checkbox" checked={hide} onChange={e=>setHide(e.target.checked)}/>{t("welcomeHide")}</label>
  </Dialog>;
}
