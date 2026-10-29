import test from 'node:test';
import assert from 'node:assert/strict';
import protocol from '../favorites-sync.js';
import {handleFavorites} from '../netlify/lib/shared-favorites.mjs';

const {FavoriteSync, OUTBOX_KEY, endpointFor, checkedOperations} = protocol;
const origin = 'https://super.sibuzu.com';
const endpoint = origin + '/.netlify/functions/favorites';
const A = 'SuperBDS/StgBDSXv6', B = 'SuperDaily/Stg時間當沖';
const storage = () => {
  const data = new Map();
  return {data, getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key)};
};
function store() {
  const values = new Map();
  return {values,
    async *list({prefix, paginate}) {
      assert.equal(paginate, true);
      // One item per page deliberately exercises complete snapshot pagination.
      for (const key of values.keys()) if (key.startsWith(prefix)) yield {blobs: [{key}]};
    },
    get: async key => values.get(key),
    setJSON: async (key, value) => values.set(key, value),
  };
}
const post = (operations, extra = {}) => new Request(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json', Origin: origin, ...extra}, body: JSON.stringify({schemaVersion: 1, operations})});
const localKey = 'favorites';
function client(shared, cached = [], options = {}) {
  const disk = options.storage || storage();
  let favorites = cached;
  const statuses = [];
  let calls = 0;
  const sync = new FavoriteSync({storage: disk, endpoint: endpointFor(options.href || origin),
    getLocal: () => favorites,
    apply: ids => { favorites = ids; disk.setItem(localKey, JSON.stringify(ids)); },
    status: value => statuses.push(value),
    fetcher: async (url, init) => { calls++; return options.fetcher ? options.fetcher(url, init) : handleFavorites(new Request(new URL(url, origin), init), shared); },
  });
  const settle = async () => { while (sync.busy) await sync.busy; };
  return {sync, disk, statuses, settle, get calls() { return calls; }, get favorites() { return favorites; }, set favorites(value) { favorites = value; }};
}

test('only the exact HTTPS domain uses the cloud; other domains do not fetch or queue', async () => {
  assert.equal(endpointFor(origin), '/.netlify/functions/favorites');
  for (const href of ['file:///D:/git/hft/site/index.html', 'http://localhost:8765', 'https://other.sibuzu.com', 'https://super.sibuzu.com.evil.example', 'https://super.sibuzu.com:444', 'http://super.sibuzu.com']) {
    assert.equal(endpointFor(href), null);
    const c = client(store(), [], {href});
    c.sync.queue(A, true); await c.sync.refresh();
    assert.equal(c.calls, 0); assert.equal(c.disk.getItem(OUTBOX_KEY), null);
  }
});

test('protocol accepts Chinese strategy IDs and rejects malformed or excessive changes', () => {
  assert.deepEqual(checkedOperations([{id: B, on: true}]), [{id: B, on: true}]);
  for (const value of [[{id: '../bad', on: true}], [{id: 'bad', on: true}], [{id: A, on: 'yes'}], null]) assert.throws(() => checkedOperations(value));
  assert.throws(() => checkedOperations(Array(101).fill({id: A, on: true}), 100));
});

test('endpoint isolates domains and rejects bad methods, content types and bodies', async () => {
  const db = store();
  assert.equal((await handleFavorites(new Request('https://preview.netlify.app/.netlify/functions/favorites'), db)).status, 403);
  assert.equal((await handleFavorites(new Request(endpoint, {headers: {Origin: 'https://other.example'}}), db)).status, 403);
  assert.equal((await handleFavorites(new Request(endpoint, {method: 'PUT'}), db)).status, 405);
  assert.equal((await handleFavorites(new Request(endpoint, {method: 'POST', body: '{}'}), db)).status, 415);
  assert.equal((await handleFavorites(post([{id: '../bad', on: true}]), db)).status, 400);
  assert.equal((await handleFavorites(post([]), db)).status, 400);
  const preflight = await handleFavorites(new Request(endpoint, {method: 'OPTIONS', headers: {Origin: origin}}), db);
  assert.equal(preflight.status, 204); assert.equal(preflight.headers.get('Access-Control-Allow-Origin'), origin);
});

test('different strategy writes stay independent, snapshots include all pages and ETags', async () => {
  const db = store();
  await Promise.all([handleFavorites(post([{id: A, on: true}]), db), handleFavorites(post([{id: B, on: true}]), db)]);
  const response = await handleFavorites(new Request(endpoint), db);
  assert.equal((await response.json()).favorites.length, 2);
  assert.equal((await handleFavorites(new Request(endpoint, {headers: {'If-None-Match': response.headers.get('ETag')}}), db)).status, 304);
  assert.equal(db.values.size, 2);
});

test('first sync uploads existing local favorites and another browser loads them', async () => {
  const db = store(), first = client(db, [A, B]);
  await first.sync.refresh();
  assert.deepEqual(new Set(first.favorites), new Set([A, B]));
  assert.equal(first.statuses.at(-1), 'synced'); assert.equal(first.disk.getItem(OUTBOX_KEY), null);
  const second = client(db); await second.sync.refresh();
  assert.deepEqual(new Set(second.favorites), new Set([A, B]));
});

test('OFF tombstones prevent stale local choices from resurrecting removed favorites', async () => {
  const db = store();
  await handleFavorites(post([{id: A, on: false}]), db);
  const c = client(db, [A]); await c.sync.refresh();
  assert.deepEqual(c.favorites, []);
  assert.equal([...db.values.values()][0].on, false);
});

test('offline changes persist in the outbox, survive reload and retry', async () => {
  const db = store(), disk = storage();
  const offline = client(db, [A], {storage: disk, fetcher: async () => { throw Error('offline'); }});
  offline.sync.queue(A, true); await offline.settle();
  assert.deepEqual(JSON.parse(disk.getItem(OUTBOX_KEY)), [{id: A, on: true}]);
  assert.equal(offline.statuses.at(-1), 'pending');
  const retry = client(db, [A], {storage: disk}); await retry.sync.refresh();
  assert.equal(retry.statuses.at(-1), 'synced'); assert.equal(disk.getItem(OUTBOX_KEY), null);
  assert.equal([...db.values.values()][0].on, true);
});

test('a toggle during an in-flight POST keeps the latest choice', async () => {
  const db = store();
  let release, entered;
  const started = new Promise(resolve => { entered = resolve; });
  const c = client(db, [], {fetcher: async (url, init) => {
    if (init.method === 'POST' && !release) { entered(); await new Promise(resolve => { release = resolve; }); }
    return handleFavorites(new Request(new URL(url, origin), init), db);
  }});
  c.favorites = [A]; c.sync.queue(A, true); await started;
  c.favorites = []; c.sync.queue(A, false); release(); await c.settle();
  assert.equal([...db.values.values()][0].on, false); assert.deepEqual(c.favorites, []);
  assert.equal(c.sync.pending.size, 0);
});

test('failed or incorrect acknowledgements never clear pending operations', async () => {
  for (const status of [404, 503, 200]) {
    const c = client(store(), [A], {fetcher: async (url, init) => init.method === 'POST'
      ? new Response(JSON.stringify({schemaVersion: 1, applied: []}), {status})
      : new Response(JSON.stringify({schemaVersion: 1, favorites: []}))});
    c.sync.queue(A, true); await c.settle();
    assert.equal(c.sync.pending.size, 1); assert.equal(c.statuses.at(-1), 'pending');
  }
});

test('more than one POST batch is sent without dropping favorites', async () => {
  const ids = Array.from({length: 125}, (_, n) => `Program/Stg${n}`), db = store();
  const c = client(db, ids); await c.sync.refresh();
  assert.equal(db.values.size, 125); assert.equal(c.sync.pending.size, 0); assert.equal(c.favorites.length, 125);
});
