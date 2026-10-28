import { busanClock, busanDate, validDepartureTime, validDepartureDate } from "./schedule.js";
import { useI18n } from "./i18n.js";
import { useEffect, useState } from "react";
import FilterPanel from "./components/FilterPanel";
import MapView from "./components/MapView";
import RouteList from "./components/RouteList";
import NextPlacePicker from "./components/NextPlacePicker";
import { getCategories, getNextPlaces } from "./api";
import "./App.css";
import Icon from "./components/Icon";
import ServiceInfo from "./components/ServiceInfo";

export default function App() {
  const { locale, setLocale, languages, t, message } = useI18n();
  const [info, setInfo] = useState(null);
  const [startPoint, setStartPoint] = useState(null);
  const [allCategories, setAllCategories] = useState([]);
  const [categories, setCategories] = useState([]);
  const [returnToStart, setReturnToStart] = useState(false);
  const [departureDate, setDepartureDate] = useState(busanDate());
  const [departureTime, setDepartureTime] = useState("");
  const [scheduleStart, setScheduleStart] = useState("");
  const [building, setBuilding] = useState(false);
  const [activeCategory, setActiveCategory] = useState(null);
  const [returnLeg, setReturnLeg] = useState(null);
  const [appliedConditions, setAppliedConditions] = useState(null);
  const [maxMinutes, setMaxMinutes] = useState(90);
  const [stops, setStops] = useState([]);
  const [alternatives, setAlternatives] = useState([]);
  const [recommendationId, setRecommendationId] = useState(null);
  const [totalMinutes, setTotalMinutes] = useState(0);
  const [overBudget, setOverBudget] = useState(false);
  const [routingEstimated, setRoutingEstimated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    getCategories().then(setAllCategories).catch(() => {
      setError("categoryError");
    });
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ids = params.getAll("stop");
    if (!ids.length) return;
    const origin = (params.get("start") || "").split(",");
    const lat = Number(origin[0]), lon = Number(origin[1]);
    const minutes = Number(params.get("minutes"));
    const departure = params.get("depart") || "";
    const dateParam = params.get("date") || "";
    const date = validDepartureDate(dateParam) ? dateParam : busanDate();
    if ((departure && !validDepartureTime(departure)) || origin.length !== 2 || origin.some((v) => !v.trim()) || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180 || !Number.isInteger(minutes) || minutes < 30 || minutes > 360 || ids.length > 24 || new Set(ids).size !== ids.length) {
      setError("sharedRouteError");
      return;
    }
    const point = { lat, lon, label: params.get("label") || "" };
    const conditions = { startPoint: point, maxMinutes: minutes, returnToStart: params.get("return") === "1", categories: [], departureDate: date, departureTime: departure };
    const urlLanguage = params.get("lang");
    const language = ["ko", "en", "ja", "zh-TW"].includes(urlLanguage) ? urlLanguage : locale;
    setLoading(true);
    getNextPlaces({ ...conditions, stops: ids.map((id) => ({ id })), category: null, language })
      .then((data) => {
        applyRoute(data);
        setStartPoint(point);
        setMaxMinutes(minutes);
        setReturnToStart(conditions.returnToStart);
        setAppliedConditions(conditions);
        setDepartureDate(date);
        setDepartureTime(departure);
        setScheduleStart(departure || busanClock());
        setHasSearched(true);
        setBuilding(false);
        if (language !== locale) setLocale(language);
      })
      .catch(() => setError("sharedRouteError"))
      .finally(() => setLoading(false));
  }, []);

  function toggleCategory(c) {
    setCategories((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  }

  function applyRoute(data) {
    setStops(data.stops);
    setAlternatives(data.alternatives || []);
    setRecommendationId(data.recommendation_id || null);
    setReturnLeg(data.return_leg || null);
    setTotalMinutes(data.total_minutes);
    setOverBudget(data.over_budget);
    setRoutingEstimated(!!data.routing_estimated);
  }

  function handleSubmit() {
    if (!startPoint || loading) return;
    const conditions = { startPoint, maxMinutes, returnToStart, categories: [...categories], departureDate, departureTime };
    setAppliedConditions(conditions);
    setScheduleStart(departureTime || busanClock());
    applyRoute({ stops: [], total_minutes: 0, over_budget: false });
    setError(null);
    setNotice(null);
    setHasSearched(true);
    setBuilding(true);
    updateSelection([], categories[0] || allCategories[0] || null, conditions);
  }

  async function updateSelection(nextStops, category = null, conditions = appliedConditions) {
    if (!conditions || loading) return;
    setActiveCategory(category);
    setLoading(true);
    setError(null);
    try {
      const data = await getNextPlaces({ ...conditions, stops: nextStops, category, language: locale });
      applyRoute(data);
      return true;
    } catch (e) {
      setError(e.message || t("recalculateError"));
      return false;
    } finally {
      setLoading(false);
    }
  }

  const phase = loading && !hasSearched ? "loading" : hasSearched ? "result" : "setup";

  return (
    <div className="app">
      <header className="app-header">
        <a className="brand" href="/" aria-label={t("home")}><span className="brand-image"><img src="/busan-full-course-logo.png" alt="부산 풀코스 · BUSAN FULL COURSE" /></span><span className="brand-partner"><small>with</small><img src="/busan-pay-logo.png" alt="BUSAN Pay" /></span></a>
        <nav className="header-nav" aria-label={t("navigation")}><span className="header-tab active"><Icon name="route" size={17} />{t("plan")}</span><button type="button" onClick={() => setInfo("guide")}>{t("guide")}</button></nav>
        <select className="language-select" aria-label={t("language")} value={locale} onChange={(e) => setLocale(e.target.value)}>{Object.entries(languages).map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <div className="sidebar-scroll">
            <section className="planner-intro" id="trip-planner"><h1>{t("appTitle")}</h1><p>{t("intro")}</p></section>
            <FilterPanel
              startPoint={startPoint} setStartPoint={setStartPoint}
              allCategories={allCategories}
              categories={categories} toggleCategory={toggleCategory}
              returnToStart={returnToStart} setReturnToStart={setReturnToStart}
              maxMinutes={maxMinutes} setMaxMinutes={setMaxMinutes}
              departureDate={departureDate} setDepartureDate={setDepartureDate}
              departureTime={departureTime} setDepartureTime={setDepartureTime}
              onSubmit={handleSubmit} loading={loading}
              collapsed={phase === "result"}
            />
            {routingEstimated && <p className="routing-estimate-note" role="status">{t("walkingEstimateNotice")}</p>}
            {notice && <div className="source-note" role="status">{message(notice)}</div>}
            {error && <div className="error">⚠ {message(error)}</div>}
            <div id="trip-results"><RouteList
              stops={stops} alternatives={alternatives}
              totalMinutes={totalMinutes} overBudget={overBudget}
              maxMinutes={appliedConditions?.maxMinutes || maxMinutes}
              scheduleStart={scheduleStart} automaticStart={!appliedConditions?.departureTime}
              phase={phase} startPoint={appliedConditions?.startPoint || startPoint} returnLeg={returnLeg}
              building={building} busy={loading}
              onRemoveStop={(index) => updateSelection(stops.filter((_, i) => i !== index))}
            />
              {hasSearched && (building ? <NextPlacePicker
                categories={appliedConditions.categories.length ? appliedConditions.categories : allCategories}
                selectedCategories={appliedConditions.categories}
                activeCategory={activeCategory} candidates={alternatives} busy={loading}
                recommendationId={recommendationId}
                maxMinutes={appliedConditions.maxMinutes}
                stops={stops} remainingMinutes={Math.max(0, appliedConditions.maxMinutes - totalMinutes)}
                onCategory={(category) => updateSelection(stops, category)}
                onSelect={(place) => updateSelection([...stops, place])}
                onFinish={() => { if (!appliedConditions.departureTime) setScheduleStart(busanClock()); setBuilding(false); setAlternatives([]); }}
              /> : <button type="button" className="secondary-btn" onClick={() => { setBuilding(true); setActiveCategory(null); }}>{t("editCourse")}</button>)}
            </div>
          </div>
        </aside>
        <main className="map-area">
          <MapView
            stops={stops} returnLeg={returnLeg} startPoint={hasSearched ? appliedConditions?.startPoint : startPoint} onPickStart={(point) => { if (!hasSearched) setStartPoint(point); }}
            totalMinutes={totalMinutes} overBudget={overBudget} maxMinutes={appliedConditions?.maxMinutes || maxMinutes}
          />
        </main>
      </div>
      <footer className="app-footer"><span>© BUSAN FULL COURSE <span className="footer-divider">|</span> {t("footer")}</span><div><button type="button" onClick={() => setInfo("guide")}>{t("guide")}</button><button type="button" onClick={() => setInfo("privacy")}>{t("privacy")}</button></div></footer>
      {info && <ServiceInfo section={info} onClose={() => setInfo(null)} />}
    </div>
  );
}
