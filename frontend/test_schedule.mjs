import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSchedule, formatScheduleRange, validDepartureTime, busanClock, busanDate, validDepartureDate } from './src/schedule.js';

test('walking, visits and return use one continuous departure-based timeline', () => {
  const stops = [{ leg_minutes: 5, duration_min: 60 }, { leg_minutes: 10, duration_min: 30 }];
  const s = buildSchedule(stops, '10:00', { leg_minutes: 5 });
  assert.equal(formatScheduleRange('ko', s.visits[0].walk), '10:00 ~ 10:05');
  assert.equal(formatScheduleRange('ko', s.visits[0].stay), '10:05 ~ 11:05');
  assert.equal(formatScheduleRange('ko', s.visits[1].walk), '11:05 ~ 11:15');
  assert.equal(formatScheduleRange('ko', s.visits[1].stay), '11:15 ~ 11:45');
  assert.equal(formatScheduleRange('ko', s.returnWalk), '11:45 ~ 11:50');
  const changed = buildSchedule(stops.slice(1), '10:00');
  assert.equal(formatScheduleRange('ko', changed.visits[0].stay), '10:10 ~ 10:40');
});

test('seconds are accumulated before rounding, and midnight is labeled in all languages', () => {
  const s = buildSchedule([{ leg_seconds: 61, leg_minutes: 1, duration_min: 60 }, { leg_seconds: 61, leg_minutes: 1, duration_min: 0 }], '23:58');
  assert.equal(formatScheduleRange('ko', s.visits[0].walk), '23:58 ~ 익일 00:00');
  assert.equal(formatScheduleRange('ko', s.visits[1].walk), '익일 01:00 ~ 익일 01:01');
  for (const [lang, label] of [['en','Next day'],['ja','翌日'],['zh-TW','翌日']]) {
    assert.equal(formatScheduleRange(lang, s.visits[0].walk), `23:58 ~ ${label} 00:00`);
  }
});

test('automatic time uses Korea time and invalid clocks cannot produce a schedule', () => {
  assert.equal(busanClock(new Date('2026-10-26T01:00:00Z')), '10:00');
  assert.equal(busanClock(new Date('2026-10-26T15:00:00Z')), '00:00');
  assert.equal(validDepartureTime('00:00'), true);
  for (const value of ['', null, undefined, '24:00','10:60','9:00','10:00\n']) {
    assert.equal(validDepartureTime(value), false);
    assert.equal(buildSchedule([], value), null);
  }
});

test('busanDate reflects the Korea calendar day, including around UTC midnight', () => {
  assert.equal(busanDate(new Date('2026-10-26T14:59:00Z')), '2026-10-26');
  assert.equal(busanDate(new Date('2026-10-26T15:00:00Z')), '2026-10-27');
  assert.equal(validDepartureDate('2026-10-26'), true);
  for (const value of ['', null, undefined, '2026-10-6', '2026-13-01', '2026-02-30', '26-10-26']) {
    assert.equal(validDepartureDate(value), false);
  }
});
