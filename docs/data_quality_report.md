# Data quality report

**Owner:** Analytics Engineering · **For:** Analytics Lead (decision maker) and the Olist platform team (source owner) · **Also for:** analysts, Finance
**Data:** Olist marketplace extract, 9 CSV files, orders purchased 2016-09-04 to 2018-10-17 · **Checked on:** the 2026-11-03 build, 300 of 300 tests passing

Every issue has a stable ID (DQ-01 to DQ-21) from the register, [`sql/data_quality/issue_register.yml`](../sql/data_quality/issue_register.yml). The 24 baseline tests, and the coverage and translation tests of DQ-19 and DQ-20, carry the same ID in `meta.dq_issue`.

## 1. Executive summary

**What we found.** Profiling the 9 raw tables found 21 issues in 9 classes. None of them is blocking: none prevents a correct count of net orders or net GMV. Each issue is corrected in the model (wrong keys and grain, duplicates, misleading column names, missing translations), kept as the source recorded it and watched by a test, with a flag on the row where analysts need one, or, for the time zone, documented as an assumption.

**What it means for trust in the marts.** The three conflicting order counts came from joins at the wrong grain and from three definitions sharing one name, not from bad source data. One analyst's join of orders, items and payments returned 117,601 rows for 99,441 orders ([01_request_and_scope.md](01_request_and_scope.md)). In the marts:

- No order, item, payment, customer, product or seller record is dropped for quality reasons. `fct_orders` holds all 99,441 orders. The 2,428 orders (2.4%) with a lifecycle contradiction, missing items or payment, or a payment mismatch carry a code in `data_quality_flags`.
- Every documented query path returns the same 98,207 net orders. `assert_net_order_count_consistent_across_query_paths` fails the build if two paths ever disagree.
- 24 of the 296 data tests are known-issue baselines. They pass at today's counts and warn as soon as a source issue grows.

**What the business must know.**

- **Net orders include 1,729 open orders** (shipped, invoiced, processing, created, approved): 1.8% of net orders and 2.0% of net GMV. Their final outcome is not in the data. 1,544 of them were placed more than 90 days before the extract's last net order (2018-09-03), well past the median delivery time of 10 days. `is_terminal_status` separates them.
- **Net GMV is bookings, not cash.** On orders that have both items and payments, payments exceed items + freight by R$2,870 (0.02%). 229 of the 232 orders overpaid by more than R$1 are card payments in installments, so we read the gap as interest, which the source does not record separately (DQ-16). R$269,735 was paid on the 1,234 canceled and unavailable orders. The source has no refund table, so we cannot tell how much of it was returned ([ADR 0004](adr/0004-payments-cancellations-and-refunds.md)).
- **Trends use complete months only, 2017-01 to 2018-08** (DQ-19).
- **A customer is a person (`customer_unique_id`), and the repeat rate depends on the definition.** It is 2.17% on 2+ purchase days (official) and 3.04% on 2+ net orders. The difference is people whose orders all fall on one day: some checkouts were split into several orders in the same second (290 times), and some people ordered again later that day (DQ-01, DQ-05).
- **Two inputs are assumptions, not data.** Timestamps are read as São Paulo local time because no time zone is recorded (DQ-21). An order reviewed twice keeps its latest answer (DQ-03).

