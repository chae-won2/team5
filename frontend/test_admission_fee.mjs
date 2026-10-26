import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('admission cards distinguish free, confirmed adult prices and conditional fees in all locales', async () => {
  const server=await createServer({server:{middlewareMode:true},appType:'custom'});
  try {
    const {default:AdmissionFee}=await server.ssrLoadModule('/src/components/AdmissionFee.jsx');
    const {LanguageContext}=await server.ssrLoadModule('/src/i18n.js');
    const render=(locale,place)=>renderToStaticMarkup(createElement(LanguageContext.Provider,
      {value:{locale,setLocale(){}}},createElement(AdmissionFee,{place:{category:'관광명소',...place}})));
    for(const locale of ['ko','en','ja','zh-TW']) {
      assert.ok(render(locale,{admission_fee_status:'free',admission_fee_krw:0}));
      assert.match(render(locale,{admission_fee_status:'paid',admission_fee_krw:12000}),/12,000/);
      assert.doesNotMatch(render(locale,{admission_fee_status:'conditional',admission_fee_krw:19000}),/19,000/);
      assert.equal(render(locale,{admission_fee_status:'unknown',admission_fee_krw:null}),'');
      assert.equal(render(locale,{category:'쇼핑',admission_fee_status:'paid',admission_fee_krw:12000}),'');
    }
  } finally {await server.close();}
});
