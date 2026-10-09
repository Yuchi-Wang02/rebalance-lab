'use strict';

// The site explains the protocol, reads a saved ingestion diagnostic, and offers
// a fee-arithmetic illustration. It does not request prices or simulate returns.
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
    tag: 'Replication control',
    title: 'A broader lens, a slower rhythm.',
    description: 'Blend long, medium, and shorter momentum horizons while retaining semiannual rebalancing. This is the control for the second frequency comparison.',
    signal: '50% 12–1 + 30% 6–1 + 20% 3–1',
    schedule: 'March / September month-end → next open',
    compare: 'MMIX · change frequency only',
  },
  MMIX: {
    tag: 'Replication comparison',
    title: 'Does the finding travel?',
    description: 'Rebalance the blended signal monthly. Compare with SMIX to see whether the frequency effect also appears under a different, prespecified signal.',
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
  document.getElementById('research-status').textContent = passed
    ? 'Price pipeline tested; research data audit pending.'
    : 'Price diagnostic issues; research audit pending.';
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
