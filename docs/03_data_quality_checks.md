# 03 — Data quality checks

**Owner:** Analytics Engineering · **Last run:** 2026-11-03, full extract, dbt 1.12.6 · **Issue IDs:** DQ-01 to DQ-21 in [`issue_register.yml`](../sql/data_quality/issue_register.yml), explained in the [data quality report](data_quality_report.md)

This is the sanity-check log. Checks 1 to 8 ran on the raw extract before any modelling, and check 9 ran on the marts afterwards. The raw checks shaped the models (grain, keys, exclusions). The mart checks show that the marts did not lose, duplicate or redefine anything. Each check lists what was checked, the SQL that reproduces it, the result and a verdict: **OK**, or **issue** with the DQ ID it is logged under. An issue is a property of the source that the models handle and the tests watch; none of them blocks the build.

## Summary

- **Load: passed.** All 9 files reconcile: parsed rows = the release's row counts = rows in `raw`. The two gaps between file lines and rows (reviews -5,495, translation +1) come from the file format and are fully explained.
- **Keys and references: no orphans, but the obvious keys mislead.** The 6 foreign keys have no orphans. But `customer_id` is issued per order (DQ-01), `review_id` and `order_id` repeat in reviews (DQ-02, DQ-03), 261,831 geolocation rows are exact duplicates (DQ-06), and 775 orders have no items (DQ-08).
- **Nulls, ranges and time: mostly passed.** Order timestamps are empty only where the order never reached that step, except on a few delivered orders (DQ-14). 610 products have no category (DQ-07). Implausible values are rare (DQ-10 to DQ-13). The months at both ends of the extract are incomplete, so trends use 2017-01 to 2018-08 (DQ-19).
- **Reconciliation and lifecycle: did not pass; accepted as baselines.** On 249 orders, payments differ from items + freight by more than R$1. Across all orders with both, payments are R$2,870.39 (0.02%) higher (DQ-16). 1,410 orders have contradictory lifecycle timestamps or statuses (DQ-14). Both are flagged in the marts, never dropped.
- **Marts: passed.** There are 99,441 placed, 98,207 net and 96,478 delivered orders. Every tested query path returns the same net orders and net GMV, and GMV reconciles exactly across every mart that carries it. The last `dbt build` passed 300 of 300 tests.

## How to reproduce

```bash
uv run python scripts/run_sql.py sql/data_quality/01_row_counts_vs_load_audit.sql
```

[`scripts/run_sql.py`](../scripts/run_sql.py) opens the warehouse read-only and prints every result set in the file (each starts with a `-- result: <name>` line). The files are plain DuckDB SQL, so any DuckDB client can run them, and all eight together run in under a second on the full extract. `make cache` re-runs them and saves each result set to `data/cache/sql/`. The app's *Raw data issues* page and [`reports/report.html`](../reports/report.html) read from there. Breakdowns that are not in the files are in the [appendix](#appendix-follow-up-queries). Each DQ ID is written up in [section 3 of the data quality report](data_quality_report.md#3-issues-by-class).

| # | Check | SQL file | Result set | Verdict |
|---|---|---|---|---|
| 1 | Row-count reconciliation | [`01_row_counts_vs_load_audit.sql`](../sql/data_quality/01_row_counts_vs_load_audit.sql) | `row_counts` | OK (format traps logged as DQ-18) |
| 2 | Primary-key uniqueness | [`02_primary_keys.sql`](../sql/data_quality/02_primary_keys.sql) | `primary_keys` | Issue: DQ-01, DQ-02, DQ-03, DQ-06 |
| 3 | Nulls | [`03_null_profile.sql`](../sql/data_quality/03_null_profile.sql) | `null_profile` | Issue: DQ-07, DQ-14 |
| 4 | Value ranges and outliers | [`04_value_ranges_and_outliers.sql`](../sql/data_quality/04_value_ranges_and_outliers.sql) | `value_ranges` | Issue: DQ-07, DQ-10, DQ-11, DQ-13 |
| 5 | Time ranges and monthly coverage | [`05_time_ranges_and_coverage.sql`](../sql/data_quality/05_time_ranges_and_coverage.sql) | `time_ranges`, `monthly_coverage` | Issue: DQ-12, DQ-19, DQ-21 |
| 6 | Referential integrity | [`06_referential_integrity.sql`](../sql/data_quality/06_referential_integrity.sql) | `referential_integrity` | Orphans OK; issue: DQ-08, DQ-09, DQ-20 |
| 7 | Payments vs items + freight | [`07_payment_reconciliation.sql`](../sql/data_quality/07_payment_reconciliation.sql) | `summary`, `difference_buckets` | Issue: DQ-16 |
| 8 | Lifecycle consistency | [`08_lifecycle_consistency.sql`](../sql/data_quality/08_lifecycle_consistency.sql) | `lifecycle_anomalies` | Issue: DQ-14; DQ-15 from the register |
| 9 | Marts after modelling | [`q0_order_count_reconciliation.sql`](../analyses/q0_order_count_reconciliation.sql) and dbt tests | `named_order_metrics`, `query_paths` | OK |

## 1. Row-count reconciliation

**Checked.** Four counts per file:
- **Physical lines:** newline characters minus the header, which is what `wc -l` suggests.
- **Parsed rows:** rows read by DuckDB's CSV parser.
- **Release count:** the row counts parsed when this Kaggle release was downloaded, kept in [`expected_row_counts.yml`](../ingestion/expected_row_counts.yml). It catches a changed or truncated file; the comparison with physical lines is the independent check of the parser.
- **Rows in `raw`.**