The asks for the source owner are in [section 6](#6-asks-for-the-source-owner-olist-platform-team). The three with the most business impact are a refund feed, a recorded time zone and an order status history.

## 2. Issue register

The table below is generated from the register by [`scripts/render_docs_tables.py`](../scripts/render_docs_tables.py), so do not edit it by hand. Every `make cache` re-counts `affected` on `raw`, in the unit shown. Some baseline tests count at a different grain (for example, distinct points after de-duplication), so section 4 lists each test's own [baseline](#baseline-thresholds). The same register feeds the app's Raw Data Issues page and `reports/report.html`.

<!-- BEGIN issue_register -->
| ID | class | table | issue | affected | how it is handled | guarded by |
|---|---|---|---|---:|---|---|
| DQ-01 | Keys, identity & grain | `customers` | customer_id is issued per order, not per person | 2,997 people with 2+ customer_ids | dim_customers and customer_360 are keyed on customer_unique_id; the facts carry customer_unique_id, and the per-order customer_id is not exposed in the marts. | `dim_customers_has_one_row_per_person`, `unique_dim_customers_customer_unique_id` |
| DQ-02 | Keys, identity & grain | `order_reviews` | review_id is not unique | 789 review_ids used on 2+ orders | Staging grain is (review_id, order_id) with a surrogate key; reviews are attached per order. | `known_issue__review_id_shared_across_orders` |
| DQ-03 | Keys, identity & grain | `order_reviews` | Some orders were reviewed 2-3 times | 547 orders with 2+ reviews | int_reviews_deduplicated_to_orders keeps the most recently answered review and stores review_count. | `known_issue__orders_with_multiple_reviews`, `unique_int_reviews_deduplicated_to_orders_order_id` |
| DQ-04 | Keys, identity & grain | `order_items` | No quantity column; one row per unit | 6,968 orders with the same product on 2+ rows | fct_order_items keeps one row per unit; quantity = count of rows. | `dbt_utils_unique_combination_of_columns_fct_order_items_order_id__order_item_id` |
| DQ-05 | Keys, identity & grain | `orders` | One checkout can be split into several orders in the same second | 290 same-second order groups | Repeat status uses distinct purchase days (dim_customers.purchase_days >= 2). | documented |
| DQ-06 | Duplicates | `geolocation` | Geolocation repeats the same point many times | 261,831 exact duplicate rows | Staging de-duplicates; int_geolocation_aggregated_to_zip_prefixes keeps one median point per prefix. | `unique_stg_olist__geolocation_geolocation_key`, `unique_int_geolocation_aggregated_to_zip_prefixes_zip_code_prefix` |
| DQ-07 | Missing values & missing records | `products` | Products without category or attributes | 610 products without category | dim_products.product_category = 'unknown'; has_complete_attributes flags the rest. | `known_issue__products_missing_category`, `known_issue__products_missing_weight`, `known_issue__products_with_zero_weight` |
| DQ-08 | Missing values & missing records | `orders` | Orders without items, payment or review | 775 orders without items | Children are left-joined after aggregation; amounts are 0 and has_items / has_payment / has_review flag the gaps. | `assert_net_orders_have_items`, `known_issue__net_orders_without_payment` |
| DQ-09 | Missing values & missing records | `geolocation` | Customer and seller zip prefixes missing from geolocation | 285 customers + sellers without coordinates | Coordinates are left null; state and region come from the customer / seller record and are always present. | `known_issue__customer_zip_prefix_missing_from_geolocation`, `known_issue__seller_zip_prefix_missing_from_geolocation` |
| DQ-10 | Invalid or out-of-range values | `geolocation` | Coordinates outside Brazil | 31 rows outside the Brazil bounding box | Excluded before the per-prefix median (is_within_brazil). | `known_issue__geolocation_points_outside_brazil` |
| DQ-11 | Invalid or out-of-range values | `order_payments` | Undefined payment type and zero installments | 5 payment rows | Kept as recorded (they do not change totals); baseline tests alert if they grow. | `known_issue__payment_type_not_defined`, `known_issue__payment_with_zero_installments` |
| DQ-12 | Invalid or out-of-range values | `order_items` | Shipping deadlines months or years after purchase | 8 item rows with a deadline > 90 days after purchase | Kept; they can only make those items look "on time" in the seller handover SLA. | `assert_shipping_limit_within_90_days_of_purchase` |
| DQ-13 | Invalid or out-of-range values | `orders` | Extreme delivery durations | 43 delivered orders taking > 120 days | Kept; they are real outcomes. | `known_issue__deliveries_over_120_days` |
| DQ-14 | Contradictory timestamps | `orders` | Order lifecycle timestamps out of order | 1,410 orders with 1+ contradiction | Flagged in fct_orders.data_quality_flags, never dropped. Delivery metrics exist only for delivered orders with a delivery timestamp. | `known_issue__carrier_pickup_before_approval`, `known_issue__carrier_pickup_before_purchase`, `known_issue__delivered_before_carrier_pickup`, `known_issue__delivered_before_approval`, `known_issue__delivered_orders_missing_approval`, `known_issue__delivered_orders_missing_delivery_timestamp`, `known_issue__canceled_orders_with_delivery_timestamp` |
| DQ-15 | Contradictory timestamps | `order_reviews` | Satisfaction surveys dated before the purchase | 64 review rows | Kept (the score is still the customer's answer); monitored. | `assert_reviews_not_sent_before_purchase` |
| DQ-16 | Cross-table reconciliation | `order_payments` | Payments do not equal items + freight | 249 orders off by more than R$1 | GMV (items + freight) is the revenue measure; payments are kept separately (payment_total_brl, payment_gmv_difference_brl, is_payment_mismatch). See ADR 0004. | `assert_payments_reconcile_with_order_gmv`, `fct_orders_payments_reconcile_with_staging` |
| DQ-17 | Text, encoding & format | `sellers` | Free-text city names | 33 seller city values needing cleaning | Macro clean_city_name (lower-case, strip accents and suffixes, null when unusable); the 7 unusable seller cities are inferred from the zip prefix (dim_sellers.is_city_inferred_from_zip). | `known_issue__seller_city_unusable`, `test_seller_city_cleaning` |
| DQ-18 | Text, encoding & format | `(files)` | File-format traps | 3,852 review rows with line breaks in the text | CSV parsing with a real parser, every raw column as VARCHAR, a load audit of physical vs parsed rows, and renamed columns in staging. | `row_count_matches_load_audit (9 sources)`, `customer_zip_prefix_is_five_digits` |
| DQ-19 | Coverage & reference data | `orders` | Incomplete months at both ends of the extract | 5 months with < 100 orders | dim_date.is_complete_data_month; a test fails if a complete month ever has < 500 net orders. | `assert_complete_months_have_expected_volume` |
| DQ-20 | Coverage & reference data | `product_category_name_translation` | Categories missing from the translation table | 2 untranslated categories | Seed product_category_translation_overrides; a test fails on any new untranslated category. | `assert_all_product_categories_translated` |
| DQ-21 | Undocumented semantics | `(all)` | Timestamps without time zone; misleading column names | 9 timestamp / date columns affected | Documented assumption (America/Sao_Paulo); fct_orders adds order_purchased_at_utc. Columns renamed in staging (review_survey_sent_date, order_delivered_to_carrier_at). | documented |
<!-- END issue_register -->

## 3. Issues by class

Each issue below covers what was found and how big it is, what goes wrong if it is ignored, how the models handle it, and the tests that guard it. "Baseline" marks a known-issue test; "hard rule" marks a test that errors on its first failing row (see section 4).

### A. Keys, identity & grain (DQ-01 to DQ-05)

#### DQ-01 `customer_id` is issued per order, not per person

- **Found:** 99,441 `customer_id`s, one per order, belong to 96,096 people (`customer_unique_id`). 2,997 people have two or more.
- **If ignored:** nobody ever buys twice. Counted on `customer_id`, the 98,207 net orders come from 98,207 "customers" and the repeat rate is 0%. Counted on people, there are 94,990 customers, and 2,888 of them have 2+ net orders.
- **Handling:** `dim_customers` and `customer_360` have one row per `customer_unique_id`, which both facts carry as the foreign key. The source `customer_id` is not exposed in any mart ([ADR 0003](adr/0003-grain-fan-out-and-customer-identity.md)).
- **Tests:** `dim_customers_has_one_row_per_person` and `unique_dim_customers_customer_unique_id` (hard rules).

#### DQ-02 `review_id` is not unique

- **Found:** 789 `review_id`s appear on 1,603 rows. In every case, one survey answer was recorded against several orders of the same person. `(review_id, order_id)` is unique.
- **If ignored:** de-duplicating on `review_id` drops 814 valid order-review pairs, and joining on it fans out.
- **Handling:** the staging grain is `(review_id, order_id)` with the surrogate key `order_review_key`. Reviews are attached per order and never counted by `review_id`.
- **Tests:** `known_issue__review_id_shared_across_orders` (baseline). `dbt_utils_unique_combination_of_columns_stg_olist__order_reviews_review_id__order_id` and `unique_stg_olist__order_reviews_order_review_key` (hard rules).

#### DQ-03 Some orders were reviewed 2-3 times

- **Found:** 547 orders have 2 or 3 survey answers, and 202 of them disagree on the score.
- **If ignored:** joining reviews straight to orders turns 99,441 orders into 99,992 rows. Those orders are counted two or three times in order counts and GMV, and their scores get extra weight in averages.
- **Handling:** `int_reviews_deduplicated_to_orders` keeps the most recently answered review (ties broken by survey date, then `review_id`) and stores `review_count`. In `fct_orders`, `review_count > 1` marks the 547 orders. Keeping the latest answer is a choice: the source does not say which answer is authoritative.
- **Tests:** `known_issue__orders_with_multiple_reviews` (baseline), `unique_int_reviews_deduplicated_to_orders_order_id` (hard rule) and the unit test `test_review_dedup_keeps_latest_answer`.

#### DQ-04 No quantity column; one row per unit

- **Found:** buying three units of a product creates three rows (`order_item_id` 1 to 3). 7,088 order-product pairs, in 6,968 orders, have the same product on more than one row.
- **If ignored:** `count(*)` on items counts units, not orders or order lines: there are 112,650 item rows but only 98,666 orders with items.
- **Handling:** `fct_order_items` keeps one row per unit, so quantity is a count of rows. Orders are counted with `count(distinct order_id)`.
- **Tests:** `dbt_utils_unique_combination_of_columns_fct_order_items_order_id__order_item_id`, `fct_order_items_has_one_row_per_source_item` and `item_gmv_reconciles_with_order_gmv`, which checks that item GMV adds up exactly to order GMV (all hard rules).

#### DQ-05 One checkout can be split into several orders in the same second

- **Found:** 290 times, a person placed 2 or more orders in the same second (582 orders). In 167 of these groups no two orders share a seller, which suggests a basket split by seller.
- **If ignored:** counted on orders, the repeat-purchase rate reads 3.04%. Counting distinct checkout timestamps removes the split checkouts and gives 2.78%. The official definition, distinct purchase days, also leaves out second checkouts on the same day and gives 2.17%.
- **Handling:** repeat status uses distinct purchase days. `dim_customers.is_repeat_customer` is true when `purchase_days >= 2`.
- **Tests:** none, because this is a definition. It is documented in [02_metric_definitions.md](02_metric_definitions.md), and [`analyses/q2_repeat_purchase.sql`](../analyses/q2_repeat_purchase.sql) shows how the rate moves under each definition.

### B. Duplicates (DQ-06)

#### DQ-06 Geolocation repeats the same point many times

- **Found:** 1,000,163 rows for 19,015 zip prefixes. 261,831 rows are exact duplicates, leaving 738,332 distinct rows.
- **If ignored:** joining customers to the raw file on zip prefix returns 15.1 million rows for 99,441 customer records, about 152 per record.
- **Handling:** `stg_olist__geolocation` de-duplicates after cleaning city names (720,495 rows). `int_geolocation_aggregated_to_zip_prefixes` then keeps one median point per prefix, using in-Brazil points only. Analysts get coordinates on `dim_customers` and `dim_sellers` and never join geolocation themselves.
- **Tests:** `unique_stg_olist__geolocation_geolocation_key` and `unique_int_geolocation_aggregated_to_zip_prefixes_zip_code_prefix` (hard rules).

### C. Missing values & missing records (DQ-07 to DQ-09)

#### DQ-07 Products without category or attributes

- **Found:** 610 products have no category, name length, description length or photo count. They appear on 1,603 item rows in 1,451 orders. 2 products have no weight or dimensions (one of them is also among the 610), and 4 have weight 0.
- **If ignored:** a category report that drops null categories silently loses R$206,524 of net GMV (1.3%).
- **Handling:** `dim_products.product_category` is `unknown` for the 610. `has_complete_attributes` is false when the category, a positive weight or any dimension is missing.
- **Tests:** `known_issue__products_missing_category`, `known_issue__products_missing_weight` and `known_issue__products_with_zero_weight` (baselines).

#### DQ-08 Orders without items, payment or review

- **Found:**
  - 775 orders have no items: 603 unavailable, 164 canceled and 8 in a net-order status (5 created, 2 invoiced, 1 shipped). All 775 still have a payment record, R$162,592 in total.
  - 1 delivered order has no payment (purchased 2016-09-15, 3 items, R$143.46).
  - 768 orders have no review.
- **If ignored:** inner joins drop orders. A net-order count taken from items comes out 8 short (98,199), and one taken from payments comes out 1 short. A bad-review rate over all orders, instead of reviewed orders, counts 768 unanswered surveys as "not bad".
- **Handling:** children are aggregated to order grain and then left-joined, so missing amounts become 0. `has_items`, `has_payment` and `has_review` flag the gaps, and `no_items` / `no_payment` also appear in `data_quality_flags`. The 8 net orders without items stay in the net-order count with GMV 0 ([ADR 0002](adr/0002-order-status-and-net-orders.md)).
- **Tests:** `assert_net_orders_have_items` and `known_issue__net_orders_without_payment` (baselines, on the net-order part). On its item path, `assert_net_order_count_consistent_across_query_paths` adds the 8 net orders without items back and requires the total to match, which shows that no other net order is missing from `fct_order_items`.

#### DQ-09 Customer and seller zip prefixes missing from geolocation

- **Found:** 278 customer records (157 zip prefixes) and 7 sellers have a zip prefix that is not in the geolocation file. One more customer prefix has only points outside Brazil.
- **If ignored:** an inner join to coordinates silently drops these customers and sellers from maps and distance calculations.
- **Handling:** coordinates are left null. State and region come from the customer or seller record and are always present. In the marts, 269 of 96,096 people (0.3%) and 7 of 3,095 sellers have no coordinates.
- **Tests:** `known_issue__customer_zip_prefix_missing_from_geolocation` and `known_issue__seller_zip_prefix_missing_from_geolocation` (baselines).

### D. Invalid or out-of-range values (DQ-10 to DQ-13)

#### DQ-10 Coordinates outside Brazil

- **Found:** 31 raw rows (27 distinct points after de-duplication) fall outside a bounding box around Brazil. 19 are in Portugal or Spain; the rest are in Argentina, Mexico and the US, Italy and the Philippines. Latitude reaches 45.07 and longitude 121.1, yet every row carries a Brazilian state code.
- **If ignored:** maps and distances place customers abroad. Four prefixes have no point inside Brazil (one of them is used by a customer), so they would be located in another country.
- **Handling:** `stg_olist__geolocation.is_within_brazil` flags these points, and they are excluded before the per-prefix median. None reaches `dim_customers` or `dim_sellers`.
- **Tests:** `known_issue__geolocation_points_outside_brazil` (baseline). It counts distinct staging points, which is why its baseline is 27 rather than 31.

#### DQ-11 Undefined payment type and zero installments

- **Found:** 3 payment rows have `payment_type = 'not_defined'` with value 0, and 2 credit-card rows have 0 installments. There are also 6 zero-value voucher rows and 80 orders with gaps in `payment_sequential`.
- **If ignored:** payment-mix charts show a meaningless `not_defined` slice (3 orders have it as `primary_payment_type`), and installment averages include impossible zeros. Totals are not affected.
- **Handling:** kept as recorded. `not_defined` is an accepted value of `payment_type` and `primary_payment_type`.
- **Tests:** `known_issue__payment_type_not_defined` and `known_issue__payment_with_zero_installments` (baselines).

#### DQ-12 Shipping deadlines months or years after purchase

- **Found:** the seller's shipping deadline is normally about a week after purchase (median 6 days, 99th percentile 19). 8 items in 7 orders have a deadline more than 90 days after purchase, and 4 of those deadlines fall in 2020.
- **If ignored:** these items can only look "on time" in the seller handover SLA (`seller_scorecard.late_handover_rate`). At 8 items the effect is negligible.
- **Handling:** kept.
- **Tests:** `assert_shipping_limit_within_90_days_of_purchase` (baseline).

#### DQ-13 Extreme delivery durations

- **Found:** 43 delivered orders took more than 120 days from purchase to delivery (maximum 210). Plausible, but extreme.
- **If ignored:** the long tail pulls averages up. The median delivery time is 10 days and the mean is 12.5.
- **Handling:** kept, because they are real outcomes.
- **Tests:** `known_issue__deliveries_over_120_days` on `fct_orders.delivery_days` (baseline).

### E. Contradictory timestamps (DQ-14, DQ-15)

#### DQ-14 Order lifecycle timestamps out of order

- **Found:** 1,410 orders have at least one contradiction:

| Contradiction | Orders | Code in `data_quality_flags` | Baseline test |
|---|---:|---|---|
| Handed to the carrier before payment approval | 1,359 | `carrier_before_approval` | `known_issue__carrier_pickup_before_approval` |
| ...of which before the purchase itself | 166 | `carrier_before_purchase` | `known_issue__carrier_pickup_before_purchase` |
| Delivered before carrier pickup | 23 | `delivered_before_carrier` | `known_issue__delivered_before_carrier_pickup` |
| Delivered before payment approval | 61 | `delivered_before_approval` | `known_issue__delivered_before_approval` |
| Status `delivered`, no approval time | 14 | `delivered_without_approval` | `known_issue__delivered_orders_missing_approval` |
| Status `delivered`, no delivery time | 8 | `delivered_without_timestamp` | `known_issue__delivered_orders_missing_delivery_timestamp` |
| Status `canceled`, but has a delivery time | 6 | `canceled_with_delivery` | `known_issue__canceled_orders_with_delivery_timestamp` |

- **If ignored:** approval and carrier-handover durations go negative, delivered orders without a delivery time break delivery metrics, and 6 canceled orders look delivered.
- **Handling:** the anomalies are flagged in `fct_orders.data_quality_flags` (and `has_lifecycle_anomaly`), and no order is dropped. Status wins over timestamps, so the 6 canceled orders stay canceled. Delivery metrics exist only for delivered orders with a delivery timestamp: 96,470 of 96,478.
- **Tests:** the seven baselines in the table. The orderings that do hold in the source are hard rules: `approved_not_before_purchase`, `delivered_not_before_purchase` and `estimate_not_before_purchase_date`. The unit test `test_late_delivery_and_status_logic` checks two of the flag codes (`carrier_before_approval`, `canceled_with_delivery`) along with the late-delivery rule.

#### DQ-15 Satisfaction surveys dated before the purchase

- **Found:** 64 review rows have a survey-sent date (source column `review_creation_date`) earlier than the purchase date.
- **If ignored:** the time from purchase to survey comes out negative for these orders.
- **Handling:** kept, because the score is still the customer's answer.
- **Tests:** `assert_reviews_not_sent_before_purchase` (baseline) and `review_answered_not_before_survey_sent` (hard rule).

### F. Cross-table reconciliation (DQ-16)

#### DQ-16 Payments do not equal items + freight

- **Found:** of the 98,665 orders with both items and payments:
  - 303 differ by more than 1 cent, and 249 by more than R$1.
  - 232 are overpaid by more than R$1. 229 of those are card payments in installments. We read the gap as installment interest, which the source does not record separately.
  - 17 are underpaid by more than R$1.
  - Net effect: payments exceed items + freight by R$2,870.39 on R$15,843,409.78 (0.02%).
- **If ignored:** revenue built from payments and revenue built from items never tie out. Using payments as revenue also books card interest, and the payments on canceled orders, as sales.
- **Handling:** GMV (items + freight, `order_gmv_brl`) is the revenue measure. Payments are kept separately and unadjusted in `payment_total_brl`, `payment_gmv_difference_brl` and `is_payment_mismatch`. The tolerance is the var `payment_mismatch_tolerance_brl`, default R$1.00 ([ADR 0004](adr/0004-payments-cancellations-and-refunds.md)).
- **Tests:** `assert_payments_reconcile_with_order_gmv` (baseline). `fct_orders_payments_reconcile_with_staging` (hard rule) checks that payments in `fct_orders` sum to staging within a cent, so nothing is lost or duplicated.

### G. Text, encoding & format (DQ-17, DQ-18)

#### DQ-17 Free-text city names

- **Found:** 33 sellers have a city value that needs cleaning. Sellers typed the state into the city (`sao paulo - sp`, `pinhais/pr`), entered a zip code or an e-mail address, or typed just `sp`. 7 of these values are unusable as a city. The geolocation file has the same problem: 8,011 distinct city spellings reduce to 5,957 after cleaning accents, case, double spaces and state suffixes. A handful of encoding errors, such as the mojibake `sa£o paulo`, survive the cleaning in staging; none reaches a mart.
- **If ignored:** one city appears under several names, which splits city-level counts.
- **Handling:** the macro `clean_city_name` lower-cases, strips accents and suffixes, and returns null when the value is not a city. The 7 unusable seller cities are inferred from the zip prefix (`dim_sellers.is_city_inferred_from_zip`).
- **Tests:** `known_issue__seller_city_unusable` (baseline) and the unit test `test_seller_city_cleaning`.

#### DQ-18 File-format traps

- **Found:**
  - The reviews file has 104,719 physical lines for 99,224 rows: 3,852 review rows have line breaks inside the comment.
  - The translation file starts with a UTF-8 BOM and has no trailing newline. A line count gives 70 data rows; there are 71.
  - 23,995 customer records have a zip prefix that starts with 0.
  - Two product columns are misspelled (`product_name_lenght`, `product_description_lenght`).
- **If ignored:** `wc -l` and other line-based tools miscount the reviews by 5,495 lines. A BOM-unaware reader puts an invisible character in front of the first column name of the translation file. Reading zip prefixes as numbers drops the leading 0 for 23,995 customer records and breaks their join to geolocation.
- **Handling:** the loader uses a real CSV parser, loads every raw column as VARCHAR, and writes a load audit of physical lines against parsed rows (`raw.load_audit`). Staging renames the misspelled columns.
- **Tests:** nine load-integrity tests, one per source table, check that the raw row count equals the parsed count in `raw.load_audit` (`row_count_matches_load_audit`). `customer_zip_prefix_is_five_digits` is a hard rule.

### H. Coverage & reference data (DQ-19, DQ-20)

#### DQ-19 Incomplete months at both ends of the extract

- **Found:** 5 months have fewer than 100 orders. 2016-09 has 4 orders, 2016-11 none and 2016-12 one. 2018-09 and 2018-10 have 20 between them, 19 of them canceled. 2016-10 has 324 orders but is followed by an empty month, so all of 2016 is left out. Complete months run from 2017-01 to 2018-08.
- **If ignored:** trend charts end in a cliff, and comparisons against 2016 are meaningless.
- **Handling:** `dim_date.is_complete_data_month` marks the complete months, set by the vars `complete_data_start_month` and `complete_data_end_month`.
- **Tests:** `assert_complete_months_have_expected_volume` (hard rule) requires at least 500 net orders in every complete month. The smallest complete month, 2017-01, has 787.

#### DQ-20 Categories missing from the translation table

- **Found:** `pc_gamer` (3 products) and `portateis_cozinha_e_preparadores_de_alimentos` (10 products) have no English name.
- **If ignored:** English category reports show Portuguese labels or nulls.
- **Handling:** the seed `product_category_translation_overrides` supplies the English names.
- **Tests:** `assert_all_product_categories_translated` (hard rule) fails the build on any new untranslated category.

### I. Undocumented semantics (DQ-21)

#### DQ-21 Timestamps without time zone; misleading column names

- **Found:** no timestamp in `orders`, `order_items` or `order_reviews` records a time zone, and the values look like São Paulo local time. Two column names mislead: `review_creation_date` is the day the survey was sent, and `order_delivered_carrier_date` is the carrier pickup time.
- **If ignored:** for 14,377 orders (14.5%), placed in the last 2-3 hours of the local day, the UTC date is the next day. Mixing local and UTC dates moves them between days. São Paulo is UTC-3, or UTC-2 under the daylight saving time Brazil observed until 2019.
- **Handling:** the time zone is a documented assumption (America/Sao_Paulo, see [assumptions.md](assumptions.md)), and `fct_orders.order_purchased_at_utc` exists for UTC joins. Staging renames the columns to `review_survey_sent_date`, `order_delivered_to_carrier_at` and `order_delivered_to_customer_at`.
- **Tests:** none. The data records no time zone to test against; the evidence behind the assumption is in [assumptions.md](assumptions.md) (A-01).

## 4. How the testing works

Every `dbt build` (`make build`) runs 300 tests: 296 data tests and 4 unit tests. They run on the real data locally and on a synthetic fixture in CI. By category: completeness 136, validity 43, uniqueness 39, known-issue baselines 24, referential integrity 19, grain and fan-out 18, load integrity 9, reconciliation 6, business rules 2, unit tests 4.

### Hard rules and known-issue baselines

| Kind | Tests | Behaviour | Example |
|---|---:|---|---|
| Hard rule | 272 | Errors on the first failing row. Covers keys, not-null, accepted values, relationships, event order, non-negative amounts, grain (`row_count_matches`), reconciliation (`sum_matches`), load integrity and business rules. | `fct_orders_has_one_row_per_source_order` |
| Known-issue baseline | 24 | Encodes a documented source issue: passes at today's count, warns if the count grows, errors if it explodes. Tagged `known_issue`, with the register ID in `meta.dq_issue`; failing rows are stored. | `known_issue__carrier_pickup_before_approval` |
| Unit test | 4 | Fixed input rows and expected output. Tests logic, not data. | `test_late_delivery_and_status_logic` |

A baseline exists because neither alternative works. A hard rule on a known issue fails on every run until the source is fixed, and people learn to ignore a red build. No test at all lets the issue grow unnoticed. The baseline makes the accepted state explicit and alarms when it grows. This example, on `stg_olist__orders.order_delivered_to_carrier_at`, is from [`_olist__models.yml`](../dbt/models/staging/olist/_olist__models.yml):

```yaml
- not_before:
    name: known_issue__carrier_pickup_before_approval
    arguments:
      compare_column: order_approved_at
    config:
      warn_if: ">1359"
      error_if: ">2000"
      store_failures: true
      tags: [known_issue]
      meta:
        dq_issue: DQ-14
```

Up to 1,359 failing rows, the test passes. From 1,360 to 2,000 it warns: `dbt build` still exits 0, and the warning shows in the dbt summary and on the app's Test Results page. Above 2,000 it errors. `make all` then stops before the cache is refreshed, so the app and the report keep the last good numbers.

Baselines only alarm upward. If the source improves, the count drops and the test keeps passing without comment. When an upstream fix lands, lower `warn_if` to the new count in the same pull request so the improvement is locked in.

### Baseline thresholds

Every baseline today sits exactly at its warn threshold: it passes up to that count, warns above it, and errors above the value in the last column.

| DQ | Test | Model | Passes up to (today) | Errors above |
|---|---|---|---:|---:|
| DQ-02 | `known_issue__review_id_shared_across_orders` | `stg_olist__order_reviews` | 789 | 2,000 |
| DQ-03 | `known_issue__orders_with_multiple_reviews` | `stg_olist__order_reviews` | 547 | 2,000 |
| DQ-07 | `known_issue__products_missing_category` | `stg_olist__products` | 610 | 1,500 |
| DQ-07 | `known_issue__products_missing_weight` | `stg_olist__products` | 2 | 50 |
| DQ-07 | `known_issue__products_with_zero_weight` | `stg_olist__products` | 4 | 50 |
| DQ-08 | `assert_net_orders_have_items` | `fct_orders` | 8 | 100 |
| DQ-08 | `known_issue__net_orders_without_payment` | `fct_orders` | 1 | 10 |
| DQ-09 | `known_issue__customer_zip_prefix_missing_from_geolocation` | `stg_olist__customers` | 278 | 1,000 |
| DQ-09 | `known_issue__seller_zip_prefix_missing_from_geolocation` | `stg_olist__sellers` | 7 | 50 |
| DQ-10 | `known_issue__geolocation_points_outside_brazil` | `stg_olist__geolocation` | 27 | 200 |
| DQ-11 | `known_issue__payment_type_not_defined` | `stg_olist__order_payments` | 3 | 50 |
| DQ-11 | `known_issue__payment_with_zero_installments` | `stg_olist__order_payments` | 2 | 50 |
| DQ-12 | `assert_shipping_limit_within_90_days_of_purchase` | `stg_olist__order_items` | 8 | 100 |
| DQ-13 | `known_issue__deliveries_over_120_days` | `fct_orders` | 43 | 300 |
| DQ-14 | `known_issue__carrier_pickup_before_approval` | `stg_olist__orders` | 1,359 | 2,000 |
| DQ-14 | `known_issue__carrier_pickup_before_purchase` | `stg_olist__orders` | 166 | 500 |
| DQ-14 | `known_issue__delivered_before_carrier_pickup` | `stg_olist__orders` | 23 | 100 |
| DQ-14 | `known_issue__delivered_before_approval` | `stg_olist__orders` | 61 | 300 |
| DQ-14 | `known_issue__delivered_orders_missing_approval` | `stg_olist__orders` | 14 | 100 |
| DQ-14 | `known_issue__delivered_orders_missing_delivery_timestamp` | `stg_olist__orders` | 8 | 100 |
| DQ-14 | `known_issue__canceled_orders_with_delivery_timestamp` | `stg_olist__orders` | 6 | 100 |
| DQ-15 | `assert_reviews_not_sent_before_purchase` | `stg_olist__order_reviews` | 64 | 500 |
| DQ-16 | `assert_payments_reconcile_with_order_gmv` | `fct_orders` | 249 | 1,000 |
| DQ-17 | `known_issue__seller_city_unusable` | `stg_olist__sellers` | 7 | 50 |

The 20 generic baselines are configured in the model YAML files. The 4 named `assert_*` are singular tests in [`dbt/tests/singular/`](../dbt/tests/singular/).

### Stored failures

All 24 baselines set `store_failures: true`. On every run, dbt rewrites a table in the `test_failures` schema, named after the test, that holds the failing rows. That makes it possible to list the affected records without rewriting the test:

```sql
select * from test_failures.known_issue__carrier_pickup_before_approval limit 20;
```

The app's Test Results page shows each baseline's stored row count next to its thresholds. Hard rules do not store failures, because they are expected to have none. dbt does not drop the table of a renamed or deleted test, so go by the test names in this report.

### When a baseline warns or errors

1. List the rows from `test_failures.<test name>`.
2. Check whether the new failures are recent records, which point to a change in the source system, or older records whose values changed, which point to a re-extract. For orders, `snapshots.snp_olist__orders` keeps every earlier version of status and lifecycle timestamps once loads repeat.
3. If the source got worse, raise it with the Olist platform team (section 6) and keep the warning visible until it is fixed.
4. If the growth is understood and accepted, raise `warn_if` in the test's config (the model YAML, or the `config()` block of a singular test) and update the register entry in the same pull request. The Analytics Lead signs off on baseline changes.
5. Treat an error as a broken load or a source change, not as drift. Re-run the raw checks in `sql/data_quality/` and compare them with this report before anything is published.

### CI: every baseline must detect its issue

The real files are not in the repository. CI ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml), on every pull request and push to `main`) therefore runs the full pipeline on a synthetic fixture with the same 9 files and columns. [`ci/make_fixture.py`](../ci/make_fixture.py) generates 2,955 orders from a fixed seed. It plants at least one instance of every issue that has a baseline test, for example shared review IDs, re-reviewed orders, missing categories and weights, dirty seller cities, missing and out-of-Brazil geolocation points, payment mismatches, net orders without items or payment, and every lifecycle contradiction. The translation file is written with a BOM, like the real one.

