'use strict';

// Read saved comparisons only. Controls become available after the whole matrix checks out.
(async () => {
  const SIGNALS = ['12-1', 'mixed'];
  const COSTS = [0, 5, 10, 25];
  const body = document.getElementById('phase-rows');
  const state = document.getElementById('pilot-data-status');
  const caption = document.getElementById('phase-caption');
  const signalControl = document.getElementById('pilot-signal');
  const costControl = document.getElementById('pilot-cost');
  const finite = (value) => typeof value === 'number' && Number.isFinite(value);
  const close = (left, right) => Math.abs(left - right) < 1e-8;
  const assert = (condition) => {
    if (!condition) throw new Error('Saved comparisons do not match this study.');
  };
  const key = (signal, cost) => `${signal}|${cost}`;
  let scenarios;

  signalControl.disabled = true;
  costControl.disabled = true;

  function unavailable() {
    signalControl.disabled = true;
    costControl.disabled = true;
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.textContent = 'Saved comparisons unavailable.';
    row.append(cell);
    body.replaceChildren(row);
    caption.textContent = 'Saved comparison table unavailable';
    state.textContent = 'The saved comparison table could not be loaded or verified. Use the downloadable CSV and static figures; no missing values are inferred.';
  }

  function validate(data) {
    assert(data?.experiment_id === 'sector-etf-frequency-v1' &&
      data.data_track === 'real_market_adjusted_price_pilot' &&
      data.market_pilot_executed === true && data.original_stock_experiment_completed === false);
    assert(data.boundaries?.report_anchor_on_or_before === '2000-12-29' &&
      data.boundaries?.full_year_end_on_or_before === '2025-12-31');
    const comparisons = data.comparisons?.full_period;
    assert(Array.isArray(comparisons) && comparisons.length === 48);
    const matrix = new Map();
    for (const row of comparisons) {
      assert(row && SIGNALS.includes(row.signal) && COSTS.includes(row.cost_bps_per_side));
      assert(Array.isArray(row.phase) && row.phase.length === 2 &&
        Number.isInteger(row.phase[0]) && row.phase[0] >= 1 && row.phase[0] <= 6 &&
        row.phase[1] === row.phase[0] + 6);
      const phase = row.phase.map((month) => String(month).padStart(2, '0')).join('-');
      const monthlyId = row.signal === '12-1' ? 'M12' : 'MMIX';
      const semiannualId = row.signal === '12-1' ? 'S12' : 'SMIX';
      assert(row.monthly_run_id === `${monthlyId}-${row.cost_bps_per_side}bps` &&
        row.semiannual_run_id === `${semiannualId}-${phase}-${row.cost_bps_per_side}bps`);
      assert(['monthly_cagr', 'semiannual_cagr', 'cagr_difference_pp',
        'monthly_max_drawdown', 'semiannual_max_drawdown', 'max_drawdown_difference_pp']
        .every((field) => finite(row[field])));
      assert(row.monthly_cagr > -1 && row.semiannual_cagr > -1 &&
        row.monthly_max_drawdown > -1 && row.monthly_max_drawdown <= 0 &&
        row.semiannual_max_drawdown > -1 && row.semiannual_max_drawdown <= 0);
      assert(close(row.cagr_difference_pp, 100 * (row.monthly_cagr - row.semiannual_cagr)) &&
        close(row.max_drawdown_difference_pp, 100 * (row.monthly_max_drawdown - row.semiannual_max_drawdown)));
      const scenario = key(row.signal, row.cost_bps_per_side);
      if (!matrix.has(scenario)) matrix.set(scenario, new Map());
      const phases = matrix.get(scenario);
      assert(!phases.has(row.phase[0]));
      if (phases.size) {
        const first = phases.values().next().value;
        assert(close(first.monthly_cagr, row.monthly_cagr) &&
          close(first.monthly_max_drawdown, row.monthly_max_drawdown));
      }
      phases.set(row.phase[0], row);
    }
    for (const signal of SIGNALS) for (const cost of COSTS) {
      assert(matrix.get(key(signal, cost))?.size === 6);
    }
    return matrix;
  }

  function render() {
    const signal = signalControl.value;
    const cost = Number(costControl.value);
    assert(SIGNALS.includes(signal) && COSTS.includes(cost));
    const rows = scenarios.get(key(signal, cost));
    assert(rows?.size === 6);
    const fragment = document.createDocumentFragment();
    for (const month of [1, 2, 3, 4, 5, 6]) {
      const row = rows.get(month);
      const tr = document.createElement('tr');
      const primary = month === 3;
      if (primary) tr.className = 'phase-primary';
      const phase = row.phase.map((value) => new Intl.DateTimeFormat('en', { month: 'short', timeZone: 'UTC' })
        .format(new Date(Date.UTC(2000, value - 1, 1)))).join(' / ') + (primary ? ' · primary' : '');
      for (const value of [phase, `${(100 * row.monthly_cagr).toFixed(2)}%`,
        `${(100 * row.semiannual_cagr).toFixed(2)}%`,
        `${row.cagr_difference_pp >= 0 ? '+' : ''}${row.cagr_difference_pp.toFixed(2)} pp`,
        `${row.max_drawdown_difference_pp >= 0 ? '+' : ''}${row.max_drawdown_difference_pp.toFixed(2)} pp`]) {
        const cell = document.createElement(value === phase ? 'th' : 'td');
        if (value === phase) cell.scope = 'row';
        cell.textContent = value;
        tr.append(cell);
      }
      fragment.append(tr);
    }
    body.replaceChildren(fragment);
    caption.textContent = `Six semiannual phases · ${signal === '12-1' ? '12–1 signal' : 'blended signal'} · ${cost} bps per side`;
    state.textContent = 'All 48 saved comparisons checked. Positive CAGR difference favors monthly selection. Positive drawdown difference means the monthly drawdown is less negative.';
  }

  function update() {
    try { render(); } catch { unavailable(); }
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('data/etf-pilot-summary.json', { signal: controller.signal });
    if (!response.ok) throw new Error('Summary unavailable.');
    scenarios = validate(await response.json());
    render();
    signalControl.addEventListener('change', update);
    costControl.addEventListener('change', update);
    signalControl.disabled = false;
    costControl.disabled = false;
  } catch {
    unavailable();
  } finally {
    clearTimeout(timer);
  }
})();