The loader ([`load_raw.py`](../ingestion/load_raw.py)) writes the first three, plus the file's md5, to `raw.load_audit`. A full load fails if any parsed count differs from the release.

**SQL:** [`01_row_counts_vs_load_audit.sql`](../sql/data_quality/01_row_counts_vs_load_audit.sql), result `row_counts`.

| Table | Physical lines | Parsed rows | Release count | Rows in `raw` | Parsed minus lines |
|---|---:|---:|---:|---:|---:|
| geolocation | 1,000,163 | 1,000,163 | 1,000,163 | 1,000,163 | 0 |
| order_items | 112,650 | 112,650 | 112,650 | 112,650 | 0 |
| order_payments | 103,886 | 103,886 | 103,886 | 103,886 | 0 |
| orders | 99,441 | 99,441 | 99,441 | 99,441 | 0 |
| customers | 99,441 | 99,441 | 99,441 | 99,441 | 0 |
| order_reviews | 104,719 | 99,224 | 99,224 | 99,224 | **-5,495** |
| products | 32,951 | 32,951 | 32,951 | 32,951 | 0 |
| sellers | 3,095 | 3,095 | 3,095 | 3,095 | 0 |
| product_category_name_translation | 70 | 71 | 71 | 71 | **+1** |

**Reviews, -5,495.** Customers' comments contain line breaks inside quoted fields. 3,852 `review_comment_message` values have at least one, and there are 5,495 in total, 22 of them in a single comment (appendix A1). That total is exactly the gap. The file uses Windows line endings (CRLF), inside comments too. Line-based tools (`wc -l`, `head -n`, `split -l`, a line-by-line reader) miscount the file or cut reviews in two. Only a quote-aware CSV parser returns 99,224 rows.

**Translation, +1.** `product_category_name_translation.csv` has no newline after its last row. `wc -l` reports 71 lines, which reads as 70 data rows after the header, but the file holds 71. The file also starts with a UTF-8 byte-order mark (`EF BB BF`). A reader that does not strip it keeps an invisible U+FEFF character at the start of the first column name, so any lookup by `product_category_name` fails. DuckDB's `read_csv(header = true)` strips it, and the column in `raw` is `product_category_name`. This file and the reviews file use CRLF line endings; the other seven use LF.

**Leading zeros.** Every column lands in `raw` as VARCHAR. One reason: 23,995 customer records (3,869 distinct prefixes) and 1,027 sellers have a zip prefix starting with 0, which a numeric type would drop (appendix A2).

**Verdict: OK.** All 9 tables reconcile. The two gaps come from the file format, not from lost or extra rows, and the traps are logged as DQ-18. Every build re-checks the load: `row_count_matches_load_audit` on all 9 sources, plus `accepted_values` on `load_audit.status`.

## 2. Primary-key uniqueness

**Checked.** Rows against distinct values of each table's obvious key. Where the obvious key fails, the alternatives tried are listed too.

**SQL:** [`02_primary_keys.sql`](../sql/data_quality/02_primary_keys.sql), result `primary_keys`.

| Table | Candidate key | Rows | Distinct | Extra rows | Verdict |
|---|---|---:|---:|---:|---|
| orders | `order_id` | 99,441 | 99,441 | 0 | OK |
| customers | `customer_id` | 99,441 | 99,441 | 0 | OK as a row key, but issued per order (DQ-01) |
| customers | `customer_unique_id` | 99,441 | 96,096 | 3,345 | The person, not a row key (DQ-01) |
| order_items | `order_id` + `order_item_id` | 112,650 | 112,650 | 0 | OK; one row per unit, no quantity column (DQ-04) |
| order_payments | `order_id` + `payment_sequential` | 103,886 | 103,886 | 0 | OK |
| order_reviews | `review_id` | 99,224 | 98,410 | 814 | Not unique (DQ-02) |
| order_reviews | `order_id` | 99,224 | 98,673 | 551 | Not unique (DQ-03) |
| order_reviews | `review_id` + `order_id` | 99,224 | 99,224 | 0 | OK: the real grain |
| products | `product_id` | 32,951 | 32,951 | 0 | OK |
| sellers | `seller_id` | 3,095 | 3,095 | 0 | OK |
| geolocation | zip code prefix | 1,000,163 | 19,015 | 981,148 | Not a key: many points per prefix |
| geolocation | all five columns | 1,000,163 | 738,332 | 261,831 | Exact duplicate rows (DQ-06) |
| product_category_name_translation | `product_category_name` | 71 | 71 | 0 | OK |

- **One person, several `customer_id`s.** 2,997 people have two or more, one per order. Counting customers on `customer_id` makes every customer a one-time buyer: 98,207 "customers" with net orders, none of them with a second order ([`03_customer_key_trap_on_raw.sql`](../sql/metrics/03_customer_key_trap_on_raw.sql)).
- **Reviews.** 789 `review_id`s appear on 1,603 rows: one survey answer is recorded against several orders of the same person. 547 orders have more than one review (543 with two, 4 with three; appendix A9), so a direct join of reviews to orders inflates order counts and GMV.
- **Geolocation.** 19,015 zip prefixes share 1,000,163 rows. A naive join on the prefix repeats each customer once for every point recorded for their prefix.

**Verdict: issue → DQ-01, DQ-02, DQ-03, DQ-06** (DQ-04 is a note on grain). The grain choices handle all of them ([ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md); geolocation in [ADR 0001](adr/0001-layered-architecture.md)):
- People are keyed on `customer_unique_id`.
- Reviews are staged at (`review_id`, `order_id`), then reduced to the latest answered review per order. `review_count` is kept.
- Geolocation is de-duplicated and reduced to one median point per prefix.

