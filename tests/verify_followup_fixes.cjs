const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

// 1 & 2: Preview Bridge Fixes
const adapter = fs.readFileSync('backend/services/hyperframes_adapter.py', 'utf8');
const bridgeMatch = adapter.match(/<script id="vm-preview-bridge">([\s\S]*?)<\/script>/);
assert.ok(bridgeMatch, 'vm-preview-bridge script tag found');
const bridge = bridgeMatch[1]
  .replaceAll('{{', '{').replaceAll('}}', '}').replaceAll('{duration}', '20');

let listener, tick, report, time = 0;
const media = {
  dataset: { start: '0', duration: '20' },
  style: {},
  currentTime: 0,
  paused: true,
  play() { this.paused = false; return Promise.resolve(); },
  pause() { this.paused = true; }
};
const tl = {
  play() {},
  pause() {},
  seek(t) { time = t; },
  time() { return time; }
};

vm.runInNewContext(bridge, {
  window: {
    __timelines: { viralmint_stage: tl },
    addEventListener: (n, cb) => { listener = cb; },
    parent: { postMessage: r => { report = r; } }
  },
  document: { querySelectorAll: () => [media] },
  Date,
  setInterval: cb => { tick = cb; },
});

// Test 1: Short seek (0.1s from 0.0s) must update currentTime immediately
listener({ data: { source: 'vm-parent', action: 'seek', time: 0.1 } });
assert.equal(media.currentTime, 0.1, 'Short seek to 0.1 must update media.currentTime to 0.1');
console.log('PASS 1: paused seek to 0.1 correctly sets media.currentTime to 0.1.');

// Test 2: GSAP clock reaching composition end must pause playback and report paused=true
listener({ data: { source: 'vm-parent', action: 'play' } });
time = 20;
tick();
assert.equal(report.paused, true, 'Report must be paused when GSAP clock reaches end');
assert.equal(media.paused, true, 'Media must be paused when GSAP clock reaches end');
console.log('PASS 2: GSAP clock reaching composition end pauses playback and reports paused=true.');

// Test 3: Conflict discard with remote fetch failure
const source = fs.readFileSync('frontend/src/pages/MotionGraphics.jsx', 'utf8');
const handlers = source.slice(
  source.indexOf('  const handleSave ='),
  source.indexOf('  // 4. Render Project')
);
let doc = { title: 'unsaved local draft' }, rev = 1, dirty = true, conflict = null;
const ctx = {
  project: { id: 'test' },
  document: doc,
  revision: rev,
  conflictState: null,
  http: {
    post: async () => { throw { response: { status: 409 } }; },
    get: async () => { throw new Error('offline'); }
  },
  setIsSaving() {},
  setRevision: v => { rev = v; },
  setDocument: v => { doc = v; },
  setIsDirty: v => { dirty = v; },
  setConflictState: v => { conflict = v; ctx.conflictState = v; },
  showSnackbar() {}
};

vm.createContext(ctx);
vm.runInContext(handlers + '\nthis.save=handleSave;this.discard=handleResolveConflictDiscard;', ctx);

(async () => {
  await ctx.save();
  assert.equal(conflict, null, 'conflictState should remain null when remote fetch fails');
  await ctx.discard();
  assert.equal(doc.title, 'unsaved local draft', 'local draft must be preserved when fetch fails');
  assert.equal(dirty, true, 'dirty state must remain true when fetch fails');
  assert.equal(rev, 1, 'revision must remain 1 without unconfirmed guesses');
  console.log('PASS 3: failed remote fetch preserves local draft, keeps dirty=true, and leaves revision=1.');
})().catch(err => {
  console.error(err);
  process.exitCode = 1;
});
