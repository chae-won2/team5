import test from "node:test";
import assert from "node:assert/strict";
import { resources, translate, formatDuration, formatEstimatedSpend, paymentTagKey } from "./src/locale.js";

test("all four languages have matching keys and substitution parameters", () => {
  const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
  for (const [locale, copy] of Object.entries(resources)) {
    assert.deepEqual(Object.keys(copy).sort(), Object.keys(resources.ko).sort());
    for (const [key, value] of Object.entries(copy)) {
      assert.ok(value.trim(), `${locale}:${key}`);
      assert.deepEqual(placeholders(value), placeholders(resources.ko[key]), `${locale}:${key}`);
    }
  }
});
test("category aliases and estimated times translate without changing category IDs", () => {
  assert.equal(translate("en", "카페/디저트"), "Café & dessert");
  assert.equal(translate("ja", "카페·디저트"), "カフェ・スイーツ");
  assert.equal(translate("zh-TW", "식당"), "餐廳");
  assert.equal(translate("zh-TW", "walkTime", { time: formatDuration("zh-TW", 10) }), "步行約10分鐘");
  assert.equal(translate("en", "placeCount", { count: 1 }), "1 stop");
  assert.equal(translate("ja", translate("en", "swapBudget")), resources.ja.swapBudget);
});

test("durations use hours and minutes across all screen time labels", () => {
  for (const [input, expected] of [[0,"0분"],[30,"30분"],[60,"1시간"],[90,"1시간 30분"],[360,"6시간"],[369,"6시간 9분"],[59.9,"1시간"],[10 + 10/60,"11분"],[60 + 1/60,"1시간 1분"],[0.01,"1분"]]) {
    assert.equal(formatDuration("ko", input), expected);
  }
  for (const [locale, expected] of [["ko","1시간 30분"],["en","1 hr 30 min"],["ja","1時間 30分"],["zh-TW","1小時 30分鐘"]]) {
    const time = formatDuration(locale, 90);
    assert.equal(time, expected);
    for (const key of ["approx", "walkTime", "stayTime"]) {
      const label = translate(locale, key, { time });
      assert.ok(label.includes(expected), `${locale}:${key}`);
      assert.ok(!label.includes("{"), label);
    }
  }
});

test("spend labels are per person, localized and absent for missing prices", () => {
  assert.equal(formatEstimatedSpend("ko", 12000), "예상지출 1인당 약 12,000원");
  assert.equal(formatEstimatedSpend("en", 12000), "Estimated spend: approx. ₩12,000 per person");
  assert.equal(formatEstimatedSpend("ja", 12000), "予算の目安：1人あたり約₩12,000");
  assert.equal(formatEstimatedSpend("zh-TW", 12000), "預估消費：每人約 ₩12,000");
  for (const value of [null, undefined, "", "12000", 0, -1, NaN, Infinity]) {
    assert.equal(formatEstimatedSpend("ko", value), "");
  }
});

test("missing registration is not treated as confirmed payment refusal", () => {
  assert.equal(paymentTagKey("merchant_listed"), "paymentTag");
  assert.equal(paymentTagKey("not_accepted"), "paymentUnavailable");
  for (const status of ["not_verified", undefined, null, ""]) {
    assert.equal(paymentTagKey(status), "paymentUnverified");
  }
});
