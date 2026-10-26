import { translate } from "./locale.js";

export const validDepartureTime = (value) => typeof value === "string" && value.length === 5 && /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(value);

export function busanClock(now = new Date()) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(now);
}

export function buildSchedule(stops, departureTime, returnLeg = null) {
  if (!validDepartureTime(departureTime)) return null;
  const [hour, minute] = departureTime.split(":").map(Number);
  const start = hour * 60 + minute;
  let elapsed = 0;
  const segment = (seconds) => {
    const from = start + elapsed / 60;
    elapsed += seconds;
    return { start: from, end: start + elapsed / 60 };
  };
  const legSeconds = (leg) => leg.leg_seconds ?? leg.leg_minutes * 60;
  const visits = stops.map((stop) => ({ walk: segment(legSeconds(stop)), stay: segment(stop.duration_min * 60) }));
  return { visits, returnWalk: returnLeg ? segment(legSeconds(returnLeg)) : null };
}

export function formatScheduleRange(locale, range) {
  if (!range) return "";
  const clock = (minutes) => {
    const rounded = Math.ceil(minutes - 1e-9);
    const dayMinute = rounded % 1440;
    const time = `${String(Math.floor(dayMinute / 60)).padStart(2, "0")}:${String(dayMinute % 60).padStart(2, "0")}`;
    return rounded >= 1440 ? translate(locale, "nextDayTime", { time }) : time;
  };
  return `${clock(range.start)} ~ ${clock(range.end)}`;
}
