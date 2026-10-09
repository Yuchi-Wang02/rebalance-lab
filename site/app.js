'use strict';

// The site explains the protocol, reads saved diagnostic/engineering receipts,
// and illustrates fee arithmetic. It does not request prices or simulate returns.
const arms = {
  S12: {
    tag: 'Primary control',
    title: 'The baseline tempo.',
    description: 'Rebalance twice a year using 12–1 risk-adjusted momentum. Comparing M12 with this arm isolates the scheduled rebalance frequency within the same model.',
    signal: '12–1 risk-adjusted momentum',
    schedule: 'March / September month-end → next open',
    compare: 'M12 · change frequency only',
  },
  M12: {
    tag: 'Primary comparison',
    title: 'Faster rhythm, same signal.',
    description: 'Rebalance monthly using the same 12–1 momentum signal as S12. This is the cleanest test of whether frequency earns its additional costs.',
    signal: '12–1 risk-adjusted momentum',
    schedule: 'Every month-end → next open',
    compare: 'S12 · change frequency only',
  },
  SMIX: {
    tag: 'Within-study robustness control',
    title: 'A broader lens, a slower rhythm.',
    description: 'Blend long, medium, and shorter momentum horizons while retaining semiannual rebalancing. This is the control for a within-study robustness check, not independent replication.',
    signal: '50% 12–1 + 30% 6–1 + 20% 3–1',
    schedule: 'March / September month-end → next open',
    compare: 'MMIX · change frequency only',
  },
  MMIX: {
    tag: 'Within-study robustness comparison',
    title: 'The same question, a blended signal.',
    description: 'Rebalance the blended signal monthly. Compare with SMIX to see whether the frequency effect also appears under a different, prespecified signal. Both comparisons use the same market history.',
    signal: '50% 12–1 + 30% 6–1 + 20% 3–1',
    schedule: 'Every month-end → next open',
    compare: 'SMIX · change frequency only',
  },
};

document.querySelectorAll('[data-arm]').forEach((button) => {
  button.addEventListener('click', () => {
    const arm = arms[button.dataset.arm];
    if (!arm) return;
    document.querySelectorAll('[data-arm]').forEach((candidate) => {
      const selected = candidate === button;
      candidate.classList.toggle('selected', selected);
      candidate.setAttribute('aria-pressed', String(selected));
    });
    document.getElementById('detail-code').textContent = button.dataset.arm;
    for (const [key, value] of Object.entries(arm)) {
      document.getElementById(`detail-${key}`).textContent = value;
    }
  });
});

const costInput = document.getElementById('cost-bps');
const tradedInput = document.getElementById('traded-multiple');
const compactNumber = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const dollars = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

function updateCosts() {
  const costBps = Number(costInput.value);
  const tradedMultiple = Number(tradedInput.value);
  const feeBps = costBps * tradedMultiple;
  const feePercent = feeBps / 100;
  document.getElementById('bps-output').textContent = `${costBps} bps`;
  document.getElementById('multiple-output').textContent = `${compactNumber.format(tradedMultiple)}× reference NAV`;
  document.getElementById('fee-percent').textContent = feePercent.toFixed(2);
  document.getElementById('fee-dollar').textContent = dollars.format(1_000_000 * feeBps / 10_000);
  document.getElementById('fee-formula').textContent = `${costBps} bps × ${compactNumber.format(tradedMultiple)} = ${compactNumber.format(feeBps)} bps = ${feePercent.toFixed(2)}%`;
  costInput.setAttribute('aria-valuetext', `${costBps} basis points per side`);
  tradedInput.setAttribute('aria-valuetext', `${tradedMultiple} times fixed reference net asset value`);
  [costInput, tradedInput].forEach((input) => {
    const fraction = (Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min));
    input.style.setProperty('--fill', `${fraction * 100}%`);
  });
}

costInput.addEventListener('input', updateCosts);
tradedInput.addEventListener('input', updateCosts);
updateCosts();

const menuToggle = document.querySelector('.menu-toggle');
const navigation = document.getElementById('primary-nav');
function closeMenu() {
  menuToggle.setAttribute('aria-expanded', 'false');
  navigation.classList.remove('open');
}
menuToggle.addEventListener('click', () => {
  const open = menuToggle.getAttribute('aria-expanded') !== 'true';
  menuToggle.setAttribute('aria-expanded', String(open));
  navigation.classList.toggle('open', open);
});
navigation.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
    closeMenu();
    menuToggle.focus();
  }
});

// Keep deep links usable when the requested evidence lives in a closed section.
function revealHashTarget() {
  const target = document.getElementById(window.location.hash.slice(1));
  if (!target) return;
  let parent = target;
  let opened = false;
  while (parent) {
    if (parent.tagName === 'DETAILS' && !parent.open) {
      parent.open = true;
      opened = true;
    }
    parent = parent.parentElement;
  }
  if (opened) requestAnimationFrame(() => target.scrollIntoView({ block: 'start' }));
}
window.addEventListener('hashchange', revealHashTarget);
revealHashTarget();

