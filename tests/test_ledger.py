"""Hand-calculated accounting tests; all inputs are synthetic."""

from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from spmo_lab.ledger import Dividend, Ledger, LedgerError


class LedgerTests(unittest.TestCase):
    def holding_a(self, *, cash=1000, weight=1.0, cost_bps=0):
        ledger = Ledger(cash, cost_bps=cost_bps)
        ledger.open_session("2025-01-02", {"A": 100}, targets={"A": weight}, eligible_ids={"A", "B", "C"})
        ledger.close_session("2025-01-02", {"A": 100})
        return ledger

    def test_initial_purchase_scales_including_fee_without_borrowing(self):
        ledger = Ledger(1000, cost_bps=10)
        ledger.open_session("2025-01-02", {"A": 100, "B": 50}, targets={"A": .5, "B": .5})
        snapshot = ledger.close_session("2025-01-02", {"A": 100, "B": 50})
        self.assertAlmostEqual(ledger.positions["A"], 500 / 1.001 / 100)
        self.assertAlmostEqual(ledger.positions["B"], 500 / 1.001 / 50)
        self.assertGreaterEqual(ledger.cash, 0)
        self.assertAlmostEqual(snapshot["nav"], 1000 / 1.001)
        self.assertAlmostEqual(ledger.cumulative_cost, 1000 - snapshot["nav"])
        self.assertTrue(all(trade["pretrade_nav"] == 1000 for trade in ledger.trades))

    def test_sales_execute_before_buys_and_each_side_pays(self):
        ledger = Ledger(1000, cost_bps=5)
        ledger.open_session("2025-01-02", {"B": 100}, targets={"B": 1})
        ledger.close_session("2025-01-02", {"B": 100})
        before = ledger.cumulative_cost
        original_value = ledger.positions["B"] * 100
        ledger.open_session("2025-01-03", {"A": 100, "B": 100}, targets={"A": 1})
        ledger.close_session("2025-01-03", {"A": 100})
        sells, buys = ledger.trades[-2:]
        self.assertEqual((sells["side"], buys["side"]), ("sell", "buy"))
        self.assertEqual((sells["security_id"], buys["security_id"]), ("B", "A"))
        self.assertAlmostEqual(sells["pretrade_nav"], original_value)
        self.assertAlmostEqual(buys["pretrade_nav"], original_value)
        self.assertAlmostEqual(ledger.positions["A"] * 100, original_value * .9995 / 1.0005)
        self.assertAlmostEqual(ledger.cumulative_cost - before, sells["cost"] + buys["cost"])
        self.assertGreaterEqual(ledger.cash, 0)

    def test_failed_sale_cannot_finance_buy_and_ordinary_orders_do_not_retry(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": None, "B": 100}, targets={"B": 1})
        snapshot = ledger.close_session("2025-01-03", {"A": 100})
        self.assertEqual(ledger.positions, {"A": 10})
        self.assertEqual(snapshot["nav"], 1000)
        self.assertEqual(len(ledger.trades), 1)
        self.assertTrue(any(item["type"] == "missing_open_valuation_only" for item in ledger.exceptions))
        ledger.open_session("2025-01-06", {"A": 100, "B": 100})
        ledger.close_session("2025-01-06", {"A": 100})
        self.assertEqual(len(ledger.trades), 1)

    def test_partial_sale_failure_scales_all_executable_buys_proportionally(self):
        ledger = Ledger(1000, cost_bps=0)
        ledger.open_session("2025-01-02", {"A": 100, "B": 100}, targets={"A": .5, "B": .5})
        ledger.close_session("2025-01-02", {"A": 100, "B": 100})
        ledger.open_session("2025-01-03", {"A": None, "B": 100, "C": 100, "D": 100}, targets={"C": .5, "D": .5})
        ledger.close_session("2025-01-03", {"A": 100, "C": 100, "D": 100})
        self.assertEqual(ledger.positions, {"A": 5, "C": 2.5, "D": 2.5})
        self.assertEqual(ledger.cash, 0)

    def test_split_conserves_value_and_changes_shares(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": 50}, splits={"A": 2})
        snapshot = ledger.close_session("2025-01-03", {"A": 50})
        self.assertEqual(ledger.positions["A"], 20)
        self.assertEqual(snapshot["nav"], 1000)
        self.assertEqual(len(ledger.trades), 1)

    def test_split_adjusts_fallback_valuation_but_never_creates_fill(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": None, "B": 100}, splits={"A": 2}, targets={"B": 1})
        snapshot = ledger.close_session("2025-01-03", {"A": 50})
        flagged = [item for item in ledger.exceptions if item["type"] == "missing_open_valuation_only"]
        self.assertEqual(flagged[-1]["valuation_price"], 50)
        self.assertEqual(snapshot["nav"], 1000)
        self.assertEqual(ledger.positions["A"], 20)
        self.assertNotIn("B", ledger.positions)

    def test_ex_date_entitlement_survives_sale_and_cash_waits_for_pay_date(self):
        ledger = self.holding_a()
        dividend = Dividend("a-div", "A", "2025-01-03", "2025-01-07", 2)
        ledger.open_session("2025-01-03", {"A": 98}, targets={}, dividends=[dividend])
        snapshot = ledger.close_session("2025-01-03", {})
        self.assertEqual(snapshot["cash"], 980)
        self.assertEqual(snapshot["receivables"], 20)
        self.assertEqual(snapshot["nav"], 1000)
        self.assertEqual(ledger.receivables["a-div"]["ex_date_quantity"], 10)
        ledger.open_session("2025-01-06", {})
        ledger.close_session("2025-01-06", {})
        self.assertEqual(ledger.cash, 980)
        ledger.open_session("2025-01-07", {})
        snapshot = ledger.close_session("2025-01-07", {})
        self.assertEqual(snapshot["cash"], 1000)
        self.assertEqual(snapshot["receivables"], 0)

    def test_ex_date_new_purchase_does_not_receive_dividend(self):
        ledger = Ledger(1000, cost_bps=0)
        ledger.open_session("2025-01-02", {"A": 100}, targets={"A": 1},
                            dividends=[Dividend("a-div", "A", "2025-01-02", "2025-01-03", 2)])
        ledger.close_session("2025-01-02", {"A": 100})
        ledger.open_session("2025-01-03", {"A": 100})
        ledger.close_session("2025-01-03", {"A": 100})
        self.assertEqual(ledger.cash, 0)
        self.assertEqual(ledger.events[0]["ex_date_quantity"], 0)

    def test_reinvestment_uses_only_paid_dividend_and_previous_close_weights(self):
        ledger = Ledger(1000, cost_bps=0)
        ledger.open_session("2025-01-02", {"A": 100, "B": 100}, targets={"A": .4, "B": .4})
        ledger.close_session("2025-01-02", {"A": 100, "B": 100})
        ledger.open_session("2025-01-03", {"A": 100, "B": 100},
                            dividends=[Dividend("a-div", "A", "2025-01-03", "2025-01-06", 2)])
        ledger.close_session("2025-01-03", {"A": 100, "B": 100})
        ledger.open_session("2025-01-06", {"A": 100, "B": 100})
        ledger.close_session("2025-01-06", {"A": 200, "B": 100})
        self.assertEqual(ledger.cash, 208)
        self.assertEqual(len(ledger.trades), 2)
        ledger.open_session("2025-01-07", {"A": 100, "B": 100})
        ledger.close_session("2025-01-07", {"A": 100, "B": 100})
        self.assertAlmostEqual(ledger.positions["A"], 4 + 8 * 2 / 3 / 100)
        self.assertAlmostEqual(ledger.positions["B"], 4 + 8 / 3 / 100)
        self.assertAlmostEqual(ledger.cash, 200)
        ledger.open_session("2025-01-08", {"A": 100, "B": 100})
        ledger.close_session("2025-01-08", {"A": 100, "B": 100})
        self.assertEqual(len(ledger.trades), 4)

    def test_reinvestment_budget_includes_fees(self):
        ledger = self.holding_a(weight=.5, cost_bps=10)
        original = ledger.positions["A"]
        ledger.open_session("2025-01-03", {"A": 100},
                            dividends=[Dividend("a-div", "A", "2025-01-03", "2025-01-03", 2)])
        ledger.close_session("2025-01-03", {"A": 100})
        strategic_cash = 1000 - original * 100 * 1.001
        ledger.open_session("2025-01-06", {"A": 100})
        ledger.close_session("2025-01-06", {"A": 100})
        self.assertAlmostEqual(ledger.cash, strategic_cash)
        self.assertAlmostEqual(ledger.positions["A"] - original, original * 2 / 1.001 / 100)

    def test_scheduled_rebalance_consumes_same_day_payment_without_double_reinvestment(self):
        ledger = self.holding_a(weight=.5)
        ledger.open_session("2025-01-03", {"A": 100}, targets={"A": .5},
                            dividends=[Dividend("a-div", "A", "2025-01-03", "2025-01-03", 2)])
        ledger.close_session("2025-01-03", {"A": 100})
        self.assertEqual(ledger.positions["A"], 5.05)
        self.assertEqual(ledger.cash, 505)
        count = len(ledger.trades)
        ledger.open_session("2025-01-06", {"A": 100})
        ledger.close_session("2025-01-06", {"A": 100})
        self.assertEqual(len(ledger.trades), count)
        self.assertEqual(ledger.cash, 505)

    def test_forced_exit_retries_does_not_buy_back_and_proceeds_remain_cash(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": None}, forced_exits={"A"}, targets={"A": 1}, eligible_ids={"A"})
        ledger.close_session("2025-01-03", {"A": 100})
        self.assertEqual(ledger.pending_exits, {"A"})
        ledger.open_session("2025-01-06", {"A": 100}, targets={"A": 1}, eligible_ids={"A"})
        ledger.close_session("2025-01-06", {})
        self.assertEqual(ledger.positions, {})
        self.assertEqual(ledger.pending_exits, set())
        self.assertEqual(ledger.cash, 1000)
        self.assertEqual(len(ledger.trades), 2)
        self.assertEqual(ledger.trades[-1]["reason"], "forced_exit")
        ledger.open_session("2025-01-07", {"A": 100}, targets={"A": 1}, eligible_ids={"A"})
        ledger.close_session("2025-01-07", {"A": 100})
        self.assertEqual(ledger.positions, {"A": 10})

    def test_dividend_reinvestment_cannot_buy_removed_holding(self):
        ledger = Ledger(1000, cost_bps=0)
        ledger.open_session("2025-01-02", {"A": 100, "B": 100}, targets={"A": .5, "B": .5})
        ledger.close_session("2025-01-02", {"A": 100, "B": 100})
        ledger.open_session("2025-01-03", {"A": 100, "B": 100},
                            dividends=[Dividend("a-div", "A", "2025-01-03", "2025-01-03", 2)])
        ledger.close_session("2025-01-03", {"A": 100, "B": 100})
        ledger.open_session("2025-01-06", {"A": 100, "B": 100}, forced_exits={"A"}, eligible_ids={"B"})
        ledger.close_session("2025-01-06", {"B": 100})
        self.assertEqual(ledger.positions, {"B": 5.1})
        self.assertEqual(ledger.cash, 500)
        self.assertEqual([item["side"] for item in ledger.trades[-2:]], ["sell", "buy"])

    def test_overlapping_actions_net_once_and_use_one_pretrade_nav(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": 50, "B": 100}, splits={"A": 2}, forced_exits={"A"},
                            targets={"A": .5, "B": .5}, eligible_ids={"B"},
                            dividends=[Dividend("a-div", "A", "2025-01-03", "2025-01-03", 1)])
        snapshot = ledger.close_session("2025-01-03", {"B": 100})
        trades = ledger.trades[1:]
        self.assertEqual(len(trades), 2)
        self.assertEqual([(item["security_id"], item["side"]) for item in trades], [("A", "sell"), ("B", "buy")])
        self.assertTrue(all(item["pretrade_nav"] == 1020 for item in trades))
        self.assertEqual(trades[0]["quantity"], 20)
        self.assertEqual(snapshot["nav"], 1020)
        self.assertAlmostEqual(snapshot["cash"], 510)
        ledger.open_session("2025-01-06", {"B": 100}, eligible_ids={"B"})
        ledger.close_session("2025-01-06", {"B": 100})
        self.assertEqual(len(ledger.trades), 3)

    def test_no_eligible_holdings_keeps_dividend_cash_without_later_sweep(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": 100},
                            dividends=[Dividend("a-div", "A", "2025-01-03", "2025-01-03", 1)])
        ledger.close_session("2025-01-03", {"A": 100})
        ledger.open_session("2025-01-06", {"A": 100}, eligible_ids=set())
        ledger.close_session("2025-01-06", {"A": 100})
        ledger.open_session("2025-01-07", {"A": 100}, eligible_ids={"A"})
        ledger.close_session("2025-01-07", {"A": 100})
        self.assertEqual(ledger.cash, 10)
        self.assertEqual(len(ledger.trades), 1)

    def test_duplicate_dividend_id_is_atomic_and_rejected_after_payment(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": 100},
                            dividends=[Dividend("same", "A", "2025-01-03", "2025-01-03", 1)])
        ledger.close_session("2025-01-03", {"A": 100})
        before = deepcopy(ledger.__dict__)
        with self.assertRaisesRegex(LedgerError, "duplicate"):
            ledger.open_session("2025-01-06", {"A": 100}, splits={"A": 2},
                                dividends=[Dividend("same", "A", "2025-01-06", "2025-01-06", 1)])
        self.assertEqual(ledger.__dict__, before)

    def test_post_fill_failure_restores_live_state_and_preserves_history_records(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": None, "B": 100}, targets={"B": 1})
        ledger.close_session("2025-01-03", {"A": 100})
        before = deepcopy(ledger.__dict__)
        histories = {name: (getattr(ledger, name), tuple(getattr(ledger, name)))
                     for name in ("trades", "events", "exceptions", "snapshots")}
        record_trade = Ledger._record_trade

        def fail_after_fill(instance, *args, **kwargs):
            record_trade(instance, *args, **kwargs)
            instance.exceptions.append({"type": "injected_failure"})
            raise LedgerError("injected failure after trade append")

        with patch.object(Ledger, "_record_trade", fail_after_fill):
            with self.assertRaisesRegex(LedgerError, "injected failure"):
                ledger.open_session("2025-01-06", {"A": 50, "B": 100},
                                    targets={"B": 1}, forced_exits={"A"}, splits={"A": 2},
                                    dividends=[Dividend("rollback", "A", "2025-01-06", "2025-01-06", 1)])
        self.assertEqual(ledger.__dict__, before)
        for name, (history, original_records) in histories.items():
            self.assertIs(getattr(ledger, name), history)
            self.assertEqual(len(history), len(original_records))
            self.assertTrue(all(actual is original for actual, original in zip(history, original_records)))
        # The same date and event can be retried after the failed transaction.
        ledger.open_session("2025-01-06", {"A": 50, "B": 100},
                            targets={"B": 1}, forced_exits={"A"}, splits={"A": 2},
                            dividends=[Dividend("rollback", "A", "2025-01-06", "2025-01-06", 1)])
        snapshot = ledger.close_session("2025-01-06", {"B": 100})
        self.assertAlmostEqual(snapshot["nav"], 1020)
        self.assertEqual(set(ledger.positions), {"B"})

    def test_invalid_inputs_and_session_order(self):
        for initial in (-1, math.inf, math.nan, True, "100"):
            with self.subTest(initial=initial), self.assertRaises(LedgerError):
                Ledger(initial)
        for fee in (-1, math.inf, 10000, True):
            with self.subTest(fee=fee), self.assertRaises(LedgerError):
                Ledger(1000, fee)
        ledger = Ledger(1000)
        for targets in ({"A": 1.1}, {"A": -.1}, {"A": math.nan}, {"A": True}, {"A": .6, "B": .6}):
            with self.subTest(targets=targets), self.assertRaises(LedgerError):
                ledger.open_session("2025-01-02", {"A": 100}, targets=targets)
        for price in (0, -1, math.inf, math.nan, True):
            with self.subTest(price=price), self.assertRaises(LedgerError):
                ledger.open_session("2025-01-02", {"A": price})
        with self.assertRaises(LedgerError):
            ledger.close_session("2025-01-02", {})
        ledger.open_session("2025-01-02", {"A": 100}, targets={"A": 1})
        with self.assertRaises(LedgerError):
            ledger.open_session("2025-01-03", {"A": 100})
        with self.assertRaises(LedgerError):
            ledger.close_session("2025-01-03", {"A": 100})
        ledger.close_session("2025-01-02", {"A": 100})
        for session in ("2025-01-02", "2025-01-01", "20250103", "2025-02-30"):
            with self.subTest(session=session), self.assertRaises(LedgerError):
                ledger.open_session(session, {"A": 100})

    def test_missing_or_invalid_close_blocks_without_stale_mark(self):
        ledger = self.holding_a()
        ledger.open_session("2025-01-03", {"A": 100})
        before = deepcopy(ledger.__dict__)
        for closes in ({}, {"A": None}, {"A": 0}, {"A": math.nan}):
            with self.subTest(closes=closes), self.assertRaises(LedgerError):
                ledger.close_session("2025-01-03", closes)
            self.assertEqual(ledger.__dict__, before)
        snapshot = ledger.close_session("2025-01-03", {"A": 101})
        self.assertEqual(snapshot["nav"], 1010)

    def test_invalid_dividend_and_split_data_fail_before_mutation(self):
        ledger = self.holding_a()
        before = deepcopy(ledger.__dict__)
        invalid = [Dividend("x", "A", "2025-01-02", "2025-01-06", 1),
                   Dividend("x", "A", "2025-01-03", "2025-01-02", 1),
                   Dividend("x", "A", "2025-01-03", "2025-01-06", -1)]
        for action in invalid:
            with self.subTest(action=action), self.assertRaises(LedgerError):
                ledger.open_session("2025-01-03", {"A": 100}, dividends=[action])
            self.assertEqual(ledger.__dict__, before)
        for ratio in (None, 0, -1, math.inf):
            with self.subTest(ratio=ratio), self.assertRaises(LedgerError):
                ledger.open_session("2025-01-03", {"A": 100}, splits={"A": ratio})
            self.assertEqual(ledger.__dict__, before)


if __name__ == "__main__":
    unittest.main()
