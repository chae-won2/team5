import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('chosen categories stay highlighted while the active category shows its candidates', async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
  try {
    const { default: NextPlacePicker } = await server.ssrLoadModule('/src/components/NextPlacePicker.jsx');
    const { LanguageContext } = await server.ssrLoadModule('/src/i18n.js');
    const render = (activeCategory) => renderToStaticMarkup(createElement(LanguageContext.Provider,
      { value: { locale: 'ko', setLocale() {} } }, createElement(NextPlacePicker, {
        categories: ['식당', '카페/디저트'], selectedCategories: ['식당', '카페/디저트'],
        activeCategory, candidates: [{ id: 'test', name: '추천 장소', address: '부산 중구',
          leg_minutes: 5, duration_min: 30, projected_total_minutes: 35, payment_status: 'merchant_listed' }],
        stops: [], remainingMinutes: 90, maxMinutes: 90, busy: false,
      })));
    for (const active of ['식당', '카페/디저트']) {
      const html = render(active);
      const tabs = html.match(/<div class="next-category-tabs">(.*?)<\/div>/)[1];
      assert.equal((tabs.match(/class="trip-category-selected"/g) || []).length, 2);
      assert.equal((tabs.match(/aria-pressed="true"/g) || []).length, 1);
      assert.ok(tabs.includes(`aria-pressed="true">${active}</button>`));
      assert.ok(html.includes('추천 장소'));
    }
  } finally { await server.close(); }
});
