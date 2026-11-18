/* Alhambra audio guide service worker.
   Shell: cache-first with background refresh; tracks.json network-first (short timeout) with cache fallback.
   Audio: cache keyed by the exact URL (including ?v= version), with HTTP Range support, else network. */
'use strict';

const SHELL_CACHE = 'alh-shell-v4';
const AUDIO_CACHE = 'alh-audio-v1'; // kept across shell versions
const SHELL_FILES = ['./', 'index.html', 'manifest.webmanifest', 'icon.svg', 'icon-180.png', 'icon-512.png', 'tracks.json'];

const scopeUrl = (p) => new URL(p, self.registration.scope).href;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    await cache.addAll(SHELL_FILES.map((p) => new Request(scopeUrl(p), { cache: 'reload' })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith('alh-shell-') && k !== SHELL_CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

// Exact cache key for audio: the version query stays, only the fragment goes.
function audioKey(url) {
  const u = new URL(url);
  u.hash = '';
  return u.href;
}

function stripSearch(url) {
  const u = new URL(url);
  u.search = '';
  u.hash = '';
  return u.href;
}

function isAudio(url) {
  return url.startsWith(scopeUrl('audio/'));
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = req.url;
  if (!url.startsWith(self.registration.scope)) return;

  if (isAudio(url)) {
    event.respondWith(audioResponse(req));
    return;
  }

  let key = stripSearch(url);
  // Other tours (madrid/) live in sub-folders of this scope: never answer
  // their pages with this tour's index.html; only the root page maps to it.
  const rel = key.slice(self.registration.scope.length);
  if (req.mode === 'navigate') {
    if (rel !== '' && rel !== 'index.html') return;
    key = scopeUrl('index.html');
  }
  const shellSet = new Set(SHELL_FILES.map(scopeUrl));
  if (!shellSet.has(key)) return; // not part of the shell: plain network

  if (key === scopeUrl('tracks.json')) {
    event.respondWith(tracksResponse(event, key));
    return;
  }
  event.respondWith(shellResponse(event, key));
});

const TRACKS_TIMEOUT_MS = 4000;

async function notifyTracksUpdated() {
  const clients = await self.clients.matchAll({ type: 'window' });
  clients.forEach((c) => c.postMessage({ type: 'tracks-updated' }));
}

// Network-first so an online phone sees new audio versions; falls back to the cache
// when offline, or after a short wait on a weak signal (then tells the page if it changed).
async function tracksResponse(event, key) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(key);
  const network = (async () => {
    const res = await fetch(key, { cache: 'no-cache' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    await cache.put(key, res.clone());
    return res;
  })();
  if (!cached) {
    try { return await network; } catch (e) {
      return new Response('Offline and not cached', { status: 503, headers: { 'Content-Type': 'text/plain' } });
    }
  }
  let timer;
  const timeout = new Promise((resolve) => { timer = setTimeout(() => resolve(null), TRACKS_TIMEOUT_MS); });
  const first = await Promise.race([network.then((r) => r, () => null), timeout]);
  clearTimeout(timer);
  if (first) return first;
  // Serve the cached copy now; if the network answers later with something new, say so.
  event.waitUntil((async () => {
    try {
      const [a, res] = await Promise.all([cached.clone().text(), network]);
      const b = await res.clone().text();
      if (a !== b) await notifyTracksUpdated();
    } catch (e) { /* still offline */ }
  })());
  return cached;
}

async function shellResponse(event, key) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(key);
  const refresh = (async () => {
    try {
      const res = await fetch(key, { cache: 'no-cache' });
      if (!res.ok) return null;
      await cache.put(key, res.clone());
      return res;
    } catch (e) {
      return null;
    }
  })();
  if (cached) {
    event.waitUntil(refresh);
    return cached;
  }
  const fresh = await refresh;
  return fresh || new Response('Offline and not cached', { status: 503, headers: { 'Content-Type': 'text/plain' } });
}

async function audioResponse(req) {
  const key = audioKey(req.url);
  const cache = await caches.open(AUDIO_CACHE);
  const cached = await cache.match(key);
  if (!cached) {
    try {
      return await fetch(req);
    } catch (e) {
      return new Response('Audio not downloaded and network unavailable', { status: 504, headers: { 'Content-Type': 'text/plain' } });
    }
  }

  const buf = await cached.arrayBuffer();
  const size = buf.byteLength;
  const type = cached.headers.get('Content-Type') || 'audio/mpeg';
  const range = req.headers.get('Range');

  if (!range) {
    return new Response(buf, {
      status: 200,
      headers: { 'Content-Type': type, 'Content-Length': String(size), 'Accept-Ranges': 'bytes' }
    });
  }

  const m = /^bytes=(\d*)-(\d*)$/.exec(range.trim());
  let start, end;
  if (m && (m[1] !== '' || m[2] !== '')) {
    if (m[1] === '') { // suffix: last N bytes
      const n = parseInt(m[2], 10);
      start = Math.max(0, size - n);
      end = size - 1;
    } else {
      start = parseInt(m[1], 10);
      end = m[2] === '' ? size - 1 : Math.min(parseInt(m[2], 10), size - 1);
    }
  }
  if (start === undefined || isNaN(start) || isNaN(end) || start >= size || start > end) {
    return new Response('', {
      status: 416,
      headers: { 'Content-Range': `bytes */${size}`, 'Accept-Ranges': 'bytes' }
    });
  }

  const body = buf.slice(start, end + 1);
  return new Response(body, {
    status: 206,
    statusText: 'Partial Content',
    headers: {
      'Content-Type': type,
      'Content-Length': String(body.byteLength),
      'Content-Range': `bytes ${start}-${end}/${size}`,
      'Accept-Ranges': 'bytes'
    }
  });
}
