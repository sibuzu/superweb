// Real Chrome QA against an isolated local profile; no application dependencies.
// The 325-page sweep needs --disable-ipc-flooding-protection on that test browser.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const output = path.join(process.env.TEMP, 'hft-site-visual');
let socket, nextId = 0;
const networkRequests = [];
const browserLogs = [];
const pending = new Map();
async function connect() {
  const targets = await (await fetch('http://127.0.0.1:9229/json/list')).json();
  const target = targets.find(t => t.type === 'page');
  assert(target, 'Isolated Chrome page missing');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {socket.addEventListener('open', resolve, {once:true});socket.addEventListener('error', reject, {once:true});});
  socket.addEventListener('message', ({data}) => {
    const response = JSON.parse(data);
    if (response.method === 'Network.requestWillBeSent') networkRequests.push(response.params.request.url);
    if (response.method === 'Log.entryAdded') browserLogs.push(response.params.entry.text);
    if (response.method === 'Runtime.exceptionThrown') browserLogs.push(JSON.stringify(response.params.exceptionDetails));
    const waiter = pending.get(response.id);
    if (!waiter) return;
    pending.delete(response.id); clearTimeout(waiter.timer);
    response.error ? waiter.reject(new Error(JSON.stringify(response.error))) : waiter.resolve(response.result);
  });
}
function rpc(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {pending.delete(id);reject(new Error(`Timeout: ${method}`));}, 12000);
    pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression) {
  const result = await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function waitFor(expression) {
  for (let i=0;i<60;i++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error(`Page condition failed: ${expression}`);
}
async function frames() {await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');}
async function viewport(width,height,mobile=false) {
  await rpc('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile});
  await frames();
}
async function screenshot(name) {
  const shot=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  fs.writeFileSync(path.join(output,name),Buffer.from(shot.data,'base64'));
}
async function noPageOverflow() {
  const size=await evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,width:innerWidth})');
  assert(size.scroll<=size.client+1,JSON.stringify(size));return size;
}
async function strategy(id,title) {
  await evaluate(`location.hash=${JSON.stringify('#strategy/'+encodeURIComponent(id))}`);
  const program = id.slice(0,id.lastIndexOf('/'));
  await waitFor(`document.querySelector('.detail-header h1')?.textContent===${JSON.stringify(title)}&&document.querySelector('.detail-header [data-program]')?.dataset.program===${JSON.stringify(program)}`);
}
async function parameters() {
  await evaluate(`document.querySelector('[data-tab="parameters"]').click()`);
  await waitFor(`!!document.querySelector('#detail-params')`);await frames();
}
async function main() {
  await connect();await rpc('Page.enable');await rpc('Network.enable');await rpc('Log.enable');await rpc('Runtime.enable');
  await viewport(1440,1100);
  await rpc('Page.navigate',{url:'file:///D:/git/hft/site/index.html'});
  await waitFor(`!!document.querySelector('.strategy-card')`);
  await evaluate(`localStorage.removeItem('hft-atlas-favorites-v1');localStorage.removeItem('hft-atlas-favorite-outbox-v1')`);
  await rpc('Page.reload');await waitFor(`!!document.querySelector('.strategy-card')`);
  await noPageOverflow();await screenshot('desktop-cdp.png');
  await evaluate(`document.querySelector('[data-detail]').click()`);
  await waitFor(`!!document.querySelector('.detail-header h1')`);
  assert((await evaluate('location.hash')).startsWith('#strategy/'));
  await strategy('SuperDaily/Stg時間當沖','時間當沖');
  assert((await evaluate(`document.querySelectorAll('.logic-sections details').length`))>=3);
  await parameters();
  const basic=`[...document.querySelectorAll('#detail-params details')].find(d=>d.querySelector('summary').textContent.includes('基本'))`;
  assert.equal(await evaluate(`(${basic}).open`),false,'Basic starts collapsed');
  await evaluate(`(${basic}).querySelector('summary').click()`);await frames();
  await evaluate(`document.querySelector('[data-tab="logic"]').click()`);await frames();await parameters();
  assert.equal(await evaluate(`(${basic}).open`),true,'Collapse state survives tab switch');
  await evaluate(`(${basic}).querySelector('summary').click()`);await frames();
  await evaluate(`{const e=document.querySelector('#detail-search');e.value='滑價';e.dispatchEvent(new Event('input',{bubbles:true}));}`);await frames();
  assert.equal(await evaluate(`(${basic}).open`),true,'Search reveals basic matches');
  await evaluate(`{const e=document.querySelector('#detail-search');e.value='';e.dispatchEvent(new Event('input',{bubbles:true}));}`);await frames();
  assert.equal(await evaluate(`(${basic}).open`),false,'Clearing search restores collapse');
  const count=await evaluate(`window.STRATEGY_CATALOG.items.find(i=>i.id==='SuperDaily/Stg時間當沖').parameters.length`);
  assert.equal(await evaluate(`document.querySelectorAll('.param-table tbody tr').length`),count);
  await screenshot('parameters-desktop.png');
  await viewport(390,900,true);const mobileSize=await noPageOverflow();
  await screenshot('parameters-mobile.png');
  await evaluate(`document.querySelector('#back-to-list').click()`);await waitFor(`!!document.querySelector('.strategy-card')`);
  await noPageOverflow();await screenshot('mobile-cdp.png');
  await evaluate(`document.querySelector('[data-favorite]').click()`);await frames();
  assert.equal(await evaluate(`document.querySelector('#favorite-count').textContent`),'1');
  await evaluate(`document.querySelector('[data-view="favorites"]').click()`);await frames();
  assert.equal(await evaluate(`document.querySelectorAll('.strategy-card').length`),1);
  await evaluate(`document.querySelector('.strategy-card [data-favorite]').click()`);await frames();
  assert.equal(await evaluate(`document.querySelector('#favorite-count').textContent`),'0');
  assert.equal(await evaluate(`document.querySelectorAll('.strategy-card').length`),1,'Unfavorite remains available for undo during visit');
  await evaluate(`document.querySelector('.strategy-card [data-favorite]').click()`);await frames();
  await rpc('Page.reload');await waitFor(`document.querySelector('#favorite-count')?.textContent==='1'`);
  assert.equal(networkRequests.filter(url=>url.includes('/.netlify/functions/favorites')).length,0,'Local file must not call cloud');
  await evaluate(`document.querySelector('.strategy-card [data-favorite]').click()`);await frames();
  assert.equal(await evaluate(`document.querySelector('#favorite-count').textContent`),'0');
  if(process.argv.includes('--all')) {
    await viewport(1440,1100);
    await evaluate(`document.querySelector('[data-view="strategies"]').click()`);await frames();
    const meta=await evaluate('window.STRATEGY_CATALOG.meta');
    assert.equal(meta.analysisCount,meta.strategyCount,'Browser must load the complete, current catalog');
    const programCounts=await evaluate(`window.STRATEGY_CATALOG.programs.map(p=>({id:p.id,expected:String(p.strategyCount),actual:[...document.querySelectorAll('.program-list [data-program]')].find(b=>b.dataset.program===p.id)?.querySelector('.count')?.textContent}))`);
    for(const p of programCounts)assert.equal(p.actual,p.expected,p.id+' completed count');
    const items=await evaluate(`window.STRATEGY_CATALOG.items.map(i=>({id:i.id,title:i.title,count:i.parameters.length}))`);
    let rendered=0;
    for (const item of items) {
      await strategy(item.id,item.title);await parameters();
      assert.equal(await evaluate(`document.querySelectorAll('.param-table tbody tr').length`),item.count,item.id);
      await noPageOverflow();
      if(++rendered%50===0)console.log(`Rendered ${rendered}/${items.length}`);
    }
    console.log(`PASS: all ${items.length} strategy parameter tables rendered in Chrome`);
  }
  console.log(JSON.stringify({result:'PASS',mobileSize,parameterCount:count,screenshots:output}));
}
main().catch(async e=>{
  console.error(e);
  if(socket?.readyState===WebSocket.OPEN){
    console.error(JSON.stringify(await evaluate(`({hash:location.hash,title:document.querySelector('.detail-header h1')?.textContent,program:document.querySelector('.detail-header [data-program]')?.dataset.program})`).catch(()=>null)));
    console.error(JSON.stringify(browserLogs.slice(-8)));await screenshot('qa-failure.png').catch(()=>{});
  }
  process.exitCode=1;
}).finally(async()=>{
  if(socket?.readyState===WebSocket.OPEN){await rpc('Browser.close').catch(()=>{});socket.close();}
});