39 `unique` and 7 `unique_combination_of_columns` tests guard the keys. Two baselines watch the review duplicates: `known_issue__review_id_shared_across_orders` (789) and `known_issue__orders_with_multiple_reviews` (547).

## 3. Nulls

**Checked.** Exact null counts for every raw column that has at least one null (empty CSV fields load as NULL). The translation table is not covered by the file; it has no nulls. No key or foreign-key column has a null.

**SQL:** [`03_null_profile.sql`](../sql/data_quality/03_null_profile.sql), result `null_profile`.

| Table | Column | Nulls | % of rows | Verdict |
|---|---|---:|---:|---|
| order_reviews | `review_comment_title` | 87,656 | 88.34 | Expected: optional free text |
| order_reviews | `review_comment_message` | 58,247 | 58.70 | Expected: optional free text |
| orders | `order_delivered_customer_date` | 2,965 | 2.98 | Expected for orders not delivered; 8 delivered orders are DQ-14 |
| products | `product_category_name`, `product_name_lenght`, `product_description_lenght`, `product_photos_qty` | 610 each | 1.85 | DQ-07: the same 610 products in all four columns (A10) |
| orders | `order_delivered_carrier_date` | 1,783 | 1.79 | Expected for orders never handed over; 2 delivered orders, minor |
| orders | `order_approved_at` | 160 | 0.16 | Expected for orders never approved; 14 delivered orders are DQ-14 |
| products | `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` | 2 each | 0.01 | DQ-07: the same 2 products in all four columns (A10) |

An order timestamp should stay empty until the order reaches that step, so the three lifecycle columns were split by status (appendix A3):

| `order_status` | Orders | `order_approved_at` null | `order_delivered_carrier_date` null | `order_delivered_customer_date` null |
|---|---:|---:|---:|---:|
| delivered | 96,478 | **14** | **2** | **8** |
| shipped | 1,107 | 0 | 0 | 1,107 |
| canceled | 625 | 141 | 550 | 619 |
| unavailable | 609 | 0 | 609 | 609 |
| invoiced | 314 | 0 | 314 | 314 |
| processing | 301 | 0 | 301 | 301 |
| created | 5 | 5 | 5 | 5 |
| approved | 2 | 0 | 2 | 2 |
| **Total** | **99,441** | **160** | **1,783** | **2,965** |

Outside the `delivered` row every null is expected, because those orders never reached that step. In the `delivered` row the nulls are anomalies:
- 14 orders have no approval time and 8 have no delivery time. Both are DQ-14.
- 2 have no carrier pickup time. They are not registered as an issue: the only metric that needs that timestamp, `seller_scorecard.late_handover_rate`, leaves them out.

There is also the reverse case: 6 canceled orders do have a delivery time (DQ-14, check 8).

**Verdict: issue → DQ-07, DQ-14**; the rest is expected missingness. Products without a category get `product_category = 'unknown'` in `dim_products`. Delivery metrics use only delivered orders that have a delivery timestamp.

## 4. Value ranges and outliers

**Checked.** The distribution of each numeric column and the number of values that break a plausibility rule. The Brazil box is latitude -34.0 to 5.5 and longitude -74.5 to -28.5.

**SQL:** [`04_value_ranges_and_outliers.sql`](../sql/data_quality/04_value_ranges_and_outliers.sql), result `value_ranges`.

| Measure | Min | p01 | Median | p99 | Max | Flag rule | Flagged |
|---|---:|---:|---:|---:|---:|---|---:|
| `order_items.price` (BRL) | 0.85 | 9.99 | 74.99 | 890.00 | 6,735.00 | <= 0 | 0 |
| `order_items.freight_value` (BRL) | 0.00 | 4.42 | 16.26 | 84.52 | 409.68 | < 0 | 0 |
| `order_payments.payment_value` (BRL) | 0.00 | 6.69 | 100.00 | 1,039.92 | 13,664.08 | <= 0 | 9 |
| `order_payments.payment_installments` | 0 | 1 | 1 | 10 | 24 | < 1 | 2 |
| `order_reviews.review_score` | 1 | 1 | 5 | 5 | 5 | not 1-5 | 0 |
| `products.product_weight_g` | 0 | 60 | 700 | 22,538 | 40,425 | <= 0 | 4 |
| `products.product_length_cm` | 7 | 16 | 25 | 100 | 105 | <= 0 | 0 |
| `geolocation.latitude` | -36.61 | -30.10 | -22.92 | -2.50 | 45.07 | outside Brazil box | 31 |
| `geolocation.longitude` | -101.47 | -57.65 | -46.64 | -34.94 | 121.11 | outside Brazil box | 26 |

- **Pass:** prices, freight, review scores and product length. Zero freight is plausible (free shipping), so only negative freight is flagged. The tails are long: the largest item price is R$6,735.00 against a median of R$74.99, so averages should be read next to medians.
- **Payments (DQ-11, appendix A10):** the 9 zero-value payments are 6 vouchers and 3 rows of payment type `not_defined`. The 2 zero-installment rows are credit-card payments. None of them changes a total.
- **Weight (DQ-07):** 4 products weigh 0 g.
- **Coordinates (DQ-10, appendix A10):** 31 geolocation rows lie outside the Brazil box, 26 of them outside on both axes. They are excluded before the per-prefix median is taken.
- **Delivery time (DQ-13, appendix A4):** 43 delivered orders took more than 120 days from purchase to delivery, up to 210 days, against a median of 10. They are plausible, so they stay in.