function validateDiagnosticSummary(summary) {
  const countFields = ['rows', 'complete_ohlc_rows', 'missing_ohlc_rows', 'invalid_ohlc_rows', 'error_count', 'warning_count'];
  const isoDate = /^\d{4}-\d{2}-\d{2}$/;
  if (!summary || summary.schema_version !== 1 || summary.research_ready !== false
      || typeof summary.diagnostic_passed !== 'boolean'
      || typeof summary.cache_replay_verified !== 'boolean'
      || summary.calendar_coverage !== 'not_verified'
      || summary.price_adjustment_semantics !== 'not_verified'
      || !isoDate.test(summary.requested_start) || !isoDate.test(summary.requested_end)
      || typeof summary.generated_at_utc !== 'string' || !Number.isFinite(Date.parse(summary.generated_at_utc))
      || !Array.isArray(summary.symbols) || summary.symbols.length === 0 || summary.symbols.length > 2) {
    throw new Error('Unsupported diagnostic summary');
  }
  const symbolNames = new Set();
  for (const entry of summary.symbols) {
    if (!entry || !['SPMO', 'SPY'].includes(entry.symbol) || symbolNames.has(entry.symbol)
        || !countFields.every((field) => Number.isSafeInteger(entry[field]) && entry[field] >= 0)
        || entry.complete_ohlc_rows + entry.missing_ohlc_rows + entry.invalid_ohlc_rows !== entry.rows
        || (entry.observed_start !== null && !isoDate.test(entry.observed_start))
        || (entry.observed_end !== null && !isoDate.test(entry.observed_end))
        || (entry.rows > 0 && (!entry.observed_start || !entry.observed_end))) {
      throw new Error('Invalid symbol diagnostic');
    }
    symbolNames.add(entry.symbol);
  }
  return summary;
}

function renderDiagnosticSummary(summary) {
  const body = document.getElementById('diagnostic-symbols');
  const rows = document.createDocumentFragment();
  for (const entry of summary.symbols) {
    const row = document.createElement('tr');
    const symbol = document.createElement('th');
    symbol.scope = 'row';
    symbol.textContent = entry.symbol;
    row.append(symbol);
    const observed = entry.observed_start && entry.observed_end
      ? `${entry.observed_start} to ${entry.observed_end}` : 'No records observed';
    const issueDetails = [];
    if (entry.error_count || entry.warning_count) {
      issueDetails.push(`${entry.error_count} error${entry.error_count === 1 ? '' : 's'} · ${entry.warning_count} warning${entry.warning_count === 1 ? '' : 's'}`);
    }
    if (entry.missing_ohlc_rows > 0) {
      issueDetails.push(`${entry.missing_ohlc_rows} bar${entry.missing_ohlc_rows === 1 ? '' : 's'} missing OHLC values`);
    }
    if (entry.invalid_ohlc_rows > 0) {
      issueDetails.push(`${entry.invalid_ohlc_rows} bar${entry.invalid_ohlc_rows === 1 ? '' : 's'} with invalid OHLC values`);
    }
    const issues = issueDetails.length ? issueDetails.join('; ')
      : entry.rows === 0 ? 'No records to assess' : 'None reported';
    for (const value of [observed, `${entry.complete_ohlc_rows.toLocaleString('en-US')} / ${entry.rows.toLocaleString('en-US')}`, issues]) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.append(cell);
    }
    rows.append(row);
  }
  body.replaceChildren(rows);
  const passed = summary.diagnostic_passed
    && summary.symbols.every((entry) => entry.rows > 0 && entry.error_count === 0
      && entry.missing_ohlc_rows === 0 && entry.invalid_ohlc_rows === 0);
  const badge = document.getElementById('diagnostic-badge');
  badge.textContent = passed ? 'Ingestion checks passed' : 'Diagnostic issues recorded';
  badge.classList.toggle('needs-review', !passed);
  document.getElementById('diagnostic-state').textContent = passed
    ? 'Price ingestion checks passed. The research data audit remains pending.'
    : 'The diagnostic has unresolved issues. Inspect the saved summary and pipeline notes before using these inputs.';
  const generated = new Date(summary.generated_at_utc).toISOString().replace('T', ' ').replace('.000Z', ' UTC');
  document.getElementById('diagnostic-meta').textContent = `Requested: ${summary.requested_start} to ${summary.requested_end}. Summary generated: ${generated}. Cache replay: ${summary.cache_replay_verified ? 'verified' : 'not verified'}.`;
  document.getElementById('diagnostic-results').hidden = false;
}

