import PlaceNameSupplement from "./PlaceNameSupplement";
import { useI18n } from "../i18n.js";
import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, ZoomControl, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import Icon from "./Icon";
import { BUSAN_CENTER } from "../constants";

function numberedIcon(n) {
  return L.divIcon({
    className: "stop-marker",
    html: `<div class="stop-marker-inner">${n}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

const startIcon = L.divIcon({
  className: "start-marker",
  html: `<div class="start-marker-inner">S</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

function FlyToStart({ startPoint }) {
  const map = useMap();
  useEffect(() => {
    if (startPoint) {
      map.flyTo([startPoint.lat, startPoint.lon], 15, { duration: 0.8 });
    }
  }, [startPoint, map]);
  return null;
}

function ClickHandler({ onPick }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lon: e.latlng.lng });
    },
  });
  return null;
}

export default function MapView({ stops, returnLeg, startPoint, onPickStart, totalMinutes, overBudget, maxMinutes }) {
  const { t, approx, minutes, locale } = useI18n();
  const paths = [...stops, returnLeg].filter((leg) => leg && leg.routing_source !== "estimated" && leg.leg_path?.length > 1).map((leg) => leg.leg_path);
  const progressPct = maxMinutes ? Math.min(100, Math.round((totalMinutes / maxMinutes) * 100)) : 0;

  return (
    <>
      <div className="map-toolbar"><div className="map-location"><span className="map-location-icon"><Icon name="pin" size={21} /></span><div><h2>{t("busanJunggu")}</h2></div></div><span className="walking-mode"><Icon name="walk" size={17} />{t("walkingMode")}</span></div>
      <MapContainer center={BUSAN_CENTER} zoom={15} className="map" zoomControl={false}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <ClickHandler onPick={onPickStart} />
        <FlyToStart startPoint={startPoint} />
        <ZoomControl key={locale} position="bottomright" zoomInTitle={t("zoomIn")} zoomOutTitle={t("zoomOut")} />

        {paths.map((path, index) => <Polyline key={index} positions={path} color="#0d9488" weight={4} opacity={0.9} />)}

        {startPoint && (
          <Marker position={[startPoint.lat, startPoint.lon]} icon={startIcon}>
            <Popup>{t("start")}</Popup>
          </Marker>
        )}

        {stops.map((stop) => (
          <Marker key={stop.id} position={[stop.lat, stop.lon]} icon={numberedIcon(stop.order)}>
            <Popup>
              <strong>{stop.order}. {stop.name}</strong><br />
              <PlaceNameSupplement place={stop} className="stop-official-name" />
              {t(stop.category)} · {stop.address}<br />
              {t("previousWalk", { time: approx(stop.leg_minutes) })}
            </Popup>
          </Marker>
        ))}
      </MapContainer>


      {stops.length > 0 && (
        <div className="map-status-card">
          <div className="map-status-row">
            <span><Icon name="route" size={17} />{t("routeStatus")}</span>
            <span className={overBudget ? "map-status-pct over" : "map-status-pct"}>
              {approx(totalMinutes)}{maxMinutes ? " / " + minutes(maxMinutes) : ""}
            </span>
          </div>
          <div className="map-status-bar">
            <div
              className={overBudget ? "map-status-fill over" : "map-status-fill"}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}
    </>
  );
}
