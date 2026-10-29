/* Offline, dependency-free strategy library. All rendering uses escaped local data. */
(() => {
  'use strict';
  const data = window.STRATEGY_CATALOG;
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = value => value.toLocaleString('en-US');
  const progressCount = (complete, total) => complete === total ? number(total) : `${number(complete)}/${number(total)}`;
  const programs = new Map(data.programs.map(p => [p.id, p]));
  const items = new Map(data.items.map(i => [i.id, i]));
  const views = {strategies:'全部策略', favorites:'我的收藏', programs:'程式總覽', parameters:'參數索引', compare:'策略比較'};
  const state = {view:'strategies', q:'', program:'', family:'', status:'', progress:'', sort:'program', page:1, layout:'list'};
  const disclosureStates = new Map();
  let selected = [], detailItem = null, detailTab = 'logic', toastTimer, returnSnapshot = null, scrollFrame;
  const favoritesKey = 'hft-atlas-favorites-v1';
  let favorites = new Set(), favoriteVisitIds = null;
  let favoriteSync;
  try {
    const stored = JSON.parse(localStorage.getItem(favoritesKey) || '[]');
    if (Array.isArray(stored)) favorites = new Set(stored.filter(id => typeof id === 'string' && items.has(id)));
  } catch (_) { /* Reading strategies remains available when storage is blocked. */ }
  try { selected = JSON.parse(localStorage.getItem('hft-atlas-compare') || '[]').filter(id => items.has(id)).slice(0, 4); } catch (_) { /* Storage is optional for file://. */ }

  const statusLabel = item => item.registration === 'listed' ? '清單中' : '未在清單中';
  const note = (item, param) => item.analysis?.parameterNotes?.[param.name] || param.description || '';
  const summary = item => item.analysis?.summary || '交易原理待逐項核對；目前已盤點此策略的參數與清單狀態。';
  const completionLabel = item => `<span class="analysis-status ${item.analysisStatus}">${item.analysisStatus==='complete'?'已整理':'待整理'}</span>`;
  const match = (value, query) => query.toLocaleLowerCase().split(/\s+/).filter(Boolean).every(word => value.toLocaleLowerCase().includes(word));
  const itemText = item => [item.title, item.name, item.program, item.family, summary(item), ...(item.parameters.map(p => [p.name,p.label,p.category,note(item,p)].join(' ')))].join(' ');
  const favoriteButton = item => `<button class="favorite-toggle" data-favorite="${escape(item.id)}" aria-pressed="false"></button>`;

  function filtered() {
    return data.items.filter(i => (state.view !== 'favorites' || favorites.has(i.id) || favoriteVisitIds?.has(i.id)) && (!state.program || i.program === state.program) && (!state.family || i.family === state.family) && (!state.status || i.registration === state.status) && (!state.progress || i.analysisStatus === state.progress) && (!state.q || match(itemText(i), state.q))).sort((a,b) => {
      if (state.sort === 'parameters') return b.parameters.length - a.parameters.length || a.id.localeCompare(b.id);
      if (state.sort === 'name') return a.title.localeCompare(b.title, 'zh-Hant');
      return a.program.localeCompare(b.program) || a.title.localeCompare(b.title, 'zh-Hant');
    });
  }

  function toast(message) {
    $('#toast').textContent = message;
    $('#toast').classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 2600);
  }

  function updateSelection() {
    $('#compare-count').textContent = selected.length;
    $('#favorite-count').textContent = favorites.size;
    $$('[data-favorite]').forEach(button => {
      const active = favorites.has(button.dataset.favorite);
      const label = active ? '取消收藏' : '加入收藏';
      button.classList.toggle('selected', active);
      button.setAttribute('aria-pressed', String(active));
      button.setAttribute('aria-label', `${label} ${items.get(button.dataset.favorite).title}`);
      button.title = label;
      button.textContent = active ? '★ 已收藏' : '☆ 收藏';
    });
    $$('[data-compare]').forEach(button => {
      const active = selected.includes(button.dataset.compare);
      button.classList.toggle('selected', active);
      button.setAttribute('aria-pressed', String(active));
      button.textContent = active ? '✓ 已加入比較' : '+ 加入比較';
    });
    try { localStorage.setItem('hft-atlas-compare', JSON.stringify(selected)); } catch (_) { /* Optional. */ }
  }

  function toggleCompare(id) {
    if (selected.includes(id)) selected = selected.filter(x => x !== id);
    else if (selected.length >= 4) return toast('最多同時比較 4 個策略');
    else selected.push(id);
    updateSelection();
    if (state.view === 'compare') render();
  }

  function toggleFavorite(id) {
    if (!items.has(id)) return;
    const next = new Set(favorites);
    if (next.has(id)) next.delete(id); else next.add(id);
    try { localStorage.setItem(favoritesKey, JSON.stringify([...next])); }
    catch (_) { if (!favoriteSync || favoriteSync.localOnly) { toast('無法儲存收藏，請檢查瀏覽器儲存設定。'); return; } }
    favorites = next;
    favoriteSync?.queue(id, next.has(id));
    if (state.view === 'favorites') {
      favoriteVisitIds ||= new Set();
      for (const key of favorites) favoriteVisitIds.add(key);
    }
    if (detailItem) updateSelection(); else render();
    toast(favorites.has(id) ? '已加入我的收藏' : '已取消收藏，可再按 ☆ 復原');
  }

  function startFavoriteSync() {
    const api = window.HftFavorites;
    if (!api) return;
    const button = $('#favorite-sync');
    const cloud = api.isCloudSite(location.href);
    $('.workspace-label span').textContent = cloud ? '雲端' : '本機';
    const labels = {local:'收藏僅存本機', syncing:'收藏同步中…', synced:'收藏已同步', pending:'收藏待同步 · 重試'};
    const storage = {
      getItem: key => localStorage.getItem(key),
      setItem: (key, value) => localStorage.setItem(key, value),
      removeItem: key => localStorage.removeItem(key),
    };
    favoriteSync = new api.FavoriteSync({storage, getLocal: () => [...favorites],
      apply: ids => {
        const next = new Set(ids.filter(id => items.has(id)));
        if (next.size === favorites.size && [...next].every(id => favorites.has(id))) return;
        favorites = next;
        try { localStorage.setItem(favoritesKey, JSON.stringify([...favorites])); } catch (_) { /* Cloud state can still be used in memory. */ }
        if (state.view === 'favorites') {
          favoriteVisitIds ||= new Set();
          for (const id of favorites) favoriteVisitIds.add(id);
        }
        if (detailItem) updateSelection(); else render();
      },
      status: state => {
        button.textContent = labels[state];
        button.dataset.sync = state;
        button.disabled = !cloud;
        button.title = cloud ? '共用同一份雲端收藏；點擊可立即同步。未送出的變更先保留在本機，連線恢復後重試。' : '此網域與本機開啟只使用目前瀏覽器，不讀寫雲端收藏。';
      },
    });
    if (!cloud) { button.title = '此網域與本機開啟只使用目前瀏覽器，不讀寫雲端收藏。'; return; }
    const refresh = () => { if (document.visibilityState !== 'hidden') void favoriteSync.refresh(); };
    button.addEventListener('click', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('online', refresh);
    document.addEventListener('visibilitychange', refresh);
    setInterval(refresh, 60000);
    refresh();
  }

  function renderSidebar() {
    const query = $('#program-search').value;
    $('.sidebar').classList.toggle('reading', !!detailItem);
    $('#program-search').hidden = !!detailItem;
    $('#clear-program').textContent = detailItem ? '全部程式' : '全部';
    if (detailItem) {
      let list = filtered().filter(i=>i.program===detailItem.program);
      if (!list.some(i=>i.id===detailItem.id)) list = data.items.filter(i=>i.program===detailItem.program);
      $('#program-heading').textContent = `${programs.get(detailItem.program).name} · ${list.length} 個策略`;
      $('#program-list').setAttribute('aria-label', `${detailItem.program} 策略導覽`);
      $('#program-list').innerHTML = list.map(i=>`<button class="strategy-nav-link ${i.id===detailItem.id?'active':''}" data-detail="${escape(i.id)}" ${i.id===detailItem.id?'aria-current="page"':''}>${escape(i.title)}</button>`).join('');
    } else {
      $('#program-heading').textContent = '依程式瀏覽';
      $('#program-list').setAttribute('aria-label', '程式目錄');
      $('#program-list').innerHTML = data.programs.filter(p => !query || match(p.name, query)).map(p => `<button data-program="${escape(p.id)}" class="${state.program === p.id ? 'active' : ''}" title="已整理 ${progressCount(p.completedCount, p.strategyCount)}"><span class="program-icon">${escape(p.name.replace('Super','').slice(0,2))}</span>${escape(p.name)}<span class="count">${progressCount(p.completedCount, p.strategyCount)}</span></button>`).join('');
    }
    const activeView = detailItem ? (returnSnapshot?.state?.view === 'favorites' ? 'favorites' : 'strategies') : state.view;
    $$('.main-nav [data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === activeView));
  }

  function renderFilters() {
    $('#program-filter').value = state.program;
    $('#family-filter').value = state.family;
    $('#status-filter').value = state.status;
    $('#progress-filter').value = state.progress;
    $('#sort-filter').value = state.sort;
    const chips = [];
    if (state.program) chips.push(['program',programs.get(state.program)?.name || state.program]);
    if (state.family) chips.push(['family',state.family]);
    if (state.status) chips.push(['status',state.status === 'listed' ? '清單中' : '未在清單中']);
    if (state.progress) chips.push(['progress',state.progress === 'complete' ? '已整理' : '待整理']);
    if (state.q) chips.push(['q',`搜尋：${state.q}`]);
    $('#active-filters').innerHTML = chips.map(([key,value]) => `<button class="filter-chip" data-clear="${key}">${escape(value)}<span>×</span></button>`).join('');
    $('.filters').hidden = state.view === 'compare';
    $('#active-filters').hidden = state.view === 'compare';
    $('#status-filter').hidden = state.view === 'programs';
    $('#layout-switch').hidden = !['strategies','favorites'].includes(state.view);
    $$('[data-layout]').forEach(b=>{b.classList.toggle('active',b.dataset.layout===state.layout);b.setAttribute('aria-pressed',String(b.dataset.layout===state.layout));});
  }

  function empty(title, text) {
    return `<div class="empty"><h3>${title}</h3><p>${text}</p><button data-reset>清除篩選</button></div>`;
  }

  function cards(list) {
    return `<div class="strategy-${state.layout}">${list.map(i => `<article class="strategy-card">
      <div class="card-main" data-card-detail="${escape(i.id)}" role="link" tabindex="0" aria-label="閱讀 ${escape(i.title)}">
      <div class="card-top"><span class="program-tag" data-program="${escape(i.program)}">${escape(programs.get(i.program).name)}</span></div>
      <div class="card-location">${escape(i.family)} <span>/</span> ${i.parameters.length} 個參數 · ${new Set(i.parameters.map(p=>p.category)).size} 個分類</div>
      <h2 class="card-title"><a href="#strategy/${encodeURIComponent(i.id)}" data-detail="${escape(i.id)}">${escape(i.title)}</a></h2>
      <p class="card-description">${escape(summary(i))}</p></div>
      <div class="card-bottom"><div class="card-status">${completionLabel(i)}<span class="status-label ${i.registration}">${statusLabel(i)}</span></div><div class="card-foot-actions">${favoriteButton(i)}<button class="compare-toggle" data-compare="${escape(i.id)}" aria-pressed="false">+ 加入比較</button><button data-detail="${escape(i.id)}" aria-label="閱讀 ${escape(i.title)}">→</button></div></div>
    </article>`).join('')}</div>`;
  }

  function renderPrograms(list) {
    const ids = new Set(list.map(i=>i.program));
    const matches = data.programs.filter(p => ids.has(p.id));
    return matches.length ? `<div class="programs-grid">${matches.map(p => {
      const strategies = list.filter(i=>i.program===p.id);
      return `<article class="program-card"><div class="eyebrow">PROGRAM PROFILE</div><h3>${escape(p.name)}</h3><p class="program-description">${escape(p.overview || '交易概況待逐項核對。此程式已盤點 '+p.strategyCount+' 個策略，參數與清單狀態可先瀏覽。')}</p><div class="numbers"><span><strong>${strategies.length}</strong>個策略</span><span><strong>${progressCount(p.completedCount, p.strategyCount)}</strong>已整理</span><span><strong>${number(strategies.reduce((s,i)=>s+i.parameters.length,0))}</strong>個完整參數</span></div><div class="families">${Object.keys(p.families).map(f=>`<span class="family-badge">${escape(f)}</span>`).join('')}</div><button data-program="${escape(p.id)}">查看策略 <span>→</span></button></article>`;
    }).join('')}</div>` : empty('沒有符合的程式','請調整搜尋或篩選條件。');
  }

  function parameterRows(list) {
    const rows = [];
    for (const item of list) for (const p of item.parameters) {
      if (!state.q || match([item.title,item.program,p.name,p.label,p.category,note(item,p)].join(' '),state.q)) rows.push({item,p});
    }
    return rows;
  }

  function renderParameterIndex(rows) {
    if (!rows.length) return empty('找不到符合的參數','可搜尋參數名稱、分類、策略名稱或參數解說。');
    const pageSize = 30, pages = Math.ceil(rows.length / pageSize);
    state.page = Math.max(1,Math.min(state.page,pages));
    const start = (state.page-1)*pageSize;
    const page = rows.slice(start,start+pageSize);
    $('#pagination').innerHTML = `<span>${start+1}–${Math.min(start+pageSize,rows.length)} / ${number(rows.length)} 個參數</span><div><button data-page="${state.page-1}" ${state.page===1?'disabled':''}>← 上一頁</button><span>${state.page} / ${pages}</span><button data-page="${state.page+1}" ${state.page===pages?'disabled':''}>下一頁 →</button></div>`;
    return `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>Category 分類</th><th>參數</th><th>所屬策略</th><th>作用與選項</th></tr></thead><tbody>${page.map(({item,p})=>`<tr class="table-click"><td><span class="category-pill">${escape(p.category)}</span></td><td><span class="index-name">${escape(p.label)}</span><span class="secondary">${escape(p.type)}</span></td><td><button data-detail="${escape(item.id)}" data-detail-tab="parameters">${escape(item.title)}</button><span class="secondary">${escape(item.program)}</span></td><td>${escape(note(item,p) || '程式未附文字說明。')}${renderOptions(p)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function renderOptions(param) {
    return param.options.length ? `<div class="options"><span>可用選項</span>${param.options.map(o=>`<code>${escape(o)}</code>`).join('')}</div>` : '';
  }

  function compareTable() {
    const list = selected.map(id=>items.get(id)).filter(Boolean);
    if (!list.length) return `<div class="empty"><h3>把策略，放在一起看。</h3><p>最多加入4個策略，即可比較交易原理、進出場及完整參數。</p><button id="compare-all">加入目前篩選的策略（最多4個）</button></div>`;
    const categoryOf = new Map();
    for (const item of list) for (const p of item.parameters) if (!categoryOf.has(p.name)) categoryOf.set(p.name,p.category);
    const names = [...categoryOf.keys()];
    const categories = [...new Set(categoryOf.values())];
    const params = list.map(i=>new Map(i.parameters.map(p=>[p.name,p])));
    const value = (item,p) => p ? [p.type,p.category,note(item,p),p.options.join('、')].join('|') : null;
    const headers = list.map(i=>`<th><span class="program-tag">${escape(i.program)}</span><strong>${escape(i.title)}</strong><button data-remove="${escape(i.id)}">移除 ×</button></th>`).join('');
    let body = [['交易原理',i=>summary(i)],['進場條件',i=>i.analysis?.entry?.join('\n') || '整理中'],['出場機制',i=>i.analysis?.exit?.join('\n') || '整理中'],['策略清單',i=>statusLabel(i)]].map(([label,get])=>`<tr><td>${label}</td>${list.map(i=>`<td class="compare-prose">${escape(get(i))}</td>`).join('')}</tr>`).join('');
    for (const category of categories) {
      body += `<tr class="comparison-group"><td colspan="${list.length+1}">${escape(category)}</td></tr>`;
      for (const name of names.filter(n=>categoryOf.get(n)===category)) {
        const cells = list.map((i,j)=>params[j].get(name));
        const different = new Set(cells.map((p,j)=>value(list[j],p))).size>1;
        body += `<tr class="${different?'different':''}"><td>${escape(cells.find(Boolean).label)}<span class="secondary">${escape(name)}</span></td>${cells.map((p,j)=>`<td>${p ? `<code>${escape(p.type)}</code><p class="compare-note">${escape(note(list[j],p)||'程式未附文字說明。')}</p>${renderOptions(p)}` : '<span class="muted">此策略沒有這個參數</span>'}</td>`).join('')}</tr>`;
      }
    }
    return `<div class="compare-intro"><p class="hint">依參數名稱對齊，並依 Category 分組；淡黃色列表示參數內容不同或某策略沒有該參數。</p><button id="clear-compare">清空比較</button></div><div class="data-table-wrap"><table class="data-table compare-table"><thead><tr><th>比較項目</th>${headers}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function render() {
    if (detailItem) { renderSidebar(); updateSelection(); return; }
    const list = filtered();
    $('#list-page').hidden=false;$('#strategy-page').hidden=true;$('#main').classList.remove('reading-strategy');
    renderSidebar(); renderFilters();
    $('#pagination').innerHTML = '';
    const label=state.view==='strategies'&&state.program?programs.get(state.program).name:views[state.view];
    $('#breadcrumb').innerHTML=`<a href="#strategies">我的研究空間</a><span>/</span><strong aria-current="page">${escape(label)}</strong>`;
    $('#page-title').textContent=label;
    document.title=`${label} · HFT 策略筆記`;
    let count = `${list.length} 個策略`;
    if (state.view === 'strategies' || state.view === 'favorites') $('#content').innerHTML = list.length ? cards(list) : state.view === 'favorites' && !favorites.size ? '<div class="empty"><h3>還沒有收藏策略</h3><p>在策略旁點 ☆，就能在這裡快速找回。</p><button data-view="strategies">瀏覽全部策略</button></div>' : empty('沒有符合的策略','試試其他關鍵字，或清除篩選。');
    if (state.view === 'programs') { $('#content').innerHTML = renderPrograms(list); count = `${new Set(list.map(i=>i.program)).size} 個程式`; }
    if (state.view === 'parameters') { const rows=parameterRows(list); $('#content').innerHTML=renderParameterIndex(rows); count=`${number(rows.length)} 個參數`; }
    if (state.view === 'compare') { $('#content').innerHTML=compareTable(); count=`${selected.length} 個策略`; }
    $('#result-count').textContent = count;
    updateSelection();
  }

  function listHash() {
    return '#'+state.view+(state.program?'?program='+encodeURIComponent(state.program):'');
  }

  function snapshot() {
    return {state:{...state},scroll:window.scrollY,hash:listHash()};
  }

  function goToList(view=state.view,program,restore=null,push=true) {
    detailItem=null;
    if(restore?.state)Object.assign(state,restore.state);
    else {state.view=view;state.page=1;if(program!==undefined)state.program=program;}
    if (state.view === 'favorites') favoriteVisitIds ||= new Set(favorites);
    else favoriteVisitIds = null;
    $('#search').value=state.q;
    render();
    if(push)history.pushState({listSnapshot:{...snapshot(),scroll:restore?.scroll||0}},'',listHash());
    cancelAnimationFrame(scrollFrame);
    scrollFrame=requestAnimationFrame(()=>window.scrollTo(0,restore?.scroll||0));
  }

  function openDetail(id,tab='logic',push=true) {
    const item = items.get(id);
    if (!item) return;
    if(push) {
      if(!detailItem){returnSnapshot=snapshot();history.replaceState({listSnapshot:returnSnapshot},'',location.href);}
      history.pushState({returnTo:returnSnapshot},'',`#strategy/${encodeURIComponent(id)}`);
    } else returnSnapshot=history.state?.returnTo||{state:{...state,view:'strategies',program:item.program,q:'',family:'',status:'',page:1},scroll:0};
    detailItem=item; detailTab=tab;
    $('#list-page').hidden=true;$('#strategy-page').hidden=false;$('#main').classList.add('reading-strategy');
    $('#detail-content').innerHTML = `<header class="detail-header"><div class="detail-subject"><span class="program-tag" data-program="${escape(item.program)}">${escape(item.program)}</span><div class="detail-actions">${favoriteButton(item)}<button class="compare-toggle" data-compare="${escape(item.id)}" aria-pressed="false">+ 加入比較</button></div></div><h1>${escape(item.title)}</h1><div class="detail-badges">${completionLabel(item)}<span>${escape(item.family)}</span><span class="status-label ${item.registration}">${statusLabel(item)}</span><span>${item.parameters.length} 個完整參數 · ${new Set(item.parameters.map(p=>p.category)).size} 個分類</span>${item.inherits.length?`<span>繼承自策略 ${escape(item.inherits.join(' → '))}</span>`:''}</div><p>${escape(summary(item))}</p></header><div class="detail-body"><div class="detail-toolbar"><button data-tab="logic">交易原理</button><button data-tab="parameters">完整參數 <span>${item.parameters.length}</span></button></div><div id="detail-panel"></div></div>`;
    $('#breadcrumb').innerHTML=`<a href="#strategies">我的研究空間</a><span>/</span><a href="${escape(returnSnapshot?.hash||'#strategies')}" data-return>${escape(returnSnapshot?.state?.view === 'favorites' ? '我的收藏' : item.program)}</a><span>/</span><strong aria-current="page">${escape(item.title)}</strong>`;
    const peers=data.items.filter(i=>i.program===item.program);
    $('#reading-position').textContent=`${peers.findIndex(i=>i.id===id)+1} / ${peers.length} 個策略`;
    document.title=`${item.title} · HFT 策略筆記`;
    renderSidebar();
    renderDetailTab();
    updateSelection();
    cancelAnimationFrame(scrollFrame);
    window.scrollTo(0,0);$('#detail-content').focus({preventScroll:true});
  }

  function disclosure(key, className, heading, content, defaultOpen=true, forceOpen=false) {
    const id=JSON.stringify([detailItem.id,detailTab,key]);
    const open=forceOpen||(disclosureStates.get(id)??defaultOpen);
    return `<details class="${className} collapsible-section" data-disclosure="${escape(id)}" ${forceOpen?'data-filter-open="true"':''} ${open?'open':''}><summary class="section-summary">${heading}<span class="collapse-chevron" aria-hidden="true"></span></summary><div class="section-body">${content}</div></details>`;
  }

  function renderDetailTab() {
    $$('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===detailTab));
    const panel=$('#detail-panel'), item=detailItem;
    if(detailTab==='parameters') {
      const cats=[...new Set(item.parameters.map(p=>p.category))];
      panel.innerHTML=`<div class="detail-filters"><input id="detail-search" type="search" placeholder="搜尋這個策略的參數…" aria-label="搜尋策略參數"><select id="detail-category" aria-label="依Category篩選"><option value="">全部 Category</option>${cats.map(c=>`<option>${escape(c)}</option>`).join('')}</select></div><p class="hint">參數依 Category 分組；每一項皆視為此策略的完整參數。</p><div id="detail-params"></div>`;
      renderDetailParameters();
      return;
    }
    const analysis=item.analysis;
    if(!analysis) {panel.innerHTML='<div class="notes">交易原理解說整理中。</div>';return;}
    const sections=[['entry','01','如何進場','ENTRY LOGIC'],['exit','02','如何出場','EXIT & PROTECTION'],['mechanics','03','部位與執行細節','EXECUTION MECHANICS']];
    const flow=analysis.flow?.length?disclosure('flow','extra-section','<h3>交易流程</h3>',`<div class="trade-flow">${analysis.flow.map((s,n)=>`<div><span>${String(n+1).padStart(2,'0')}</span><p>${escape(s)}</p></div>`).join('')}</div>`):'';
    const mainSections=sections.filter(([key])=>analysis[key]?.length).map(([key,n,title,en])=>disclosure(key,'logic-section',`<div class="logic-heading"><span>${n}</span><div><span>${en}</span><h3>${title}</h3></div></div>`,`<ol>${analysis[key].map(s=>`<li>${escape(s)}</li>`).join('')}</ol>`)).join('');
    const extraSections=analysis.sections?.map((s,n)=>disclosure(`extra-${n}`,'extra-section',`<h3>${escape(s.title)}</h3>`,s.body.map(p=>`<p>${escape(p)}</p>`).join(''))).join('')||'';
    const example=analysis.example?disclosure('example','example-block',`<div class="summary-title"><div class="eyebrow">WALKTHROUGH</div><h3>${escape(analysis.example.title||'用一筆交易理解')}</h3></div>`,typeof analysis.example==='string'?`<p>${escape(analysis.example)}</p>`:`<ol>${analysis.example.steps.map(s=>`<li>${escape(s)}</li>`).join('')}</ol>`):'';
    const caveats=analysis.caveats?.length?disclosure('caveats','reading-notes','<h3>閱讀這份實作時要留意</h3>',`<ul>${analysis.caveats.map(s=>`<li>${escape(s)}</li>`).join('')}</ul>`):'';
    panel.innerHTML=`${flow}<div class="logic-sections">${mainSections}</div>${extraSections}${example}${caveats}<div class="logic-next"><p>接著看控制這些條件的參數。</p><button data-tab="parameters">依 Category 瀏覽完整參數 →</button></div>`;
  }

  function renderDetailParameters() {
    const query=$('#detail-search').value, category=$('#detail-category').value, item=detailItem;
    const params=item.parameters.filter(p=>(!category||p.category===category)&&(!query||match([p.name,p.label,p.type,p.category,note(item,p),...p.options].join(' '),query)));
    const groups=[...new Set(params.map(p=>p.category))];
    $('#detail-params').innerHTML=groups.length?groups.map(c=>{
      const group=params.filter(p=>p.category===c);
      const heading=`<h3><span class="category-square"></span>${escape(c)}<small>${group.length} 個參數</small></h3>`;
      const table=`<div class="data-table-wrap"><table class="data-table param-table"><thead><tr><th>參數</th><th>型別</th><th>作用與選項</th></tr></thead><tbody>${group.map(p=>`<tr><td><strong>${escape(p.label)}</strong>${p.label!==p.name?`<span class="secondary">${escape(p.name)}</span>`:''}</td><td><code>${escape(p.type)}</code></td><td>${escape(note(item,p)||'程式未附文字說明。')}${renderOptions(p)}</td></tr>`).join('')}</tbody></table></div>`;
      return disclosure(c,'parameter-section',heading,table,c!=='基本',!!query||!!category);
    }).join(''):'<div class="empty"><p>沒有符合的參數。</p></div>';
  }

  function exportCsv() {
    let rows;
    if(state.view==='parameters') rows=[['程式','策略','Category','參數','型別','作用','選項'],...parameterRows(filtered()).map(({item,p})=>[item.program,item.title,p.category,p.label,p.type,note(item,p),p.options.join('；')])];
    else {
      const list=state.view==='compare'?selected.map(id=>items.get(id)):filtered();
      rows=[['程式','策略','類型','策略清單','交易原理','進場條件','出場機制','參數數量'],...list.map(i=>[i.program,i.title,i.family,statusLabel(i),summary(i),i.analysis?.entry?.join('\n')||'',i.analysis?.exit?.join('\n')||'',i.parameters.length])];
    }
    const csv='\uFEFF'+rows.map(row=>row.map(cell=>`"${String(cell??'').replace(/"/g,'""')}"`).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'}));
    const link=document.createElement('a');link.href=url;link.download=`hft-${state.view}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
    toast('已匯出目前結果');
  }

  function reset() { Object.assign(state,{q:'',program:'',family:'',status:'',progress:'',sort:'program',page:1}); $('#search').value=''; render(); }
  function applyRoute() {
    const hash=location.hash.slice(1);
    let id=null;
    try {
      if(hash.startsWith('strategy/'))id=decodeURIComponent(hash.slice(9));
      else if(hash.startsWith('strategy='))id=new URLSearchParams(hash).get('strategy');
    } catch (_) { /* An invalid route returns to the list. */ }
    if(id&&items.has(id)){openDetail(id,'logic',false);return;}
    const [view,query='']=hash.split('?');
    const restored=history.state?.listSnapshot;
    if(restored?.state){goToList(restored.state.view,undefined,restored,false);return;}
    const program=new URLSearchParams(query).get('program')||'';
    goToList(views[view]?view:'strategies',programs.has(program)?program:'',null,false);
  }
  document.addEventListener('click',event=>{
    const returnLink=event.target.closest('[data-return]');
    if(returnLink){event.preventDefault();goToList('strategies',undefined,returnSnapshot);return;}
    const button=event.target.closest('button,a[data-detail],[data-card-detail]');
    if(!button)return;
    if(button.dataset.view) {
      if (button.dataset.view === 'favorites') Object.assign(state,{q:'',program:'',family:'',status:'',progress:''});
      goToList(button.dataset.view,['strategies','favorites'].includes(button.dataset.view)?'':undefined);return;
    }
    if(button.dataset.program) {goToList('strategies',button.dataset.program);return;}
    if(button.dataset.layout){state.layout=button.dataset.layout;render();return;}
    if(button.hasAttribute('data-clear')){state[button.dataset.clear]='';state.page=1;if(button.dataset.clear==='q')$('#search').value='';render();}
    if(button.dataset.favorite){toggleFavorite(button.dataset.favorite);return;}
    if(button.dataset.compare)toggleCompare(button.dataset.compare);
    if(button.dataset.remove){selected=selected.filter(x=>x!==button.dataset.remove);render();}
    if(button.dataset.detail||button.dataset.cardDetail){
      if(button.tagName==='A'&&(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey))return;
      event.preventDefault();openDetail(button.dataset.detail||button.dataset.cardDetail,button.dataset.detailTab||'logic');return;
    }
    if(button.dataset.close)$('#'+button.dataset.close).close();
    if(button.dataset.tab){detailTab=button.dataset.tab;renderDetailTab();}
    if(button.dataset.page){state.page=Number(button.dataset.page);render();$('.list-heading').scrollIntoView({block:'start'});}
    if(button.hasAttribute('data-reset')||button.id==='reset')reset();
    if(button.id==='clear-program'){goToList('strategies','');}
    if(button.id==='back-to-list'){goToList('strategies',undefined,returnSnapshot);}
    if(button.id==='about-button')$('#about-dialog').showModal();
    if(button.id==='export-button')exportCsv();
    if(button.id==='clear-compare'){selected=[];render();}
    if(button.id==='compare-all'){selected=filtered().map(i=>i.id).slice(0,4);render();}
  });
  $('#search').addEventListener('input',()=>{state.q=$('#search').value.trim();state.page=1;render();});
  $('#program-search').addEventListener('input',renderSidebar);
  for(const [id,key] of [['program-filter','program'],['family-filter','family'],['status-filter','status'],['progress-filter','progress'],['sort-filter','sort']])$('#'+id).addEventListener('change',e=>{state[key]=e.target.value;state.page=1;render();});
  document.addEventListener('input',e=>{if(e.target.id==='detail-search')renderDetailParameters();});
  document.addEventListener('change',e=>{if(e.target.id==='detail-category')renderDetailParameters();});
  document.addEventListener('toggle',e=>{
    const section=e.target;
    if(section.matches('details[data-disclosure]')&&section.isConnected&&section.dataset.filterOpen!=='true')disclosureStates.set(section.dataset.disclosure,section.open);
  },true);
  document.addEventListener('keydown',e=>{
    if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-card-detail]')){e.preventDefault();openDetail(e.target.dataset.cardDetail);}
    if(e.key==='/'&&!detailItem&&!$('dialog[open]')&&!/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();$('#search').focus();}
  });
  for(const dialog of $$('dialog'))dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  $('#program-filter').innerHTML+=[...data.programs].map(p=>`<option value="${escape(p.id)}">${escape(p.name)}</option>`).join('');
  $('#family-filter').innerHTML+=[...new Set(data.items.map(i=>i.family))].map(f=>`<option>${escape(f)}</option>`).join('');
  $('#nav-count').textContent=data.items.length;
  $('.local-label').innerHTML=`<span class="status-dot"></span>已整理 ${progressCount(data.meta.analysisCount, data.meta.strategyCount)} · ${data.programs.length} 個程式`;
  $('#generated-at').textContent=`更新 ${new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(data.meta.generatedAt))}`;
  $('#about-scope').textContent=data.meta.scope;
  window.addEventListener('hashchange',applyRoute);
  if('scrollRestoration' in history)history.scrollRestoration='manual';
  applyRoute();
  startFavoriteSync();
})();
