const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `요청 실패: ${res.status}`);
  }
  return res.json();
}

export function getCategories() {
  return request("/api/spots/categories");
}

export function searchLocation(query) {
  return request(`/api/geocode?query=${encodeURIComponent(query)}`);
}

export function getRecommendation({ startLat, startLon, categories, maxMinutes, returnToStart, selectedOnly }) {
  return request("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_lat: startLat,
      start_lon: startLon,
      categories: categories && categories.length ? categories : null,
      max_minutes: maxMinutes,
      return_to_start: returnToStart,
      selected_only: selectedOnly,
    }),
  });
}

export function sendRouteEmail({ email, stops, totalMinutes, maxMinutes, startPoint, emailConsent, returnLeg, language, departureTime }) {
  return request("/api/notify/email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      email_consent: emailConsent === true,
      language,
      departure_time: departureTime || null,
      return_seconds: returnLeg?.leg_seconds,
      return_to_start: !!returnLeg,
      return_minutes: returnLeg?.leg_minutes,
      total_minutes: totalMinutes,
      max_minutes: maxMinutes,
      start_label: startPoint?.label && startPoint.label !== "내 위치" ? [startPoint.label, startPoint.address].filter(Boolean).join(" ") : null,
      start_lat: startPoint?.lat,
      start_lon: startPoint?.lon,
      stops,
    }),
  });
}

export function recalculateRoute({ startPoint, stops, maxMinutes, returnToStart }) {
  return request("/api/recommend/recalculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start_lat: startPoint.lat, start_lon: startPoint.lon,
      stop_ids: stops.map((s) => s.id), max_minutes: maxMinutes, return_to_start: returnToStart }),
  });
}

export function getNextPlaces({ startPoint, stops, category, maxMinutes, returnToStart }) {
  return request("/api/recommend/next", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start_lat: startPoint.lat, start_lon: startPoint.lon,
      stop_ids: stops.map((stop) => stop.id), category, max_minutes: maxMinutes, return_to_start: returnToStart }),
  });
}

export function recordImpression(recommendationId) {
  return request('/api/recommend/impressions', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recommendation_id: recommendationId }),
  });
}