On the fixture, every planted count stays below the production thresholds, so a passing baseline proves nothing on its own. After `dbt build`, [`ci/check_known_issues_detected.py`](../ci/check_known_issues_detected.py) checks two things for each of the 24 tests tagged `known_issue`: the test passed, and it stored at least one failing row. A test that can no longer see its issue, for example after a column rename or a wrong filter, fails the pull request. On the current fixture, each test detects between 1 and 35 rows.

The same CI run also fails on any hard-rule error, on dbt deprecation warnings (`dbt --warn-error parse`) and on `dbt_project_evaluator` best-practice violations. Because the fixture is small, the coverage test runs there with `min_net_orders_per_complete_month: 50`. What CI cannot check is real volume. The baselines are validated on the full data locally (`make all`), and the counts in this report come from that run.

## 5. Left for downstream users

The marts handle the issues above. These caveats remain for anyone building on them (see also [analyst_guide.md](analyst_guide.md)):

- **Customers:** count people with `customer_unique_id`. There is no `customer_id` in the marts (DQ-01).
- **Repeat customers:** use `is_repeat_customer` (2+ purchase days), not "customers with 2+ orders" (DQ-05).
- **Open orders:** net orders include 1,729 non-terminal orders, and 1,544 of them were placed more than 90 days before the last net order. Filter on `is_terminal_status` when you need settled outcomes.
- **Trends:** filter on `dim_date.is_complete_data_month` (2017-01 to 2018-08) (DQ-19).
- **Revenue:** use `order_gmv_brl`, and filter on `is_net_order` for net GMV. `payment_total_brl` includes what we read as card installment interest, and the payments on canceled and unavailable orders. Use it only for cash or payment-method questions (DQ-16).
- **Item-level sums:** filter `fct_order_items` on `is_net_order`. Units are `count(*)`; orders are `count(distinct order_id)` (DQ-04). The 8 net orders without items exist only in `fct_orders` (DQ-08).
- **Categories:** keep the `unknown` bucket visible (1,589 net-order item rows, 1.3% of net GMV), and exclude it only on purpose (DQ-07).
- **Reviews:** review metrics are per order, on the latest answer, with reviewed orders (`has_review`) as the denominator. `review_count > 1` marks the 547 re-reviewed orders. Do not measure the time from purchase to survey on the 64 surveys dated before the purchase (DQ-02, DQ-03, DQ-08, DQ-15).
- **Delivery:** use orders where `is_late_delivery` is not null (96,470 delivered orders with a timestamp), and report the median next to the mean (DQ-13, DQ-14).
- **Flagged orders:** 2,428 orders carry `data_quality_flags`, and they stay in every metric. To study or exclude them on purpose, filter on the booleans (`has_data_quality_flag`, `has_lifecycle_anomaly`, `is_payment_mismatch`, `has_items`, `has_payment`), not on the text codes. Durations between lifecycle steps are unreliable for the 1,410 orders with `has_lifecycle_anomaly` (DQ-14).
- **Geography:** use `fct_orders.delivery_state` for orders and deliveries; `dim_customers.customer_state` is the person's latest address instead. Maps drop the 269 people and 7 sellers without coordinates, so use state or region for aggregates. For sellers, prefer state over city (DQ-09, DQ-17).
- **Payment mix:** exclude `not_defined` from payment-method charts (DQ-11).
- **Seller handover SLA:** `seller_scorecard.late_handover_rate` uses single-seller orders only. Delivery and review outcomes of multi-seller orders (1.3% of orders) are attributed to every seller in them. The 8 items with deadlines more than 90 days out can only count as on time (DQ-12).
- **Dates:** all dates and timestamps are read as São Paulo local time, which is an assumption ([assumptions.md](assumptions.md), A-01). Use `order_purchased_at_utc` only to join systems that log in UTC (DQ-21).