**Verdict: issue → DQ-07, DQ-10, DQ-11, DQ-13**, all small.

## 5. Time ranges and monthly coverage

**Checked.** The first and last value of every timestamp column. Then placed and net orders per purchase month, for every month in the range, empty months included. The casts are strict, so the query itself shows that every non-empty value parses as a timestamp.

**SQL:** [`05_time_ranges_and_coverage.sql`](../sql/data_quality/05_time_ranges_and_coverage.sql), results `time_ranges` and `monthly_coverage`.

Result `time_ranges`:

| Column | First | Last | Nulls |
|---|---|---|---:|
| `orders.order_purchase_timestamp` | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 | 0 |
| `orders.order_approved_at` | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 | 160 |
| `orders.order_delivered_carrier_date` | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 | 1,783 |
| `orders.order_delivered_customer_date` | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 | 2,965 |
| `orders.order_estimated_delivery_date` | 2016-09-30 | 2018-11-12 | 0 |
| `order_items.shipping_limit_date` | 2016-09-19 00:15:34 | **2020-04-09 22:35:08** | 0 |
| `order_reviews.review_creation_date` | 2016-10-02 | 2018-08-31 | 0 |
| `order_reviews.review_answer_timestamp` | 2016-10-07 18:32:28 | 2018-10-29 12:27:35 | 0 |

Result `monthly_coverage`, shortened (the file lists all 26 months):

| Purchase month | Placed orders | Net orders | Fewer than 100 orders |
|---|---:|---:|---|
| 2016-09 | 4 | 2 | yes |
| 2016-10 | 324 | 293 | no |
| 2016-11 | 0 | 0 | yes |
| 2016-12 | 1 | 1 | yes |
| 2017-01 | 800 | 787 | no |
| 2017-02 to 2018-06 | 1,780 to 7,544 a month | 1,718 to 7,423 a month | no |
| 2018-07 | 6,292 | 6,233 | no |
| 2018-08 | 6,512 | 6,421 | no |
| 2018-09 | 16 | 1 | yes |
| 2018-10 | 4 | 0 | yes |

- **The end of the extract.** Purchases run to 2018-10-17, but the last approval is on 2018-09-03 and the last carrier pickup on 2018-09-11. Normal order flow stops at the start of September 2018: 19 of the 20 orders placed after August are canceled or unavailable.
- **The start.** 2016-10 has 324 orders, but the months around it hold 4, 0 and 1, so the continuous series starts in 2017-01.
- **Complete months** are therefore 2017-01 to 2018-08 (20 months, flagged by `dim_date.is_complete_data_month`). They hold 99,092 of the 99,441 placed orders; the other 349 fall in the six edge months.
- **Future dates.** Estimated delivery dates run to 2018-11-12, after the last purchase. That is expected for delivery promises made before the cut. Shipping deadlines, however, run into 2020: 8 item rows (7 orders) have a deadline more than 90 days after purchase, 4 of them in 2020 (DQ-12, appendix A11).
- **Semantics (DQ-21).** No column carries a time zone; values are read as local São Paulo time ([assumptions](assumptions.md)). Two names mislead, and both are renamed in staging: `review_creation_date` is the day the survey was sent (`review_survey_sent_date`), and `order_delivered_carrier_date` is the carrier pickup (`order_delivered_to_carrier_at`).

**Verdict: issue → DQ-12, DQ-19, DQ-21.** Trend charts and month-over-month comparisons use complete months only. `assert_complete_months_have_expected_volume` fails the build if a complete month ever has fewer than 500 net orders; the smallest, 2017-01, has 787.

## 6. Referential integrity

**Checked.** Three kinds of break:
- **Orphans:** child rows whose key has no parent.
- **Missing children:** parents without child rows.
- **Missing lookups:** codes absent from a reference table.

**SQL:** [`06_referential_integrity.sql`](../sql/data_quality/06_referential_integrity.sql), result `referential_integrity`.

| Type | Relationship | Unmatched | Verdict |
|---|---|---:|---|
| orphan | `order_items.order_id` → orders | 0 | OK |
| orphan | `order_items.product_id` → products | 0 | OK |
| orphan | `order_items.seller_id` → sellers | 0 | OK |
| orphan | `order_payments.order_id` → orders | 0 | OK |
| orphan | `order_reviews.order_id` → orders | 0 | OK |
| orphan | `orders.customer_id` → customers | 0 | OK |
| missing child | orders without items | 775 | DQ-08 |
| missing child | orders without payments | 1 | DQ-08 |
| missing child | orders without reviews | 768 | DQ-08 |
| missing child | customers without orders | 0 | OK |
| missing lookup | customer zip prefix → geolocation | 278 | DQ-09 |
| missing lookup | seller zip prefix → geolocation | 7 | DQ-09 |
| missing lookup | product category → translation (distinct categories) | 2 | DQ-20 |

- **775 orders without items (appendix A5):** 603 unavailable, 164 canceled and 8 net orders (5 created, 2 invoiced, 1 shipped). All 775 have payment records, R$162,591.95 in total. That is one reason why "sum of payments" overstates sales (section 9.4).
- **1 order without payments:** a delivered order with 3 item rows worth R$143.46 (`bfbd0f9bdef84302105ad712db648a6c`).
- **768 orders without reviews (appendix A6):** 646 delivered, 75 shipped and 47 in other statuses. Review rates therefore use reviewed orders as the denominator.
- **Missing lookups:** the 278 customer records cover 157 zip prefixes. Their coordinates stay null; state and region are always present. The 2 untranslated categories are `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos` (13 products).
- **Customers and orders are exactly 1:1:** `customer_id` is unique in both tables, no customer is without an order, and no order is without a customer. This is the root of DQ-01.

