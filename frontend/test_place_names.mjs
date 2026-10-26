import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('foreign names follow current locale, prefer official names, and label automatic readings', async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
  try {
    const { default: Supplement } = await server.ssrLoadModule('/src/components/PlaceNameSupplement.jsx');
    const { LanguageContext } = await server.ssrLoadModule('/src/i18n.js');
    const render = (locale, place) => renderToStaticMarkup(createElement(LanguageContext.Provider,
      { value: { locale, setLocale() {} } }, createElement(Supplement, { place })));
    const place = {name:'부산공원', official_name:'Old English',
      official_names:{en:'Official English', ja:'公式名称'}, romanized_name:'Busangongwon'};
    assert.equal(render('ko',place),'');
    assert.match(render('en',place),/Official English/);
    assert.match(render('ja',place),/公式名称/);
    assert.doesNotMatch(render('en',place),/automatic|Busangongwon/);
    assert.match(render('zh-TW',place),/Busangongwon.*羅馬字標示（自動）/);
    for (const locale of ['en','ja','zh-TW']) {
      const html=render(locale,{name:'대양상회', official_names:{}, romanized_name:'Daeyangsanghoe'});
      assert.match(html,/Daeyangsanghoe/);
    }
    assert.equal(render('en',{name:'CAFE 123',official_names:{},romanized_name:''}),'');
  } finally { await server.close(); }
});
