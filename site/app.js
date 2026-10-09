"use strict";

// The homepage reads saved study summaries. It does not fetch prices or run a strategy.
(() => {
  const COSTS = [0, 5, 10, 25];
  const PERIODS = ["year2025", "ytd2026", "full_period"];
  const number = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const $ = (id) => document.getElementById(id);
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const pp = (value) =>
    `${value > 0 ? "+" : value < 0 ? "−" : ""}${number.format(Math.abs(value))} pp`;
  const percent = (value) => `${number.format(value * 100)}%`;
  const assert = (condition) => {
    if (!condition) throw new Error("Saved summary does not match this study.");
  };

  async function load(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path, { signal: controller.signal });
      if (!response.ok) throw new Error("Summary unavailable.");
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function stockScenarios(data) {
    const metadata = data?.metadata;
    assert(
      data?.data_track === "baseline_issuer_stock_pilot" &&
        data.formal_protocol_compliant === false,
    );
    assert(data.cohort_size === 100 && metadata?.selected_count === 20);
    assert(
      data.initial_signal === "2024-12-31" &&
        data.report_anchor === "2025-12-31" &&
        data.report_end === "2026-10-02",
    );
    assert(
      Array.isArray(data.runs) &&
        data.runs.length === 16 &&
        Array.isArray(data.comparisons),
    );
    const runs = new Map();
    for (const run of data.runs) {
      assert(
        ["M12", "S12", "MMIX", "SMIX"].includes(run.strategy_id) &&
          COSTS.includes(run.cost_bps_per_side),
      );
      const key = `${run.strategy_id}|${run.cost_bps_per_side}`;
      assert(!runs.has(key));
      for (const period of PERIODS) {
        const metric = run.metrics?.[period];
        assert(
          metric && finite(metric.total_return) && metric.total_return > -1,
        );
        assert(
          finite(metric.start_nav) &&
            metric.start_nav > 0 &&
            finite(metric.end_nav) &&
            metric.end_nav > 0,
        );
        assert(
          Math.abs(
            metric.total_return - (metric.end_nav / metric.start_nav - 1),
          ) < 0.000001,
        );
      }
      runs.set(key, run);
    }
    const scenarios = new Map();
    for (const cost of COSTS) {
      const values = {};
      for (const period of PERIODS) {
        const monthly = runs.get(`M12|${cost}`).metrics[period].total_return;
        const slow = runs.get(`S12|${cost}`).metrics[period].total_return;
        const spread = 100 * (monthly - slow);
        const published = data.comparisons.filter(
          (row) => row.cost_bps_per_side === cost && row.period === period,
        );
        assert(
          published.length === 1 &&
            finite(published[0].primary_frequency_difference_pp),
        );
        assert(
          Math.abs(spread - published[0].primary_frequency_difference_pp) <
            0.000001,
        );
        // The chart's fixed ±10 pp axis is shared across every displayed scenario.
        assert(Math.abs(spread) <= 10);
        values[period] = spread;
      }
      scenarios.set(cost, values);
    }
    return scenarios;
  }

  function showStockCost(scenarios, cost) {
    const values = scenarios.get(cost);
    assert(values);
    for (const [period, suffix] of [
      ["year2025", "2025"],
      ["ytd2026", "2026"],
      ["full_period", "full"],
    ]) {
      const value = values[period];
      $(`home-gap-${suffix}`).textContent = pp(value);
      const bar = $(`home-bar-${suffix}`);
      bar.classList.toggle("positive", value >= 0);
      bar.classList.toggle("negative", value < 0);
      bar.style.setProperty("--bar-width", `${Math.abs(value) * 5}%`);
    }
    $("home-cost-label").textContent = `${cost} bps per side`;
    const base = scenarios.get(5).full_period,
      stressed = scenarios.get(25).full_period;
    $("home-cost-reading").textContent =
      cost === 5
        ? `The full-period difference falls from ${pp(base)} at 5 bps to ${pp(stressed)} at 25 bps per side.`
        : `At ${cost} bps per side, the full-period difference is ${pp(values.full_period)}. The same comparison is ${pp(base)} at 5 bps and ${pp(stressed)} at 25 bps.`;
    $("home-stock-status").textContent =
      `Saved results · ${cost} bps per side · three observed windows. No interpolated scenarios.`;
  }

  load("data/stock-pilot-summary.json")
    .then((data) => {
      const scenarios = stockScenarios(data);
      showStockCost(scenarios, 5);
      $("home-cost-controls").disabled = false;
      document.querySelectorAll('input[name="home-cost"]').forEach((input) => {
        input.addEventListener("change", () => {
          if (input.checked) showStockCost(scenarios, Number(input.value));
        });
      });
    })
    .catch(() => {
      $("home-cost-controls").disabled = true;
      $("home-stock-status").textContent =
        "Other saved scenarios could not be checked. The published 5 bps snapshot remains visible; consult the full stock report.";
    });

  load("data/etf-pilot-summary.json")
    .then((data) => {
      const primary = data?.primary?.full_period;
      assert(
        data?.experiment_id === "sector-etf-frequency-v1" &&
          data.market_pilot_executed === true,
      );
      assert(
        data.data_track === "real_market_adjusted_price_pilot" &&
          data.original_stock_experiment_completed === false,
      );
      assert(
        data.boundaries?.report_anchor_on_or_before === "2000-12-29" &&
          data.boundaries?.full_year_end_on_or_before === "2025-12-31",
      );
      assert(
        primary?.monthly_run_id === "M12-5bps" &&
          primary.semiannual_run_id === "S12-03-09-5bps",
      );
      assert(
        primary.signal === "12-1" &&
          primary.cost_bps_per_side === 5 &&
          primary.phase?.[0] === 3 &&
          primary.phase?.[1] === 9,
      );
      assert(
        [
          "monthly_cagr",
          "semiannual_cagr",
          "cagr_difference_pp",
          "monthly_max_drawdown",
          "semiannual_max_drawdown",
        ].every((field) => finite(primary[field])),
      );
      assert(
        Math.abs(
          primary.cagr_difference_pp -
            100 * (primary.monthly_cagr - primary.semiannual_cagr),
        ) < 0.000001,
      );
      const unit = document.createElement("small");
      unit.textContent = "pp";
      $("home-etf-gap").replaceChildren(
        document.createTextNode(
          `${primary.cagr_difference_pp < 0 ? "−" : primary.cagr_difference_pp > 0 ? "+" : ""}${number.format(Math.abs(primary.cagr_difference_pp))} `,
        ),
        unit,
      );
      $("home-etf-monthly").textContent = percent(primary.monthly_cagr);
      $("home-etf-slow").textContent = percent(primary.semiannual_cagr);
      $("home-etf-status").textContent =
        "Saved primary comparison checked · 2001–2025 · 5 bps per side.";
    })
    .catch(() => {
      $("home-etf-status").textContent =
        "The saved summary could not be checked. Published figures are shown; see the full report and its source files.";
    });
})();
