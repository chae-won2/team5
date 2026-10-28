import test from 'node:test';
import assert from 'node:assert/strict';
import {watchMapRegion} from './src/map-region.js';
const pause=()=>new Promise(r=>setTimeout(r,400));
function map(){let listener;return {center:{lat:35.1,lng:129.03},on(_,fn){listener=fn},off(_,fn){assert.equal(listener,fn);listener=null},getCenter(){return this.center},move(lat){this.center={lat,lng:129.04};listener?.()}}}

test('rapid moves are debounced; old replies and replies after cleanup cannot replace the current district',async()=>{
 const m=map(),pending=[],states=[];
 const stop=watchMapRegion(m,args=>new Promise(resolve=>pending.push({args,resolve})),s=>states.push(s));
 m.move(35.11);m.move(35.12);await pause();assert.equal(pending.length,1);assert.equal(pending[0].args.lat,35.12);
 m.move(35.13);assert.ok(pending[0].args.signal.aborted);await pause();assert.equal(pending.length,2);
 pending[1].resolve({district:'영도구',dong:'동삼1동'});await pause();assert.equal(states.at(-1).label,'영도구 동삼1동');
 pending[0].resolve({district:'중구',dong:'광복동'});await pause();assert.equal(states.at(-1).label,'영도구 동삼1동');
 m.move(35.14);await pause();stop();const count=states.length;pending[2].resolve({district:'다른구',dong:'다른동'});await pause();assert.equal(states.length,count);
});

test('failed or empty lookups clear the previous map label',async()=>{
 const m=map(),states=[];let fail=false;
 const stop=watchMapRegion(m,async()=>{if(fail)throw new Error('network');return {district:'',dong:''}},s=>states.push(s));
 await pause();assert.deepEqual(states.at(-1),{status:'ready',label:''});fail=true;m.move(35.2);await pause();assert.deepEqual(states.at(-1),{status:'error',label:''});stop();
});