import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../site/pilot.js', import.meta.url), 'utf8');
const published = JSON.parse(readFileSync(new URL('../site/data/etf-pilot-summary.json', import.meta.url), 'utf8'));

// Minimal DOM boundary: exercise the production script and its real event handlers.
class Element {
  constructor(tag = '') {
    this.tagName = tag;
    this.textContent = '';
    this.value = '';
    this.disabled = false;
    this.children = [];
    this.listeners = new Map();
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) {
    this.children = nodes.flatMap((node) => node.tagName === '#fragment' ? node.children : [node]);
  }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  change(value) {
    this.value = String(value);
    for (const listener of this.listeners.get('change') || []) listener();
  }
}

function start({ mutate = () => {}, fetchResponse } = {}) {
  const summary = structuredClone(published);
  mutate(summary);
  const nodes = new Map(['phase-rows', 'pilot-data-status', 'phase-caption', 'pilot-signal', 'pilot-cost']
    .map((id) => [id, new Element()]));
  nodes.get('pilot-signal').value = '12-1';
  nodes.get('pilot-cost').value = '5';
  const timers = new Map();
  let timerId = 0;
  const completion = vm.runInNewContext(source, {
    document: {
      getElementById: (id) => nodes.get(id),
      createElement: (tag) => new Element(tag),
      createDocumentFragment: () => new Element('#fragment'),
    },
    fetch: fetchResponse || (async () => ({ ok: true, json: async () => summary })),
    AbortController,
    setTimeout(callback, delay) { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout(id) { timers.delete(id); },
  });
  return { nodes, timers, completion };
}

function assertUnavailable(nodes) {
  assert.equal(nodes.get('pilot-signal').disabled, true);
  assert.equal(nodes.get('pilot-cost').disabled, true);
  assert.equal(nodes.get('phase-caption').textContent, 'Saved comparison table unavailable');
  assert.match(nodes.get('pilot-data-status').textContent, /could not be loaded or verified/);
  const rows = nodes.get('phase-rows').children;
  assert.equal(rows.length, 1);
  assert.equal(rows[0].children.length, 1);
  assert.equal(rows[0].children[0].colSpan, 5);
  assert.equal(rows[0].children[0].textContent, 'Saved comparisons unavailable.');
}

test('the actual published file renders all eight scenarios with canonical phases and exact rounded values', async () => {
  const { nodes, timers, completion } = start();
  assert.equal(nodes.get('pilot-signal').disabled, true);
  assert.equal(nodes.get('pilot-cost').disabled, true);
  await completion;
  assert.equal(timers.size, 0);
  for (const signal of ['12-1', 'mixed']) for (const cost of [0, 5, 10, 25]) {
    nodes.get('pilot-signal').change(signal);
    nodes.get('pilot-cost').change(cost);
    assert.equal(nodes.get('pilot-signal').disabled, false);
    assert.equal(nodes.get('pilot-cost').disabled, false);
    const rows = nodes.get('phase-rows').children;
    assert.equal(rows.length, 6);
    for (let index = 0; index < 6; index++) {
      const expected = published.comparisons.full_period.find((row) =>
        row.signal === signal && row.cost_bps_per_side === cost && row.phase[0] === index + 1);
      assert.equal(rows[index].children[0].tagName, 'th');
      assert.equal(rows[index].children[0].scope, 'row');
      assert.equal(rows[index].children[1].textContent, `${(100 * expected.monthly_cagr).toFixed(2)}%`);
      assert.equal(rows[index].children[2].textContent, `${(100 * expected.semiannual_cagr).toFixed(2)}%`);
      assert.equal(rows[index].children[3].textContent,
        `${expected.cagr_difference_pp >= 0 ? '+' : ''}${expected.cagr_difference_pp.toFixed(2)} pp`);
      assert.equal(rows[index].children[4].textContent,
        `${expected.max_drawdown_difference_pp >= 0 ? '+' : ''}${expected.max_drawdown_difference_pp.toFixed(2)} pp`);
    }
    assert.equal(rows[2].children[0].textContent, 'Mar / Sep · primary');
    assert.match(nodes.get('phase-caption').textContent, new RegExp(`${cost} bps per side$`));
  }
});

const malformedCases = {
  'malformed nondefault scenario': (data) => {
    data.comparisons.full_period.find((row) => row.signal === 'mixed' && row.cost_bps_per_side === 25).cagr_difference_pp = null;
  },
  'duplicate phase hiding a missing phase': (data) => {
    const rows = data.comparisons.full_period.filter((row) => row.signal === 'mixed' && row.cost_bps_per_side === 25);
    Object.assign(rows[1], structuredClone(rows[0]));
  },
  'invalid phase pair': (data) => { data.comparisons.full_period[0].phase = [1, 8]; },
  'CAGR spread inconsistent with its two returns': (data) => { data.comparisons.full_period[0].cagr_difference_pp = 999; },
  'drawdown spread inconsistent with its two drawdowns': (data) => { data.comparisons.full_period[0].max_drawdown_difference_pp = 999; },
  'mismatched run identity': (data) => { data.comparisons.full_period[0].semiannual_run_id = 'S12-03-09-5bps'; },
  'different monthly comparator across phases': (data) => {
    const row = data.comparisons.full_period[1];
    row.monthly_cagr += 0.01;
    row.cagr_difference_pp = 100 * (row.monthly_cagr - row.semiannual_cagr);
  },
  'wrong experiment scope': (data) => { data.original_stock_experiment_completed = true; },
  'wrong reporting interval': (data) => { data.boundaries.full_year_end_on_or_before = '2026-10-02'; },
};

for (const [name, mutate] of Object.entries(malformedCases)) {
  test(`rejects ${name} before enabling any control`, async () => {
    const { nodes, timers, completion } = start({ mutate });
    await completion;
    assertUnavailable(nodes);
    assert.equal(timers.size, 0);
  });
}

test('an invalid change after a successful render clears all stale result rows', async () => {
  const { nodes, completion } = start();
  await completion;
  assert.equal(nodes.get('phase-rows').children.length, 6);
  assert.doesNotThrow(() => nodes.get('pilot-cost').change(99));
  assertUnavailable(nodes);
});

test('a failed request presents an unavailable table and keeps controls disabled', async () => {
  const { nodes, timers, completion } = start({ fetchResponse: async () => ({ ok: false }) });
  await completion;
  assertUnavailable(nodes);
  assert.equal(timers.size, 0);
});

test('a stalled request is aborted after the ten-second limit without leaving a loading state', async () => {
  let requestSignal;
  const { nodes, timers, completion } = start({ fetchResponse: async (_path, { signal }) => {
    requestSignal = signal;
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('Aborted'))));
  } });
  const [{ callback, delay }] = [...timers.values()];
  assert.equal(delay, 10000);
  assert.equal(nodes.get('pilot-cost').disabled, true);
  callback();
  await completion;
  assert.equal(requestSignal.aborted, true);
  assertUnavailable(nodes);
  assert.equal(timers.size, 0);
});