## 6. Asks for the source owner (Olist platform team)

None of these blocks the marts. The first three would change how a KPI is reported. The rest would let us delete workarounds and the baseline tests that watch them.

| # | Ask | Issues | Why |
|---:|---|---|---|
| 1 | Publish refunds and chargebacks (order, amount, date, reason), and split installment interest from the principal on card payments | DQ-08, DQ-16 | R$269,735 was paid on canceled and unavailable orders, with no record of whether it was returned, and installment interest appears to be included in card payment amounts. Without this, net GMV reconciles to bookings but not to cash. |
| 2 | Record the time zone of every timestamp, or deliver UTC with the offset | DQ-21 | Daily metrics rest on an assumption, and 14.5% of orders change calendar day between local time and UTC. |
| 3 | Publish an order status history (status, changed at) and close out abandoned orders | DQ-14 | 1,729 open orders count as net orders, and 1,544 of them were placed more than 90 days before the last net order. A changed-at column would also let `fct_order_items` load changes directly instead of re-processing every open order ([ADR 0005](adr/0005-incremental-fct-order-items.md)). |
| 4 | Add a checkout (basket) ID to orders, and document how `customer_unique_id` is assigned | DQ-01, DQ-05 | 290 checkouts were split into 582 orders, so repeat purchase uses purchase days as a proxy. The whole customer model rests on `customer_unique_id`. |
| 5 | Add a quantity column to order items, or deliver one row per order line | DQ-04 | Units, lines and orders are easy to confuse, and 6,968 orders repeat a product across rows. |
| 6 | Make the review grain explicit: a unique key per answer and order, and a rule for which answer counts when an order is surveyed twice | DQ-02, DQ-03 | 789 review IDs are shared across orders, and 202 re-reviewed orders disagree on the score. Today we keep the latest answer by assumption. |
| 7 | Document what `order_approved_at` and `order_delivered_carrier_date` record. Explain why 1,359 orders reached the carrier before approval and 6 canceled orders have a delivery time | DQ-14 | Durations between lifecycle steps are unreliable for the 1,410 flagged orders. If approval is recorded later by a batch process, documenting that is enough. |
| 8 | Replace the free-text seller city with a validated field (IBGE municipality code). Publish one validated point per zip prefix that covers every customer and seller prefix and lies inside the row's state | DQ-06, DQ-09, DQ-10, DQ-17 | 7 seller cities are unusable, 157 customer prefixes and 7 seller prefixes are missing from geolocation, and 31 rows (27 distinct points) lie outside Brazil. |
| 9 | Validate at entry: category, weight and dimensions mandatory on listings; shipping deadline within 90 days of purchase; survey date after purchase; no `not_defined` payment type or 0 installments | DQ-07, DQ-11, DQ-12, DQ-15 | The counts are small, but each one needs a workaround and a baseline test today. |
| 10 | Deliver typed files (Parquet), or document the CSV dialect (UTF-8 without BOM, zip codes as text, correct column names). Keep the category translation complete, and deliver whole months only | DQ-18, DQ-19, DQ-20 | Removes the line-count trap, the BOM, the leading-zero risk, the `*_lenght` renames, the translation override seed and the manual cut of partial months. |

