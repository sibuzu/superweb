/* Shared protocol and local-first sync, inspired by TestReview's mark sync. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HftFavorites = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const CLOUD_ORIGIN = 'https://super.sibuzu.com';
  const OUTBOX_KEY = 'hft-atlas-favorite-outbox-v1';
  const isCloudSite = href => { try { return new URL(href).origin === CLOUD_ORIGIN; } catch (_) { return false; } };
  const endpointFor = href => isCloudSite(href) ? '/.netlify/functions/favorites' : null;
  const allowedOrigin = (origin, url) => isCloudSite(url) && (!origin || origin === CLOUD_ORIGIN);
  const validId = id => typeof id === 'string' && id.length <= 200 && id.split('/').length >= 2 && id.split('/').length <= 4 && id.split('/').every(part => /^[\p{L}\p{N}_-]+$/u.test(part));
  function checkedOperations(value, limit = 10000) {
    if (!Array.isArray(value) || value.length > limit) throw Error('收藏資料格式不正確。');
    return value.map(op => {
      if (!op || !validId(op.id) || typeof op.on !== 'boolean') throw Error('收藏資料格式不正確。');
      return {id: op.id, on: op.on};
    });
  }
  function checkedSnapshot(value) {
    if (value?.schemaVersion !== 1) throw Error('雲端收藏版本不相容。');
    return checkedOperations(value.favorites);
  }
  class FavoriteSync {
    constructor({storage, getLocal, apply, status, fetcher, endpoint = endpointFor(globalThis.location?.href)}) {
      Object.assign(this, {storage, getLocal, apply, status, endpoint});
      this.fetcher = fetcher || globalThis.fetch?.bind(globalThis);
      this.localOnly = endpoint === null;
      this.pending = new Map();
      this.sequence = 0;
      this.snapshot = [];
      this.etag = '';
      if (this.localOnly) return;
      try {
        for (const op of checkedOperations(JSON.parse(storage.getItem(OUTBOX_KEY) || '[]'))) this.pending.set(op.id, {...op, seq: ++this.sequence});
      } catch (_) { /* A malformed outbox must not stop reading the catalogue. */ }
    }
    persist() {
      try {
        if (this.pending.size) this.storage.setItem(OUTBOX_KEY, JSON.stringify([...this.pending.values()].map(({seq, ...op}) => op)));
        else this.storage.removeItem(OUTBOX_KEY);
      } catch (_) { /* In-memory changes can still sync while this page stays open. */ }
    }
    queue(id, on) {
      if (this.localOnly) return;
      const [op] = checkedOperations([{id, on}], 1);
      this.pending.set(id, {...op, seq: ++this.sequence});
      this.persist();
      this.status('pending');
      void this.refresh();
    }
    importUnknownLocal() {
      const remote = new Set(this.snapshot.map(op => op.id));
      for (const id of this.getLocal()) {
        if (validId(id) && !remote.has(id) && !this.pending.has(id)) this.pending.set(id, {id, on: true, seq: ++this.sequence});
      }
      this.persist();
    }
    publish() {
      const merged = new Map(this.snapshot.map(op => [op.id, op]));
      for (const op of this.pending.values()) merged.set(op.id, op);
      this.apply([...merged.values()].filter(op => op.on).map(op => op.id));
    }
    refresh() {
      if (this.localOnly) return Promise.resolve();
      if (this.busy) { this.again = true; return this.busy; }
      this.busy = this.run().finally(() => {
        this.busy = null;
        if (this.again) { this.again = false; void this.refresh(); }
      });
      return this.busy;
    }
    async request(options = {}) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      try { return await this.fetcher(this.endpoint, {...options, cache: 'no-store', signal: controller.signal}); }
      finally { clearTimeout(timeout); }
    }
    async run() {
      this.status('syncing');
      try {
        const response = await this.request({headers: this.etag ? {'If-None-Match': this.etag} : {}});
        if (response.status !== 304) {
          if (!response.ok) throw Error('Cloud unavailable');
          this.snapshot = checkedSnapshot(await response.json());
          this.etag = response.headers.get('ETag') || '';
        }
        this.importUnknownLocal();
        this.publish();
        while (this.pending.size) {
          const batch = [...this.pending.values()].slice(0, 100);
          const sent = batch.map(({seq, ...op}) => op);
          const saved = await this.request({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({schemaVersion: 1, operations: sent})});
          if (!saved.ok) throw Error('Cloud write failed');
          const ack = await saved.json();
          if (ack.schemaVersion !== 1 || JSON.stringify(checkedOperations(ack.applied, 100)) !== JSON.stringify(sent)) throw Error('Cloud acknowledgement mismatch');
          for (const op of batch) if (this.pending.get(op.id)?.seq === op.seq) this.pending.delete(op.id);
          const merged = new Map(this.snapshot.map(op => [op.id, op]));
          for (const op of sent) merged.set(op.id, op);
          this.snapshot = [...merged.values()];
          this.etag = '';
          this.persist();
          this.publish();
        }
        this.status('synced');
      } catch (_) { this.status('pending'); }
    }
  }
  return {CLOUD_ORIGIN, OUTBOX_KEY, isCloudSite, endpointFor, allowedOrigin, validId, checkedOperations, checkedSnapshot, FavoriteSync};
});