**Verdict: orphans OK; issue → DQ-08, DQ-09, DQ-20.**
- Children are aggregated to the order before they are left-joined. An order without children keeps amounts of 0 and a flag (`has_items`, `has_payment`, `has_review`).
- The seed `product_category_translation_overrides` adds the two missing translations.
- 19 `relationships` tests run in every build. The gaps have baselines: `assert_net_orders_have_items` (8), `known_issue__net_orders_without_payment` (1), `known_issue__customer_zip_prefix_missing_from_geolocation` (278) and `known_issue__seller_zip_prefix_missing_from_geolocation` (7). `assert_all_product_categories_translated` fails on any new untranslated category.

## 7. Payments vs items + freight

**Checked.** For every order that has both items and payments: the sum of payments against the sum of item prices plus freight. Amounts are cast to DECIMAL(10,2) before summing. With DOUBLE, rounding noise pushes some exact one-cent differences over the one-cent threshold: 380 orders instead of 303 (appendix A7).

**SQL:** [`07_payment_reconciliation.sql`](../sql/data_quality/07_payment_reconciliation.sql), results `summary` and `difference_buckets`.

Result `summary`, with the split at one cent from appendix A7:

| Measure | Value |
|---|---:|
| Orders with items and payments | 98,665 |
| Payments within R$0.01 of items + freight (`exact_match`) | 98,362 |
| of which equal to the cent / off by exactly one cent | 98,089 / 273 |
| Off by more than R$0.01 | 303 |
| Off by more than R$1 | 249 |
| Overpaid by more than R$1 (part of the 249) | 232 |
| Overpaid by more than R$1, credit card in installments (part of the 232) | 229 |
| Underpaid by more than R$1 (part of the 249) | 17 |
| Items + freight (BRL) | 15,843,409.78 |
| Payments (BRL) | 15,846,280.17 |
| Net difference (BRL) | +2,870.39 (0.02%) |

Result `difference_buckets` (payments minus items + freight):

| Difference | Orders |
|---|---:|
| Underpaid by more than R$10 | 7 |
| Underpaid by R$1 to R$10 | 10 |
| Within R$1 | 98,416 |
| Overpaid by R$1 to R$10 | 141 |
| Overpaid by R$10 to R$100 | 88 |
| Overpaid by more than R$100 | 3 |

The totals agree within 0.02%, but 249 individual orders do not. 229 of the 232 orders overpaid by more than R$1 were paid by credit card in installments. That is consistent with installment interest being included in the amount paid. The source has no interest field, so this is the likely explanation, not a confirmed one. The source offers no explanation for the 17 underpaid orders.

**Verdict: issue → DQ-16.** GMV (items + freight) is the revenue measure. Payments are kept separately as `payment_total_brl`, and `is_payment_mismatch` flags the 249 orders ([ADR 0004](adr/0004-payments-cancellations-and-refunds.md)). The baseline test `assert_payments_reconcile_with_order_gmv` passes at 249, warns above 249 and errors above 1,000. It stores the failing rows.

## 8. Lifecycle consistency

**Checked.** Timestamps that contradict the sequence purchase → approval → carrier pickup → delivery, and statuses that contradict the timestamps.

**SQL:** [`08_lifecycle_consistency.sql`](../sql/data_quality/08_lifecycle_consistency.sql), result `lifecycle_anomalies`.

| Check | Orders | Verdict |
|---|---:|---|
| Approved before purchase | 0 | OK |
| Delivered before purchase | 0 | OK |
| Estimated delivery before purchase | 0 | OK |
| Carrier pickup before approval | 1,359 | DQ-14 |
| Carrier pickup before purchase | 166 | DQ-14 |
| Delivered before carrier pickup | 23 | DQ-14 |
| Delivered before approval | 61 | DQ-14 |
| Status delivered, no delivery time | 8 | DQ-14 |
| Status delivered, no approval time | 14 | DQ-14 |
| Status canceled, has a delivery time | 6 | DQ-14 |
| Orders with at least one contradiction (rows overlap) | 1,410 | DQ-14 |

- **The hard rules hold.** No order was approved or delivered before it was bought, and no delivery estimate predates the purchase. All three are error-level dbt tests: `approved_not_before_purchase`, `delivered_not_before_purchase` and `estimate_not_before_purchase_date`.
- **Most carrier-pickup contradictions are small (appendix A8).** 901 of the 1,359 "carrier before approval" orders are within 24 hours (median gap 17.2 hours). For "carrier before purchase" it is 164 of 166 (median gap 0.6 hours). That looks more like timestamps recorded late or in batches than like real out-of-order events. The source cannot confirm it, so nothing is corrected.
- **Reviews (not in file 08).** 64 review rows have a survey date before their order's purchase date (DQ-15). The register's `count_sql` counts them, and `assert_reviews_not_sent_before_purchase` is their baseline.

**Verdict: issue → DQ-14, DQ-15.** The 1,410 orders stay in the marts, with their contradictions listed in `fct_orders.data_quality_flags`. Delivery metrics use only delivered orders with a delivery timestamp: 96,470 of the 96,478. Each contradiction type has its own baseline test at today's count, for example `known_issue__carrier_pickup_before_approval` at 1,359.

## 9. Checks on the marts after modelling

The raw checks decide what the models must handle. These checks show the models did it without losing, duplicating or redefining anything. Most of them are dbt tests that run in every build; the two exceptions, the Q0 analysis and the incremental script, are named where they appear. All of them passed in the last run.

### 9.1 Grain: one row per source record

