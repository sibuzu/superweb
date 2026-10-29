import {createHash} from 'node:crypto';
import protocol from '../../favorites-sync.js';
const {allowedOrigin, checkedOperations, validId} = protocol;
const prefix = 'v1/favorite/';
const json = (value, status = 200, extra = {}) => new Response(JSON.stringify(value), {status, headers: {
  'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...extra,
}});

export async function handleFavorites(request, store) {
  const origin = request.headers.get('Origin');
  if (!allowedOrigin(origin, request.url)) return json({error: '此入口的收藏僅儲存在瀏覽器。'}, 403);
  let response;
  if (request.method === 'OPTIONS') response = new Response(null, {status: 204});
  else response = await handleRequest(request, store);
  if (origin) {
    response.headers.set('Access-Control-Allow-Origin', origin);
    response.headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type, If-None-Match');
    response.headers.set('Access-Control-Expose-Headers', 'ETag');
    response.headers.set('Vary', 'Origin');
  }
  return response;
}

async function handleRequest(request, store) {
  if (request.method === 'GET') {
    const favorites = [];
    // Iterate every page; a single list() response is not a complete snapshot.
    for await (const page of store.list({prefix, paginate: true})) {
      const keys = page.blobs.map(blob => blob.key).filter(key => key.startsWith(prefix));
      for (let start = 0; start < keys.length; start += 20) {
        const rows = await Promise.all(keys.slice(start, start + 20).map(async key => {
          let id;
          try { id = decodeURIComponent(key.slice(prefix.length)); } catch (_) { return null; }
          if (!validId(id)) return null;
          const value = await store.get(key, {type: 'json', consistency: 'strong'});
          return typeof value?.on === 'boolean' ? {id, on: value.on} : null;
        }));
        favorites.push(...rows.filter(Boolean));
      }
    }
    favorites.sort((a, b) => a.id.localeCompare(b.id));
    const payload = {schemaVersion: 1, favorites};
    const etag = '"' + createHash('sha256').update(JSON.stringify(payload)).digest('hex') + '"';
    if (request.headers.get('If-None-Match') === etag) return new Response(null, {status: 304, headers: {'ETag': etag, 'Cache-Control': 'no-store'}});
    return json(payload, 200, {'ETag': etag});
  }
  if (request.method !== 'POST') return json({error: '只接受 GET、POST 或 OPTIONS。'}, 405, {'Allow': 'GET, POST, OPTIONS'});
  if (!request.headers.get('Content-Type')?.startsWith('application/json')) return json({error: '請使用 JSON 格式。'}, 415);
  let operations;
  try {
    const text = await request.text();
    if (text.length > 65536) return json({error: '單次收藏資料過大。'}, 413);
    const body = JSON.parse(text);
    if (body.schemaVersion !== 1) throw Error('Unsupported version');
    operations = checkedOperations(body.operations, 100);
    if (!operations.length) throw Error('Empty changes');
  } catch (_) { return json({error: '收藏資料格式不正確。'}, 400); }
  const unique = [...new Map(operations.map(op => [op.id, op])).values()];
  for (const op of unique) {
    // OFF is deliberately retained so old devices cannot resurrect a removal.
    await store.setJSON(prefix + encodeURIComponent(op.id), {on: op.on});
  }
  return json({schemaVersion: 1, applied: unique});
}