When a fix lands, the matching baseline's count drops, and we lower its `warn_if` to lock in the gain (section 4).

## 7. How to re-run

You need the 9 Olist CSV files, located by `raw_data_dir` in [`config.yaml`](../config.yaml) or by `OLIST_RAW_DIR` in `.env`.

```bash
make all       # full pipeline: setup -> load -> dbt build (models + 300 tests) -> docs -> incremental check -> cache -> notebooks -> report
make build     # dbt build: seeds, snapshot, models, data tests, unit tests, contracts
make cache     # re-runs the register's count_sql and the sql/ checks on raw; writes data/cache/ (incl. dq_issues.parquet)
uv run python scripts/render_docs_tables.py   # refreshes the register table in this file from the cache (make report runs it too)
make ci-local  # the CI pipeline on the synthetic fixture, in a separate data/warehouse/ci.duckdb
```

To run only the 24 baselines:

```bash
cd dbt && uv run dbt test --profiles-dir . --select tag:known_issue
```

The standalone raw checks open the warehouse read-only, and each file also runs as-is in any DuckDB client opened on `data/warehouse/olist.duckdb`:

```bash
uv run python scripts/run_sql.py sql/data_quality/08_lifecycle_consistency.sql
```

| File in `sql/data_quality/` | Checks | Issues |
|---|---|---|
| `01_row_counts_vs_load_audit.sql` | file lines vs parsed rows vs release counts vs raw | DQ-18 |
| `02_primary_keys.sql` | whether each candidate key is unique | DQ-01, DQ-02, DQ-03, DQ-06 |
| `03_null_profile.sql` | null counts per column | DQ-07, DQ-14 |
| `04_value_ranges_and_outliers.sql` | ranges and implausible values | DQ-07, DQ-10, DQ-11, DQ-13 |
| `05_time_ranges_and_coverage.sql` | min and max of every timestamp, orders per month | DQ-12, DQ-19, DQ-21 |
| `06_referential_integrity.sql` | orphans, missing children, missing lookups | DQ-08, DQ-09, DQ-20 |
| `07_payment_reconciliation.sql` | payments vs items + freight | DQ-16 |
| `08_lifecycle_consistency.sql` | contradictory lifecycle timestamps | DQ-14 |

Results and reading notes for each file are in [03_data_quality_checks.md](03_data_quality_checks.md).

**Adding an issue:** add an entry to `issue_register.yml` with a `count_sql` that returns one integer from `raw`. Add a baseline test with `tags: [known_issue]`, `store_failures: true` and `meta.dq_issue`, and plant an instance in `ci/make_fixture.py` so CI proves the test detects it. Then run `make cache` and re-render this table.