| Mart | Rows | Must equal | dbt test |
|---|---:|---|---|
| `fct_orders` | 99,441 | rows in `stg_olist__orders` | `fct_orders_has_one_row_per_source_order` |
| `fct_order_items` | 112,650 | rows in `stg_olist__order_items` | `fct_order_items_has_one_row_per_source_item` |
| `dim_customers` | 96,096 | distinct `customer_unique_id` in `stg_olist__customers` | `dim_customers_has_one_row_per_person` |
| `customer_360` | 96,096 | rows in `dim_customers` | `customer_360_has_one_row_per_person` |
| `dim_products` | 32,951 | rows in `stg_olist__products` | `row_count_matches` |
| `dim_sellers` | 3,095 | rows in `stg_olist__sellers` | `row_count_matches` |
| `seller_scorecard` | 3,095 | rows in `dim_sellers` | `seller_scorecard_has_one_row_per_seller` |
| `dim_date` | 1,096 | one row per day, 2016-01-01 to 2018-12-31 | `is_continuous_date_spine` |

### 9.2 Placed, net and delivered orders

This is result `named_order_metrics` of [`q0_order_count_reconciliation.sql`](../analyses/q0_order_count_reconciliation.sql), split by status. The seed [`order_status_mapping.csv`](../dbt/seeds/order_status_mapping.csv) decides which statuses count ([ADR 0002](adr/0002-order-status-and-net-orders.md)).

| `order_status` | Orders | Placed | Net | Delivered |
|---|---:|:---:|:---:|:---:|
| delivered | 96,478 | yes | yes | yes |
| shipped | 1,107 | yes | yes (open) | no |
| invoiced | 314 | yes | yes (open) | no |
| processing | 301 | yes | yes (open) | no |
| created | 5 | yes | yes (open) | no |
| approved | 2 | yes | yes (open) | no |
| canceled | 625 | yes | no | no |
| unavailable | 609 | yes | no | no |
| **Orders** | | **99,441** | **98,207** | **96,478** |

Net orders include 1,729 open orders whose final outcome is not in the extract. Raw gives the same three numbers with the right filters ([`01_three_analysts_on_raw.sql`](../sql/metrics/01_three_analysts_on_raw.sql)). The fourth raw number, 117,601 rows from joining orders to items and payments, has no equivalent in the marts. Payments exist there only aggregated to the order, so nothing can fan out against them.

### 9.3 One net order count on every query path

This is result `query_paths` of the same file: the three analysts' questions, answered from the marts.

| Analyst | Query path | Net orders | Net GMV (BRL) |
|---|---|---:|---:|
| A (finance) | `fct_orders` where `is_net_order` | 98,207 | 15,735,527.03 |
| A (finance), item level | `fct_order_items` joined to `fct_orders`: distinct orders plus net orders without items | 98,207 | 15,735,527.03 |
| B (ops) | `fct_orders` × `dim_date`, summed by month | 98,207 | 15,735,527.03 |
| C (marketing) | sum of `dim_customers.frequency_orders` | 98,207 | 15,735,527.03 |
| C (marketing), CRM table | sum of `customer_360.frequency_orders` | 98,207 | 15,735,527.03 |

The dbt test [`assert_net_order_count_consistent_across_query_paths`](../dbt/tests/singular/assert_net_order_count_consistent_across_query_paths.sql) counts net orders six ways in every build:
1. `fct_orders` directly.
2. The star join `fct_orders` × `dim_customers` × `dim_date`.
3. Monthly counts through `dim_date`, summed.
4. `dim_customers.frequency_orders`, summed.
5. Distinct net orders in `fct_order_items`, plus net orders without items.
6. `stg_olist__orders` joined to the status seed, which bypasses every intermediate and mart model.

All six return 98,207, and the test fails if any two disagree.

### 9.4 GMV and payments reconcile

The raw totals from checks 6 and 7 carry into `fct_orders` exactly (appendix A12):

| Orders | Count | Items + freight (BRL) | Payments (BRL) |
|---|---:|---:|---:|
| With items and payments (check 7) | 98,665 | 15,843,409.78 | 15,846,280.17 |
| With items, no payment | 1 | 143.46 | 0.00 |
| With payments, no items | 775 | 0.00 | 162,591.95 |
| **All orders in `fct_orders`** | **99,441** | **15,843,553.24** | **16,008,872.12** |
| Net orders | 98,207 | 15,735,527.03 | 15,739,137.01 |
| Canceled or unavailable | 1,234 | 108,026.21 | 269,735.11 |

In the raw reconstruction of the dispute ([`01_three_analysts_on_raw.sql`](../sql/metrics/01_three_analysts_on_raw.sql)), analyst B's revenue is R$16,008,872.12. That figure is the sum of every payment, including R$269,735.11 paid on canceled and unavailable orders. The official revenue measure is net GMV: R$15,735,527.03.

| dbt test (`sum_matches`) | Compares | Total (BRL) | Tolerance |
|---|---|---:|---:|
| `item_gmv_reconciles_with_order_gmv` | `fct_order_items.item_total_brl` with `fct_orders.order_gmv_brl` | 15,843,553.24 | 0 |
| `item_net_gmv_reconciles_with_order_net_gmv` | the same, net orders only | 15,735,527.03 | 0 |
| `customer_gmv_reconciles_with_net_order_gmv` | `dim_customers.monetary_gmv_brl` with net `order_gmv_brl` | 15,735,527.03 | 0 |
| `seller_gmv_reconciles_with_net_order_gmv` | `seller_scorecard.gmv_brl` with net `order_gmv_brl` | 15,735,527.03 | 0 |
| `fct_orders_payments_reconcile_with_staging` | `fct_orders.payment_total_brl` with `stg_olist__order_payments.payment_value_brl` | 16,008,872.12 | R$0.01 |

