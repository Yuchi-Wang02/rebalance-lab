'use strict';

// Read saved, derived pilot outputs only. No quotes, credentials, or backtest run here.
(() => {
  const IDS = ['M12', 'S12', 'MMIX', 'SMIX', 'SPMO', 'SPY'];
  const COSTS = [0, 5, 10, 25];
  const WINDOWS = {
    year2025: { label: '2025 formation year', start: '2024-12-31', end: '2025-12-31' },
    ytd2026: { label: '2026 YTD through October 2', start: '2025-12-31', end: '2026-10-02' },
    full_period: { label: 'Full period: 2025–2026', start: '2024-12-31', end: '2026-10-02' },
  };
  const STYLE = {
    M12: { color: '#285f51', dash: '', width: 2.7, label: 'Monthly · 12–1' },
    S12: { color: '#bd773a', dash: '', width: 2.4, label: 'Semiannual · 12–1' },
    MMIX: { color: '#456f9b', dash: '8 4', width: 2, label: 'Monthly · blended' },
    SMIX: { color: '#94657e', dash: '8 4', width: 2, label: 'Semiannual · blended' },
    SPMO: { color: '#4f606c', dash: '2 5', width: 1.8, label: 'ETF context' },
    SPY: { color: '#777e73', dash: '5 5', width: 1.8, label: 'ETF context' },
  };
  const CHECK_NAMES = {
    all_16_strategy_cost_paths: 'All 16 strategy and cost paths present',
    fixed_cohort_for_all_paths: 'Same baseline cohort across paths',
    no_negative_cash: 'No negative cash',
    positive_finite_nav: 'Positive, finite portfolio values',
    next_session_execution: 'Orders execute in the next session',
    self_financing_fees: 'Fees reconcile with portfolio value',
    fees_match_executed_notional: 'Fees match executed notional',
    anchor_is_existing_portfolio: 'Existing holdings cross the YTD anchor',
  };
  const $ = (id) => document.getElementById(id);
  const costSelect = $('stock-cost');
  const periodSelect = $('stock-period');
  const number = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const dayFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  const shortDate = new Intl.DateTimeFormat('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' });
  let saved;

  function assert(condition, message) { if (!condition) throw new Error(message); }
  function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
  function key(id, cost) { return `${id}|${cost}`; }
  function dateValue(value) {
    assert(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value), 'Invalid session date');
    const result = new Date(`${value}T00:00:00Z`);
    assert(Number.isFinite(result.getTime()) && result.toISOString().slice(0, 10) === value, 'Invalid session date');
    return result;
  }
  function pct(value) { return `${number.format(100 * value)}%`; }
  function pp(value) {
    const rounded = Math.abs(value) < 0.005 ? 0 : value;
    return `${rounded > 0 ? '+' : ''}${number.format(rounded)} pp`;
  }
  function friendly(value) { return value.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase()); }

  function validate(summary, nav) {
    assert(summary && typeof summary === 'object' && !Array.isArray(summary), 'Missing summary');
    const metadata = { ...summary, ...(summary.metadata || {}) };
    assert(summary.formal_protocol_compliant === false && summary.data_track === 'baseline_issuer_stock_pilot', 'Unexpected experiment scope');
    assert(metadata.cohort_size === 100 && metadata.selected_count === 20, 'Unexpected cohort or position count');
    assert((metadata.date_start || summary.initial_signal) === WINDOWS.full_period.start, 'Unexpected formation date');
    assert((metadata.report_anchor || summary.report_anchor) === WINDOWS.ytd2026.start, 'Unexpected YTD anchor');
    assert((metadata.end || summary.report_end) === WINDOWS.full_period.end, 'Unexpected reporting end');
    assert(Array.isArray(summary.runs) && summary.runs.length === 16, 'Expected all 16 stock runs');
    assert(Array.isArray(summary.benchmarks) && summary.benchmarks.length === 8, 'Expected both ETF benchmarks at every cost');
    assert(summary.checks && Object.keys(summary.checks).length > 0 && Object.values(summary.checks).every((value) => value === true), 'Saved engine checks are incomplete');
    assert(Array.isArray(nav?.series), 'Missing portfolio paths');
    const metrics = new Map();
    const paths = new Map();
    const runIds = new Set();
    for (const run of [...summary.runs, ...summary.benchmarks]) {
      assert(IDS.includes(run.strategy_id) && COSTS.includes(run.cost_bps_per_side), 'Unexpected run identity');
      const id = key(run.strategy_id, run.cost_bps_per_side);
      assert(typeof run.run_id === 'string' && run.run_id.length > 0 && !runIds.has(run.run_id) && !metrics.has(id), 'Duplicate run identity');
      runIds.add(run.run_id);
      for (const [period, window] of Object.entries(WINDOWS)) {
        const item = run.metrics?.[period];
        assert(item && item.start_session === window.start && item.end_session === window.end, 'Inconsistent metric window');
        assert(['total_return', 'max_drawdown', 'two_sided_turnover', 'mean_cash_weight'].every((field) => finite(item[field])), 'Missing numeric metric');
        assert(item.total_return > -1 && item.max_drawdown <= 0 && item.max_drawdown > -1 && item.two_sided_turnover >= 0 && item.mean_cash_weight >= -1e-10 && item.mean_cash_weight <= 1 + 1e-10, 'Invalid metric range');
      }
      metrics.set(id, run);
    }
    for (const series of nav.series) {
      const id = key(series.strategy_id, series.cost_bps_per_side);
      const run = metrics.get(id);
      assert(run && run.run_id === series.run_id && !paths.has(id), 'Portfolio path does not match its summary');
      assert(Array.isArray(series.points) && series.points.length > 1, 'Empty portfolio path');
      let previous = '';
      for (const point of series.points) {
        dateValue(point.date);
        assert(point.date > previous && finite(point.value) && point.value > 0, 'Invalid or duplicate portfolio observation');
        previous = point.date;
      }
      assert(series.points[0].date === WINDOWS.full_period.start && previous === WINDOWS.full_period.end, 'Missing formation or final portfolio observation');
      paths.set(id, series.points);
    }
    assert(metrics.size === 24 && paths.size === 24, 'Missing a strategy or cost scenario');
    for (const cost of COSTS) {
      let commonDates;
      for (const id of IDS) {
        const points = paths.get(key(id, cost));
        assert(points, 'Incomplete portfolio matrix');
        const dates = points.map((point) => point.date).join(',');
        if (commonDates === undefined) commonDates = dates;
        assert(dates === commonDates, 'Portfolio dates are not aligned');
        for (const [period, window] of Object.entries(WINDOWS)) {
          const selected = points.filter((point) => point.date >= window.start && point.date <= window.end);
          assert(selected.length > 1 && selected[0].date === window.start && selected[selected.length - 1].date === window.end, 'Missing exact window endpoints');
          const expected = metrics.get(key(id, cost)).metrics[period];
          let high = selected[0].value;
          let drawdown = 0;
          for (const point of selected) {
            high = Math.max(high, point.value);
            drawdown = Math.min(drawdown, point.value / high - 1);
          }
          const realizedReturn = selected[selected.length - 1].value / selected[0].value - 1;
          assert(Math.abs(realizedReturn - expected.total_return) < 0.00001 && Math.abs(drawdown - expected.max_drawdown) < 0.00001, 'Saved path and summary do not reconcile');
        }
      }
    }
    return { summary, metadata, metrics, paths };
  }

  function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = content;
    if (className) node.className = className;
    return node;
  }
  function svgElement(tag, attributes = {}, content) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function renderChart(cost, period) {
    const window = WINDOWS[period];
    const chart = $('stock-chart');
    const container = chart.parentElement;
    const padding = parseFloat(getComputedStyle(container).paddingLeft) * 2;
    const width = Math.max(300, Math.min(1100, container.clientWidth - padding));
    const compact = width < 600;
    const height = compact ? 320 : 420, left = compact ? 48 : 62, right = compact ? 12 : 24, top = 24, bottom = 53;
    chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const series = IDS.map((id) => {
      const selected = saved.paths.get(key(id, cost)).filter((point) => point.date >= window.start && point.date <= window.end);
      return { id, points: selected.map((point) => ({ date: point.date, value: 100 * point.value / selected[0].value })) };
    });
    let low = 100, high = 100;
    for (const line of series) for (const point of line.points) { low = Math.min(low, point.value); high = Math.max(high, point.value); }
    const pad = Math.max((high - low) * 0.08, 1);
    low -= pad; high += pad;
    const startTime = dateValue(window.start).getTime(), endTime = dateValue(window.end).getTime();
    const x = (date) => left + (dateValue(date).getTime() - startTime) / (endTime - startTime) * plotWidth;
    const y = (value) => top + (high - value) / (high - low) * plotHeight;
    const fragment = document.createDocumentFragment();
    fragment.append(svgElement('title', { id: 'stock-svg-title' }, `Six normalized portfolio paths: ${window.label}, ${cost} bps per side`));
    fragment.append(svgElement('desc', { id: 'stock-svg-desc' }, 'Each saved portfolio is rebased to 100 at the first closing observation of this window. All six series use the same dates and a common linear axis. Endpoint returns, drawdowns, and turnover are listed in the following table.'));
    for (let index = 0; index <= 4; index += 1) {
      const value = low + (high - low) * index / 4;
      const position = y(value);
      fragment.append(svgElement('line', { x1: left, x2: width - right, y1: position, y2: position, class: 'chart-grid' }));
      fragment.append(svgElement('text', { x: left - 12, y: position + 4, 'text-anchor': 'end' }, value.toFixed(0)));
    }
    fragment.append(svgElement('line', { x1: left, x2: width - right, y1: y(100), y2: y(100), class: 'chart-reference' }));
    const dates = series[0].points.map((point) => point.date);
    const dateIntervals = compact ? 2 : 4;
    for (let index = 0; index <= dateIntervals; index += 1) {
      const date = dates[Math.round((dates.length - 1) * index / dateIntervals)];
      fragment.append(svgElement('text', { x: x(date), y: height - 20, 'text-anchor': index === 0 ? 'start' : index === dateIntervals ? 'end' : 'middle' }, shortDate.format(dateValue(date))));
    }
    // Context lines first; the primary stock comparison remains visually legible.
    for (const id of ['SPY', 'SPMO', 'SMIX', 'MMIX', 'S12', 'M12']) {
      const line = series.find((item) => item.id === id);
      const style = STYLE[id];
      const path = line.points.map((point, index) => `${index ? 'L' : 'M'}${x(point.date).toFixed(2)},${y(point.value).toFixed(2)}`).join(' ');
      const node = svgElement('path', { d: path, class: 'chart-line', stroke: style.color, 'stroke-width': style.width, 'stroke-dasharray': style.dash });
      node.append(svgElement('title', {}, `${id}: ends at ${number.format(line.points[line.points.length - 1].value)}`));
      fragment.append(node);
      const last = line.points[line.points.length - 1];
      fragment.append(svgElement('circle', { cx: x(last.date), cy: y(last.value), r: 2.5, fill: style.color }));
    }
    chart.replaceChildren(fragment);
    chart.removeAttribute('hidden');
    $('stock-chart-placeholder').hidden = true;
    $('stock-chart-window').textContent = `${dayFormat.format(dateValue(window.start))} close – ${dayFormat.format(dateValue(window.end))} close · rebased to 100 · ${cost} bps per side`;
  }

  function renderAudit() {
    const { summary, metadata } = saved;
    const checks = Object.entries(summary.checks).map(([name, passed]) => element('li', `${CHECK_NAMES[name] || friendly(name)}: ${passed ? 'passed' : 'not passed'}`));
    $('stock-engine-checks').replaceChildren(...checks);
    const limitations = [...new Set([...(summary.limitations || []), ...(metadata.limitations || [])])].filter((value) => typeof value === 'string');
    $('stock-limitations').replaceChildren(...limitations.map((value) => element('li', value)));
    const audit = metadata.dataset_audit || summary.dataset_audit || {};
    const items = [];
    function describe(value) {
      if (value === null || value === undefined) return 'Not supplied';
      if (typeof value === 'boolean') return value ? 'Yes' : 'No';
      if (Array.isArray(value)) return value.length ? value.map(describe).join(' · ') : 'None reported';
      if (typeof value === 'object') return Object.entries(value).filter(([name]) => !name.endsWith('sha256')).map(([name, detail]) => `${friendly(name)}: ${describe(detail)}`).join('; ');
      return String(value);
    }
    function addItem(name, value) {
      if (name.endsWith('sha256')) return;
      const row = element('div');
      row.append(element('dt', name === 'passed' ? 'Pilot-specific audit gate passed' : friendly(name)), element('dd', describe(value)));
      items.push(row);
    }
    for (const [name, value] of Object.entries(audit)) {
      addItem(name, value);
    }
    if (!items.length) {
      const row = element('div');
      row.append(element('dt', 'Detailed provenance'), element('dd', 'See the saved summary and repository.'));
      items.push(row);
    }
    $('stock-data-audit').replaceChildren(...items);
    const repairs = audit.sourced_price_reconstructions;
    if (Array.isArray(repairs) && repairs.length) {
      const descriptions = repairs.map((repair) => `${repair.symbol || 'A security'} on ${repair.date || 'the recorded date'}${Number.isFinite(repair.hourly_bars) ? ` from ${repair.hourly_bars} hourly bars` : ''}`);
      $('stock-price-caveat').textContent = `Source reconstruction disclosed: ${descriptions.join('; ')}. The official closing auction and spin-off entitlement completeness are not independently verified. This remains a vendor-price proxy experiment.`;
    }
  }

  function render() {
    const cost = Number(costSelect.value), period = periodSelect.value;
    assert(COSTS.includes(cost) && WINDOWS[period], 'Unknown view');
    const get = (id) => saved.metrics.get(key(id, cost)).metrics[period];
    const monthly = get('M12'), slow = get('S12');
    const primary = 100 * (monthly.total_return - slow.total_return);
    const replication = 100 * (get('MMIX').total_return - get('SMIX').total_return);
    const interaction = replication - primary;
    const window = WINDOWS[period];
    const direction = primary > 0 ? 'ahead of' : primary < 0 ? 'behind' : 'level with';
    $('stock-primary-spread').textContent = pp(primary);
    $('stock-primary-caption').textContent = `M12 minus S12 · ${window.label} · ${cost} bps`;
    $('stock-monthly-return').textContent = pct(monthly.total_return);
    $('stock-slow-return').textContent = pct(slow.total_return);
    $('stock-mixed-spread').textContent = pp(replication);
    $('stock-monthly-drawdown').textContent = pct(monthly.max_drawdown);
    $('stock-drawdown-context').textContent = `Semiannual S12: ${pct(slow.max_drawdown)}`;
    const spreadFor = (name) => 100 * (saved.metrics.get(key('M12', cost)).metrics[name].total_return - saved.metrics.get(key('S12', cost)).metrics[name].total_return);
    const spread2025 = spreadFor('year2025'), spread2026 = spreadFor('ytd2026');
    const reversal = spread2025 * spread2026 < 0;
    $('stock-spread-2025').textContent = pp(spread2025);
    $('stock-spread-2026').textContent = pp(spread2026);
    $('stock-perspective-title').textContent = reversal ? 'The sign changes across years.' : 'The same test, two windows.';
    $('stock-perspective-note').textContent = `M12 minus S12 at ${cost} bps per side. ${reversal ? 'A stronger result in one window does not settle the frequency question.' : 'Neither window is an independent, untouched holdout.'}`;
    $('stock-result-story').textContent = `In the ${window.label.toLowerCase()} view, monthly 12–1 selection returned ${pct(monthly.total_return)}, ${direction} the semiannual portfolio at ${pct(slow.total_return)}. Both figures include ${cost} bps per side in modeled trading costs. The comparison belongs to this 100-issuer, 20-position pilot.`;
    $('stock-interpretation').textContent = `The primary frequency difference is ${pp(primary)}; with the blended signal it is ${pp(replication)}. The difference between those effects is ${pp(interaction)}. These are observed differences for the selected window and cost assumption, not statistical significance or evidence that the full 75-stock strategy would behave the same way.`;
    const rows = IDS.map((id) => {
      const metrics = get(id);
      const row = element('tr', undefined, id === 'M12' || id === 'S12' ? 'primary-row' : id === 'SPMO' || id === 'SPY' ? 'context-row' : '');
      const label = element('th', id);
      label.scope = 'row';
      label.append(element('span', STYLE[id].label, 'portfolio-caption'));
      row.append(label, element('td', pct(metrics.total_return)), element('td', pct(metrics.max_drawdown)), element('td', `${number.format(metrics.two_sided_turnover)}×`), element('td', pct(metrics.mean_cash_weight)));
      return row;
    });
    $('stock-table-body').replaceChildren(...rows);
    $('stock-table-caption').textContent = `${window.label} · ${cost} bps per side · all six saved portfolios`;
    renderChart(cost, period);
    $('stock-load-status').textContent = `Saved results loaded. All 24 paths reconcile with their reported returns and drawdowns. Showing ${window.label.toLowerCase()} at ${cost} bps per side; this is a presentation check, not a new data audit.`;
  }

  function showError() {
    costSelect.disabled = true;
    periodSelect.disabled = true;
    $('stock-load-status').classList.add('stock-error');
    $('stock-load-status').textContent = 'The saved summary and portfolio paths could not be loaded or reconciled. No results are inferred. Reload the page or inspect the source files below.';
    $('stock-result-story').textContent = 'The result display is unavailable. The research scope and limitations remain below; numerical claims are withheld until the saved files can be checked.';
    for (const id of ['stock-primary-spread', 'stock-monthly-return', 'stock-slow-return', 'stock-mixed-spread', 'stock-monthly-drawdown', 'stock-spread-2025', 'stock-spread-2026']) $(id).textContent = 'Unavailable';
    $('stock-primary-caption').textContent = 'Saved data required';
    $('stock-drawdown-context').textContent = 'Saved data required';
    $('stock-perspective-title').textContent = 'Saved data required.';
    $('stock-perspective-note').textContent = 'Year-by-year comparisons are withheld until the saved data can be checked.';
    $('stock-interpretation').textContent = 'No interpretation is generated without a reconciled summary and portfolio paths.';
    $('stock-table-caption').textContent = 'Saved results unavailable';
    $('stock-chart').setAttribute('hidden', '');
    $('stock-chart-placeholder').hidden = false;
    $('stock-chart-placeholder').textContent = 'No chart is displayed because the saved data could not be verified.';
    const row = element('tr');
    const cell = element('td', 'Saved results unavailable.');
    cell.colSpan = 5;
    row.append(cell);
    $('stock-table-body').replaceChildren(row);
  }

  async function loadJson(path) {
    const response = await fetch(path);
    assert(response.ok, 'Saved data request failed');
    return response.json();
  }
  for (const control of [costSelect, periodSelect]) control.addEventListener('change', () => {
    try { render(); } catch { showError(); }
  });
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (saved && !costSelect.disabled) {
        try { renderChart(Number(costSelect.value), periodSelect.value); } catch { showError(); }
      }
    }, 100);
  });
  Promise.all([loadJson('data/stock-pilot-summary.json'), loadJson('data/stock-pilot-nav.json')])
    .then(([summary, nav]) => {
      saved = validate(summary, nav);
      renderAudit();
      render();
      costSelect.disabled = false;
      periodSelect.disabled = false;
    }).catch(showError);
})();
