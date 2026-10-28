import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

test('completed course keeps timeline, partial price summary, email action and all locales',async()=>{
 const server=await createServer({server:{middlewareMode:true},appType:'custom'});
 try {
 const {default:RouteList}=await server.ssrLoadModule('/src/components/RouteList.jsx');
 const {default:Welcome}=await server.ssrLoadModule('/src/components/WelcomeDialog.jsx');
 const {LanguageContext}=await server.ssrLoadModule('/src/i18n.js');
 for(const locale of ['ko','en','ja','zh-TW']) {
 const render=(component,props)=>renderToStaticMarkup(createElement(LanguageContext.Provider,{value:{locale,setLocale(){}}},createElement(component,props)));
 const html=render(RouteList,{phase:'result',building:false,stops:[{id:'one',order:1,name:'가게',category:'식당',address:'부산 중구',leg_seconds:61,leg_minutes:61/60,duration_min:60,estimated_spend:12000},{id:'two',order:2,name:'명소',category:'관광명소',address:'부산 중구',leg_seconds:61,leg_minutes:61/60,duration_min:30,estimated_spend:null}],totalMinutes:92.1,maxMinutes:120,scheduleStart:'10:00',startPoint:{lat:35.1,lon:129.03},departureDate:'2026-10-28'});
 assert.match(html,/10:00 ~ 11:33/);assert.match(html,/₩12,000/);assert.doesNotMatch(html,/NaN|undefined/);assert.match(html,/google.com\/maps\/dir/);assert.match(html,/email-cta/);
 assert.match(render(Welcome,{}),/busan-full-course-logo.png/);
 }
 }finally{await server.close();}
});