async function loadDiagnosticSummary() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('data/ingestion-summary.json', { signal: controller.signal });
    if (!response.ok) throw new Error('Diagnostic summary unavailable');
    renderDiagnosticSummary(validateDiagnosticSummary(await response.json()));
  } catch {
    document.getElementById('diagnostic-badge').textContent = 'Summary unavailable';
    document.getElementById('diagnostic-state').textContent = 'The saved diagnostic summary could not be loaded or validated. Read the pipeline notes for status; no data-readiness claim is inferred.';
  } finally {
    clearTimeout(timeout);
  }
}

loadDiagnosticSummary();

function validateEngineSummary(summary) {
  const expectedStrategies = ['S12', 'M12', 'SMIX', 'MMIX'];
  const expectedCosts = [0, 5, 10, 25];
  const matchesSet = (values, expected) => Array.isArray(values)
    && values.length === expected.length && new Set(values).size === expected.length
    && values.every((value) => expected.includes(value));
  const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  if (!summary || summary.schema_version !== 1 || summary.engine_status !== 'synthetic_prototype'
      || summary.data_track !== 'synthetic' || summary.formal_engine_accepted !== false
      || summary.market_backtest_executed !== false || summary.research_ready !== false
      || !matchesSet(summary.strategy_ids, expectedStrategies) || !matchesSet(summary.cost_bps, expectedCosts)
      || !Number.isSafeInteger(summary.run_count)
      || summary.run_count !== expectedStrategies.length * expectedCosts.length
      || !isRecord(summary.checks) || Object.keys(summary.checks).length === 0
      || Object.keys(summary.checks).length > 40
      || !Object.entries(summary.checks).every(([name, value]) => name.length > 0 && name.length <= 120 && typeof value === 'boolean')
      || typeof summary.generated_at_utc !== 'string' || !Number.isFinite(Date.parse(summary.generated_at_utc))
      || !Array.isArray(summary.limitations) || summary.limitations.length > 20
      || !summary.limitations.every((value) => typeof value === 'string' && value.trim().length > 0 && value.length <= 2000)) {
    throw new Error('Unsupported synthetic engine receipt');
  }
  return summary;
}

function renderEngineSummary(summary) {
  const checks = Object.entries(summary.checks);
  const passedCount = checks.filter(([, passed]) => passed).length;
  document.getElementById('engine-run-count').textContent = String(summary.run_count);
  document.getElementById('engine-check-count').textContent = `${passedCount} / ${checks.length}`;
  document.getElementById('engine-combinations').textContent = `${summary.strategy_ids.join(' · ')}. Each tested at ${summary.cost_bps.join(' / ')} bps per side, on synthetic data.`;
  const checkList = document.createDocumentFragment();
  for (const [name, passed] of checks) {
    const item = document.createElement('li');
    const label = document.createElement('span');
    const humanName = name.replace(/[_-]+/g, ' ');
    label.textContent = humanName.charAt(0).toUpperCase() + humanName.slice(1);
    const result = document.createElement('strong');
    result.textContent = passed ? 'Passed' : 'Needs review';
    result.className = passed ? 'check-passed' : 'check-unresolved';
    item.append(label, result);
    checkList.append(item);
  }
  document.getElementById('engine-checks').replaceChildren(checkList);
  const limitations = document.createDocumentFragment();
  for (const limitation of summary.limitations) {
    const item = document.createElement('li');
    item.textContent = limitation;
    limitations.append(item);
  }
  if (summary.limitations.length === 0) {
    const item = document.createElement('li');
    item.textContent = 'No additional limitations listed in this receipt. Market validation and formal acceptance remain pending.';
    limitations.append(item);
  }
  document.getElementById('engine-limitations').replaceChildren(limitations);
  document.getElementById('engine-state').textContent = passedCount === checks.length
    ? 'The recorded synthetic checks passed. They establish only the specific software behavior tested.'
    : 'Some recorded synthetic checks need review. This receipt does not establish engine acceptance.';
  const generated = new Date(summary.generated_at_utc).toISOString().replace('T', ' ').replace(/Z$/, ' UTC');
  document.getElementById('engine-meta').textContent = `Receipt generated: ${generated}. See the saved JSON for the code, fixture, and configuration hashes.`;
  document.getElementById('engine-results').hidden = false;
}

async function loadEngineSummary() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('data/engine-status.json', { signal: controller.signal });
    if (!response.ok) throw new Error('Engine receipt unavailable');
    renderEngineSummary(validateEngineSummary(await response.json()));
  } catch {
    document.getElementById('engine-state').textContent = 'The saved engine receipt could not be loaded or validated. No check results are inferred; read the engine guide for implementation details.';
  } finally {
    clearTimeout(timeout);
  }
}

loadEngineSummary();