`customer_360.monetary_gmv_brl` sums to the same R$15,735,527.03 (section 9.3). The payment total equals the raw file's, so aggregating payments to the order dropped nothing. `is_payment_mismatch` is true on exactly the 249 orders found in check 7: 247 net orders and 2 canceled or unavailable ones.

### 9.5 Other guards

| Check | Result | Where |
|---|---|---|
| Complete months have plausible volume | Smallest complete month: 787 net orders (2017-01); threshold 500 | `assert_complete_months_have_expected_volume` |
| Delivery metric base | 96,470 delivered orders with a delivery timestamp (96,478 minus 8) | `fct_orders.is_late_delivery` not null |
| Flag, don't drop | 2,428 orders carry at least one flag; all 99,441 stay in `fct_orders` | `fct_orders.data_quality_flags` |
| Incremental model equals a full refresh | First the extract as of 2018-07-01 (98,309 item rows), then the full extract. The incremental run, a rerun and a full refresh all give 112,650 rows with an identical checksum. Between the loads, 1,939 existing rows changed status; 1,344 of them were outside the 3-day lookback and were picked up by the open-order rule | [`check_incremental.py`](../scripts/check_incremental.py), [ADR 0005](adr/0005-incremental-fct-order-items.md) |
| Late arrivals are detected | 25 orders (26 item rows) held back from the first load are missed by the incremental run. The grain test fails as designed, and a full refresh repairs the table | same |
| Whole test suite | 300 of 300 pass: 296 data tests (24 of them known-issue baselines at today's counts) and 4 unit tests | last `dbt build`, 8.9 s |

Flag counts in `data_quality_flags` (an order can carry several; appendix A12):

| Flag | Orders |
|---|---:|
| `carrier_before_approval` | 1,359 |
| `no_items` | 775 |
| `payment_mismatch` | 249 |
| `carrier_before_purchase` | 166 |
| `delivered_before_approval` | 61 |
| `delivered_before_carrier` | 23 |
| `delivered_without_approval` | 14 |
| `delivered_without_timestamp` | 8 |
| `canceled_with_delivery` | 6 |
| `no_payment` | 1 |

## How the checks stay enforced

- **The SQL files are for investigation; dbt tests enforce the rules.** Hard rules fail the build: keys, relationships, accepted values, and nothing delivered before it was bought. Known source issues are baselines. They pass at today's count, warn if it grows and error if it explodes, and they store the failing rows in the `test_failures` schema.
- **The baselines are proven able to fire.** CI builds on a synthetic fixture ([`make_fixture.py`](../ci/make_fixture.py)) that plants every known issue. [`check_known_issues_detected.py`](../ci/check_known_issues_detected.py) then fails unless each known-issue test detected its planted rows. So a baseline that passes on real data has also been seen to catch its issue.
- **The published counts stay current.** `make cache` re-runs the eight files and the register's `count_sql` queries, so the app and the HTML report show the counts of the latest load.

## Limits

- **Internal consistency only.** These checks cover the path from file to `raw` to marts. No system of record (finance ledger, payment settlement) is in scope, so agreement with Finance's books is not tested. Finance signs off the definition of net orders, not a reconciliation to its ledger.
- **Time zone.** America/Sao_Paulo is an assumption. The data is consistent with it (no timestamp falls in the hour skipped when daylight saving time began in 2016 and 2017), but Olist documents no time zone ([assumptions](assumptions.md) A-01, DQ-21).
- **New kinds of issue.** Baselines catch growth in known issues, not new kinds of issue. A new extract should be re-profiled with these eight files before it replaces the current one.
- **Unconfirmed explanations.** Two explanations above are likely but not confirmed: overpayments as installment interest (check 7), and small lifecycle gaps as recording delays (check 8).
- **Not covered here.** Two register entries are outside these checks: DQ-05 (one checkout split into several orders in the same second) and DQ-17 (free-text seller city names). Their counts come from the register's `count_sql`; see the [data quality report](data_quality_report.md).

## Appendix: follow-up queries

These are the breakdowns used above that are not in the eight files. A1 to A11 run against `raw` and A12 against `marts`, in any DuckDB client.

```sql
-- A1 (check 1): line breaks inside review comments
select
    count(*) filter (where regexp_matches(coalesce(review_comment_message, ''), '[\r\n]')) as comments_with_breaks,
    sum(length(coalesce(review_comment_message, '')) - length(replace(coalesce(review_comment_message, ''), chr(10), ''))) as line_breaks,
    max(length(coalesce(review_comment_message, '')) - length(replace(coalesce(review_comment_message, ''), chr(10), ''))) as most_in_one_comment
from raw.order_reviews;

-- A2 (check 1): zip prefixes with a leading zero
select
    count(*) filter (where customer_zip_code_prefix like '0%') as customer_records,
    count(distinct customer_zip_code_prefix) filter (where customer_zip_code_prefix like '0%') as customer_prefixes,
    (select count(*) from raw.sellers where seller_zip_code_prefix like '0%') as sellers
from raw.customers;

-- A3 (check 3): lifecycle nulls by status
select
    order_status,
    count(*) as orders,
    count(*) - count(order_approved_at) as approved_null,
    count(*) - count(order_delivered_carrier_date) as carrier_null,
    count(*) - count(order_delivered_customer_date) as delivered_null
from raw.orders
group by order_status
order by orders desc;

-- A4 (check 4): delivery durations of delivered orders, in days
select
    count(*) filter (where days > 120) as over_120_days,
    max(days) as max_days,
    median(days) as median_days
from (
    select date_diff('day', order_purchase_timestamp::date, order_delivered_customer_date::date) as days
    from raw.orders
    where order_status = 'delivered' and order_delivered_customer_date is not null
);

-- A5 (check 6): orders without items, by status, and what was paid on them
select o.order_status, count(*) as orders, count(p.order_id) as with_payment, sum(p.paid) as paid_brl
from raw.orders as o
left join (
    select order_id, sum(payment_value::decimal(10, 2)) as paid from raw.order_payments group by order_id
) as p on o.order_id = p.order_id
where o.order_id not in (select order_id from raw.order_items)
group by o.order_status
order by orders desc;

-- A6 (check 6): orders without reviews, by status
select order_status, count(*) as orders
from raw.orders
where order_id not in (select order_id from raw.order_reviews)
group by order_status
order by orders desc;

-- A7 (check 7): payment differences at one-cent resolution, and the same count with DOUBLE
with

items as (
    select
        order_id,
        sum(price::decimal(10, 2) + freight_value::decimal(10, 2)) as items_and_freight,
        sum(price::double + freight_value::double) as items_and_freight_double
    from raw.order_items group by order_id
),

payments as (
    select order_id, sum(payment_value::decimal(10, 2)) as paid, sum(payment_value::double) as paid_double
    from raw.order_payments group by order_id
)

select
    count(*) filter (where paid = items_and_freight) as equal_to_the_cent,
    count(*) filter (where abs(paid - items_and_freight) = 0.01) as off_by_one_cent,
    count(*) filter (where abs(paid - items_and_freight) > 0.01) as off_by_more,
    count(*) filter (where abs(paid_double - items_and_freight_double) > 0.01) as off_by_more_with_double
from items
inner join payments on items.order_id = payments.order_id;

-- A8 (check 8): size of the carrier-pickup contradictions, in hours
select
    anomaly,
    count(*) as orders,
    count(*) filter (where gap_hours < 24) as within_24_hours,
    round(median(gap_hours), 1) as median_gap_hours
from (
    select 'carrier pickup before approval' as anomaly,
        date_diff('minute', order_delivered_carrier_date::timestamp, order_approved_at::timestamp) / 60.0 as gap_hours
    from raw.orders
    where order_delivered_carrier_date::timestamp < order_approved_at::timestamp
    union all
    select 'carrier pickup before purchase',
        date_diff('minute', order_delivered_carrier_date::timestamp, order_purchase_timestamp::timestamp) / 60.0
    from raw.orders
    where order_delivered_carrier_date::timestamp < order_purchase_timestamp::timestamp
)
group by anomaly
order by orders desc;

-- A9 (check 2): rows behind the shared review_ids, and orders by number of reviews
select
    (select count(*) from (select review_id from raw.order_reviews group by review_id having count(*) > 1)) as shared_review_ids,
    (select sum(n) from (select count(*) as n from raw.order_reviews group by review_id having count(*) > 1)) as their_rows,
    (select count(*) from (select order_id from raw.order_reviews group by order_id having count(*) = 2)) as orders_with_2_reviews,
    (select count(*) from (select order_id from raw.order_reviews group by order_id having count(*) = 3)) as orders_with_3_reviews;

-- A10 (checks 3 and 4): overlap of the product nulls; zero payments and outlying points by kind
select 'products without category, name, description and photos' as finding, count(*) as n
from raw.products
where product_category_name is null and product_name_lenght is null
    and product_description_lenght is null and product_photos_qty is null
union all
select 'products without weight and all dimensions', count(*)
from raw.products
where product_weight_g is null and product_length_cm is null
    and product_height_cm is null and product_width_cm is null
union all
select 'zero-value payments: ' || payment_type, count(*)
from raw.order_payments where payment_value::decimal(10, 2) = 0 group by payment_type
union all
select 'zero-installment payments: ' || payment_type, count(*)
from raw.order_payments where payment_installments::int = 0 group by payment_type
union all
select 'geolocation rows outside the Brazil box on both axes', count(*)
from raw.geolocation
where not (geolocation_lat::double between -34.0 and 5.5)
    and not (geolocation_lng::double between -74.5 and -28.5)
order by finding;

-- A11 (check 5): shipping deadlines more than 90 days after purchase
select
    count(*) as item_rows,
    count(distinct order_id) as orders,
    count(*) filter (where year(shipping_limit_date::timestamp) = 2020) as deadline_in_2020
from raw.order_items
inner join raw.orders using (order_id)
where shipping_limit_date::timestamp > order_purchase_timestamp::timestamp + interval 90 day;

-- A12 (checks 9.4 and 9.5): the GMV bridge, the net split and the flag counts in the marts
select
    case
        when has_items and has_payment then 'with items and payments'
        when has_items then 'with items, no payment'
        else 'with payments, no items'
    end as orders,
    count(*) as order_count,
    sum(order_gmv_brl) as gmv_brl,
    sum(payment_total_brl) as paid_brl
from marts.fct_orders
group by orders
order by orders;

select
    is_net_order,
    count(*) as order_count,
    sum(order_gmv_brl) as gmv_brl,
    sum(payment_total_brl) as paid_brl,
    count(*) filter (where is_payment_mismatch) as payment_mismatches
from marts.fct_orders
group by is_net_order
order by is_net_order desc;

select flag, count(*) as orders
from (select unnest(string_split(data_quality_flags, ',')) as flag from marts.fct_orders)
group by flag
order by orders desc;
```
