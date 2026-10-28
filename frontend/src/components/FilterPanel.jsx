import { useI18n } from "../i18n.js";
import { useState } from "react";
import { searchLocation } from "../api";
import { busanDate, busanClock } from "../schedule.js";
import Icon from "./Icon";

export default function FilterPanel({
  startPoint, setStartPoint,
  returnToStart, setReturnToStart,
  maxMinutes, setMaxMinutes,
  departureDate, setDepartureDate,
  departureTime, setDepartureTime,
  onSubmit, loading, collapsed,
}) {
  const { t, minutes, placeLabel, message } = useI18n();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [locating, setLocating] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [departureMode, setDepartureMode] = useState(departureTime ? "date" : "now");


  const mode = departureMode === "now" && (departureTime || departureDate !== busanDate()) ? "date" : departureMode;
  const canSubmit = !!startPoint && !loading;

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      const data = await searchLocation(query.trim());
      setResults(data.results);
      if (data.results.length === 0) setSearchError(t("noSearchResults"));
    } catch {
      setSearchError(t("searchError"));
    } finally {
      setSearching(false);
    }
  }

  function pickResult(r) {
    setStartPoint({ lat: r.lat, lon: r.lon, label: r.name, address: r.address });
    setResults([]);
    setQuery("");
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setSearchError(t("locationUnsupported"));
      return;
    }
    setLocating(true);
    setSearchError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setStartPoint({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: "내 위치" });
        setLocating(false);
      },
      () => {
        setSearchError(t("locationError"));
        setLocating(false);
      }
    );
  }

  if (collapsed && !expanded) {
    return (
      <div className="filter-summary">
        <div className="filter-summary-text">
          <span className="filter-summary-pin"><Icon name="pin" size={15} /> {placeLabel(startPoint)}</span>
          <span className="filter-summary-dot">·</span>
          <span>{minutes(maxMinutes)}</span>
          {departureDate !== busanDate() && <span>{departureDate}</span>}
          {departureTime && <span>{t("departureAt", { time: departureTime })}</span>}
          <span className="filter-summary-dot">·</span>
          <span>{returnToStart ? t("returnShort") : t("finishShort")}</span>
        </div>
        <button type="button" className="filter-edit-btn" onClick={() => setExpanded(true)}>
          {t("editSettings")}
        </button>
      </div>
    );
  }

  return (
    <div className="filter-panel">
      <div className="panel-heading"><h2>{t("tripSettings")}</h2></div>
      <div className="field field-start">
        <span className="field-title"><Icon name="pin" size={16} />{t("start")}</span>

        {startPoint ? (
          <div className="start-point-chip">
            <Icon name="pin" size={17} /> {startPoint.label ? placeLabel(startPoint) : `${startPoint.lat.toFixed(5)}, ${startPoint.lon.toFixed(5)}`}
            <button type="button" className="clear-start" onClick={() => setStartPoint(null)}>{t("change")}</button>
          </div>
        ) : (
          <>
            <form className="search-row" onSubmit={handleSearch}>
              <input
                type="text"
                aria-label={t("searchLabel")}
                placeholder={t("searchPlaceholder")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button type="submit" aria-label={t("search")} disabled={searching}>{searching ? "…" : <Icon name="search" size={19} />}</button>
            </form>

            <button type="button" className="my-location-btn" onClick={useMyLocation} disabled={locating}>
              {locating ? t("locating") : <><Icon name="locate" size={16} />{t("useLocation")}</>}
            </button>

            {searchError && <div className="search-error">{message(searchError)}</div>}

            {results.length > 0 && (
              <ul className="search-results">
                {results.map((r, i) => (
                  <li key={i}><button type="button" onClick={() => pickResult(r)}>
                    <div className="result-name">{r.name}</div>
                    <div className="result-address">{r.address}</div>
                  </button></li>
                ))}
              </ul>
            )}

            <div className="start-point-hint">{t("mapHint")}</div>
          </>
        )}
      </div>

      <div className="field departure-modes"><span className="field-title">{t("departureTime")}</span><div className="departure-options">{["now","today","date"].map(option => <button key={option} type="button" aria-pressed={mode===option} onClick={() => { setDepartureMode(option); if(option!=="date") setDepartureDate(busanDate()); setDepartureTime(option==="now" ? "" : departureTime || busanClock()); }}>{t({now:"departNow",today:"departToday",date:"departDate"}[option])}</button>)}</div></div>
      {mode === "date" && <div className="field field-date">
        <label className="field-title" htmlFor="departure-date">{t("departureDate")}</label>
        <div className="departure-time-row"><input id="departure-date" type="date" min={busanDate()} value={departureDate} onChange={(e) => setDepartureDate(e.target.value)} /></div>
        <span className="start-point-hint">{t("departureDateHint")}</span>
      </div>}

      {mode !== "now" && <div className="field field-time">
        <label className="field-title" htmlFor="departure-time">{t("departureTime")}</label>
        <div className="departure-time-row"><input id="departure-time" type="time" step="60" value={departureTime} onChange={(e) => setDepartureTime(e.target.value)} />{departureTime && <button type="button" className="filter-edit-btn" onClick={() => setDepartureTime("")}>{t("automaticDeparture")}</button>}</div>
        <span className="start-point-hint">{t("departureHint")}</span>
      </div>}

      <label className="field field-budget">
        <span className="field-title"><Icon name="clock" size={16} />{t("tripTime")}<b className="time-value">{minutes(maxMinutes)}</b></span>
        <input
          aria-label={t("tripTime")} type="range" min={30} max={360} step={10} aria-valuetext={minutes(maxMinutes)} value={maxMinutes}
          onChange={(e) => setMaxMinutes(Number(e.target.value))}
        />
        <span className="range-labels"><span>{minutes(30)}</span><span>{minutes(360)}</span></span>
        <span className="start-point-hint">{t("budgetHint")}</span>
      </label>

      <div className="field field-end"><span className="field-title">{t("endMode")}</span>
        <div className="end-options" aria-label={t("endMode")}><button type="button" aria-pressed={!returnToStart} onClick={() => setReturnToStart(false)}>{t("finishLast")}</button><button type="button" aria-pressed={returnToStart} onClick={() => setReturnToStart(true)}>{t("returnStart")}</button></div>
        <span className="start-point-hint">{t("radiusHint")}{returnToStart && t("returnHint")}</span>
      </div>

      <button
        className="submit-btn"
        onClick={() => { onSubmit(); setExpanded(false); }}
        disabled={!canSubmit}
      >
        {loading ? t("creating") : <>{t("recommend")}<Icon name="arrow" size={19} /></>}
      </button>
    </div>
  );
}
