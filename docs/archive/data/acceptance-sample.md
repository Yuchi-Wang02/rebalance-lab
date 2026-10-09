> Archived research document. Historical scope and status are retained; see the [current validation case](../../studies/validation-study.md).

# Historical-data acceptance sample

The next data milestone is a small, inspectable **event-led sample**, before a full-universe market run. It must show that source records can support the existing [data contract](feasibility.md) and [protocol](../methods/original-stock-protocol.md). It is neither a performance sample nor permission to infer full historical coverage.

No provider sample described here has been acquired or accepted. The existing SPMO/SPY Yahoo diagnostic is a separate ingestion check; it does not supply the historical membership, capitalization or event evidence below.

## Choose a route before an extract

If an institutional WRDS/CRSP entitlement already exists, first ask whether its permitted components and export can cover the required securities, events, fields and historical availability. Confirm the actual subscription, data dictionary and extraction rights; the provider name alone does not establish those capabilities. A local authorized export imported into this workspace is sufficient for review. Do not assume a new credential or purchase is necessary.

Otherwise validate component contracts before selecting a commercial route: historical prices and class-level capitalization, a complete membership history with timing evidence, and action/settlement records may come from different sources. Sharadar’s own `SP500` table is a verified historical-membership candidate; use a separate supplier if its coverage fails acceptance. These remain candidate feeds without an accepted authorized sample. See the [purchase guide](purchase-guide.md) for direct links, verified prices and a sample request. Norgate is a conditional Windows export route whose documented current-only capitalization and dividend-date gaps need other evidence. The [source plan](sources.md) records what has actually been inspected.

For every source retain its field definitions, units, permitted use, historical coverage, extraction/version time and availability semantics. Distinguish original announcement evidence from reconstructed or assumed timestamps. An inferred timestamp must remain visibly flagged; extraction time is not historical knowledge time.

## Select cases by behavior

Use as few permanent security IDs as needed to cover the cases below; one security can cover several cases. Include a continuously listed control as well as difficult events. Choose cases from verified source records rather than naming securities whose history has not been checked.

| Case | Required evidence | Expected acceptance check |
|---|---|---|
| Continuing constituent | Membership interval, raw prices, class-level shares/cap, publication timing | Joins remain one-to-one; a signal uses only information available at that close |
| Index entry and exit | Membership state before/after, effective and known times, source announcement/version | Entry is not backfilled; removal cannot trigger an exit before it is both effective and known; next tradable-open policy is traceable |
| Ticker change or code reuse | Stable ID and dated ticker mappings | Old/new symbols map to the correct security without merging different issuers or duplicating returns |
| Split | Ratio, units, effective time, raw prices and action record | Shares scale by the ratio, cash does not arise from an ordinary split, and the signal series has no mechanical split return |
| Cash dividend | Per-share amount, currency, ex-date, pay date, applicable quantity and revisions | Receivable is recognized once on the ex-date; cash becomes spendable on the pay date; no second dividend is hidden in the signal series |
| Multiple share classes | Separate security IDs, one issuer ID, class-level shares/cap | No company-wide cap is copied onto both classes; issuer exposure sums the distinct positions |
| Merger or delisting | Last tradable session, terms, cash/security consideration, settlement timing and sources | Missing quotes do not create fictitious fills; share/cash/receivable transitions reconcile to the actual terms |
| Halt or unavailable opening fill | Price/status flags and next tradable observation | No forward-filled opening trade; ordinary orders expire and required exits retry according to the protocol |

Include SPMO and SPY distributions and documented return conventions in a small benchmark reconciliation sample as well. A stock-data entitlement does not establish ETF coverage.

The sample should contain a continuous common exchange calendar for each inspected signal window, enough prehistory for every active lookback, and observations through event settlement or the resolution of any pending position. A few surrounding dates can explain an action but cannot validate a 252-session signal. Separate short event excerpts from complete signal windows explicitly. Record every sampled date range and why it was chosen; do not call the sample representative or survivorship-free solely because it includes a delisted name.

## Normalized review bundle

Preserve original files privately where licensing requires it. Each normalized record must link back to its source record or extract. Names below define the review contract; a provider adapter may map different native field names.

| Artifact | Required fields or content |
|---|---|
| `sample_manifest.json` | Source/dataset/version, safe extraction description, extracted-at time, covered IDs/dates, file hashes, license/redistribution decision, purpose of each selected case |
| `security_master.csv` | `security_id`, `issuer_id`, historical ticker, share class, currency, exchange, validity intervals, source reference |
| `membership.csv` | `security_id`, effective interval, `known_at`, timing-evidence type and source reference |
| `prices.csv` | `security_id`, exchange session, raw OHLC, volume, currency, availability time, tradability/valuation status, source reference |
| `capitalization.csv` | `security_id`, shares or total class cap, units, effective time, `known_at`, revision/vintage identifier, staleness/availability evidence, source reference |
| `actions.csv` | Event/security IDs, event type, effective and known times, split ratio or dividend amount/ex/pay dates or settlement terms, currency, revision and source reference |
| `calendar.csv` | Session, timezone-aware open/close, holiday/early-close definition and calendar version |
| `expected_ledger.csv` | Case/event ID, timestamps, expected shares/cash/receivables, units, derivation and supporting source references |
| `findings.csv` | Check/case ID, severity, observation, source evidence, resolution or unresolved dependency; no silent deletions |

Use stable IDs for joins. Keep availability and economic effective times distinct. Reject duplicate keys, overlapping unexplained validity intervals, invalid units, missing required sessions and unexplained source disagreements. A not-applicable field must have a reason; a missing payment date cannot be filled with an ex-date.

## Reconcile the ledger before scaling

Write expected event transitions from source terms independently of the engine output. For an ordinary split with ratio `r`, verify `q_after = r × q_before`, with cash unchanged by the split itself. For a cash dividend, verify the entitlement quantity and `receivable = eligible_quantity × amount_per_share`, then transfer that same receivable into cash on payment; count it once. Explain combined split/dividend ordering from the source terms rather than assuming a universal order.

Reconcile cash, receivables and raw marked security value to total NAV at every inspected step. Apply fees only to actual fills, make failed fills visible and never fund a purchase from an unfilled sale. At membership removal, trace both timing conditions and the first permissible executable opening fill. At a merger/delisting, record any successor security or pending consideration and reconcile it through settlement; the last quoted close is not automatically liquidation proceeds.

The current synthetic engine does not support all merger, spinoff or delisting settlements. Finding a valid source record for such a case is a data milestone, not engine acceptance. Keep the case blocked until its explicit accounting and independent reconciliation exist; do not discard it to obtain a passing report.

## Acceptance record and next gate

For each case, mark source semantics, identifiers, calendar/price coverage, historical availability, action terms and ledger reconciliation as **accepted**, **unresolved** or **not applicable with reason**. Numeric tolerance must follow documented source precision and rounding; do not invent a broad tolerance to hide an accounting mismatch.

Publish a metadata-only case inventory and findings summary when permitted. The bundle passes this local gate only after all required cases have supporting records and no unresolved critical timing, unit, action or accounting gap. This does not accept the whole market dataset: the later audit must verify complete membership, every required security/session, historical revisions and all relevant events across the actual experiment interval.

Do not feed the sample into a performance leaderboard. Its purpose is to decide whether the data route and accounting can faithfully support a full study. Market results remain unavailable until the full data, engine and market-run gates pass.
