const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '../../static/tasks/js/serviceworker.js'), 'utf8'
);

function loadWorker({ networkResponse = { kind: 'live' }, offline = false } = {}) {
  const listeners = {};
  const cacheReads = [];
  const cacheWrites = [];
  const networkRequests = [];
  const offlinePage = { kind: 'offline' };
  const cachedAsset = { kind: 'cached asset' };
  const caches = {
    open: async () => ({
      addAll: async urls => cacheWrites.push(...urls),
    }),
    keys: async () => [],
    match: async request => {
      const url = typeof request === 'string' ? request : request.url;
      cacheReads.push(url);
      return url === '/offline/' ? offlinePage : cachedAsset;
    },
    delete: async () => true,
  };
  const self = {
    location: { origin: 'https://hangarin.example' },
    clients: { claim: async () => {} },
    skipWaiting() {},
    addEventListener(name, callback) { listeners[name] = callback; },
  };
  const fetch = async request => {
    networkRequests.push(request.url);
    if (offline) throw new Error('network unavailable');
    return networkResponse;
  };

  vm.runInNewContext(source, { self, caches, fetch, URL, Promise });

  return {
    listeners,
    cacheReads,
    cacheWrites,
    networkRequests,
    async fetchRequest(request) {
      let response;
      listeners.fetch({ request, respondWith(result) { response = result; } });
      return response === undefined ? undefined : await response;
    },
  };
}

test('installation precaches only the offline page and presentation assets', async () => {
  const worker = loadWorker();
  let installation;
  worker.listeners.install({ waitUntil(promise) { installation = promise; } });
  await installation;

  assert.ok(worker.cacheWrites.includes('/offline/'));
  assert.ok(worker.cacheWrites.includes('/static/tasks/css/hangarin.css'));
  assert.ok(worker.cacheWrites.includes('/static/tasks/img/icon-512.png'));
  assert.ok(worker.cacheWrites.every(url => url === '/offline/' || url.startsWith('/static/tasks/')));
});

test('online task navigation uses the network and does not touch the cache', async () => {
  const worker = loadWorker();
  const response = await worker.fetchRequest({
    method: 'GET', mode: 'navigate', url: 'https://hangarin.example/tasks/'
  });

  assert.deepEqual(response, { kind: 'live' });
  assert.deepEqual(worker.networkRequests, ['https://hangarin.example/tasks/']);
  assert.deepEqual(worker.cacheReads, []);
  assert.deepEqual(worker.cacheWrites, []);
});

test('offline task navigation returns only the public offline page', async () => {
  const worker = loadWorker({ offline: true });
  const response = await worker.fetchRequest({
    method: 'GET', mode: 'navigate', url: 'https://hangarin.example/tasks/1/'
  });

  assert.deepEqual(response, { kind: 'offline' });
  assert.deepEqual(worker.cacheReads, ['/offline/']);
  assert.deepEqual(worker.cacheWrites, []);
});

test('task mutations bypass the worker', async () => {
  const worker = loadWorker();
  const response = await worker.fetchRequest({
    method: 'POST', mode: 'navigate', url: 'https://hangarin.example/tasks/add/'
  });

  assert.equal(response, undefined);
  assert.deepEqual(worker.networkRequests, []);
  assert.deepEqual(worker.cacheReads, []);
});
