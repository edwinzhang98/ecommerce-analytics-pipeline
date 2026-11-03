# Q1. How do delivery time and lateness relate to bad reviews, and which states are worst?

**Answer.** Missing the estimated date goes with the largest jump in bad reviews. Late deliveries get a bad review (1-2 stars) 62.42% of the time, against 9.25% for on-time deliveries. Delivery time matters too: on-time deliveries that take 31 days or more get a bad review 23.17% of the time, against 7.54% for those that take a week or less. Across states, the late rate tracks the bad-review rate closely (r = 0.937 over 21 states).

Rio de Janeiro (RJ) is the place to start. It has the second-largest number of late deliveries after São Paulo, and more bad reviews than its lateness and delivery times predict. These are associations in historical data, not measured effects.

SQL: [`q1_delivery_vs_reviews_by_state.sql`](q1_delivery_vs_reviews_by_state.sql). Numbers come from the build of 2026-11-03, with default parameters.

## Question

How do delivery time and lateness relate to bad reviews, by delivery state? Which states should logistics look at first?

## Decision it supports

Where logistics improvements start: which delivery states (and their routes and carriers) get reviewed first, and whether the estimated delivery date needs work. Owner: ops / logistics lead.

## Data and population

- **Tables.** `fct_orders`, joined to `dim_date` on `order_purchase_date`.
- **Population.** 95,560 reviewed deliveries. These are delivered orders with a delivery timestamp (`is_late_delivery is not null`) that have a review (`has_review`), purchased in a complete month, 2017-01 to 2018-08 (`dim_date.is_complete_data_month`).
- **Review coverage.** Almost every delivery has a review: 95,824 of 96,470 measured deliveries across all months, or 99.3%. Survey non-response is therefore not a material bias here.
- **State.** `delivery_state`, the order's delivery address. This is not the person's latest address in `dim_customers`.
- **Review.** The latest answered review per order (DQ-03).
- **Bad review.** A score of 2 or lower (`bad_review_max_score = 2`).
- **Late.** Delivered on a later calendar day than the estimated date shown at purchase. `delivery_delay_days` is the delivery date minus the estimated date, so a negative value means early.
- **Small states.** States with fewer than 300 reviewed deliveries (`min_orders_per_state`) are left out of the state table and the correlation. These are TO, RO, AM, AC, AP and RR, with 845 reviewed deliveries in total. They stay in the national figures.

## Method

1. **Late vs on time.** The bad-review rate for each group, with a 95% Wilson interval.
2. **By delay.** The same rate by days early or late against the estimate. This shows whether the rate rises gradually with delay or steps up at the estimated date.
3. **By state.** For each state: mean and median delivery days (medians because a few deliveries take over 120 days, DQ-13), the late rate, and the bad-review rate with its Wilson interval. Each state also gets an **expected bad-review rate from lateness alone**:

   expected = state late rate × 62.42% + (1 − state late rate) × 9.25%

   - The two percentages are the national bad-review rates for late and for on-time deliveries.
   - The expected rate is what the state would score if the only difference from the national picture were how often its deliveries are late.
   - Excess = actual − expected, in percentage points.
   - A state whose whole 95% interval lies above its expected rate has more bad reviews than its lateness alone predicts.
   - In the app's scatter, the expected rate is the dotted line.
4. **Across states.** The Pearson correlation between late rate and bad-review rate over the 21 states (each state counts once), its R², and the regression slope.
5. **Two checks that are not in the SQL file** (queries under [How to reproduce](#how-to-reproduce)):
   - the bad-review rate by delivery days for on-time deliveries only, which separates the wait from the broken promise;
   - a second expected rate per state, built from the national bad-review rate for each combination of late or on time and delivery week (0–6, 7–13, … 42+ days). It accounts for slow deliveries that still arrive on time.

Why Wilson intervals: they stay within 0–100% and keep close to 95% coverage for small groups and for rates near 0% or 100%. The textbook normal interval does neither. The smallest state shown has 331 reviewed deliveries.

## Results

**Late vs on time**

| Delivery | Reviewed deliveries | Bad reviews | Bad-review rate | 95% CI | Avg score |
|---|---:|---:|---:|---|---:|
| Late | 6,378 | 3,981 | 62.42% | 61.22–63.60% | 2.27 |
| On time | 89,182 | 8,247 | 9.25% | 9.06–9.44% | 4.29 |

6.67% of reviewed deliveries were late. Late deliveries get a bad review 6.7 times as often as on-time ones.

**By delay against the estimate**

| Delivered | Reviewed deliveries | Bad-review rate | 95% CI |
|---|---:|---:|---|
| 15+ days early | 34,526 | 9.00% | 8.71–9.31% |
| 8–14 days early | 36,147 | 8.90% | 8.61–9.20% |
| 1–7 days early | 17,229 | 10.23% | 9.78–10.69% |
| On the estimated day | 1,280 | 12.42% | 10.73–14.34% |
| 1–3 days late | 1,851 | 32.14% | 30.06–34.31% |
| 4–7 days late | 1,748 | 67.68% | 65.45–69.83% |
| 8–14 days late | 1,446 | 80.15% | 78.02–82.13% |
| 15+ days late | 1,333 | 78.32% | 76.03–80.45% |

For most orders the estimate is generous: 74% of reviewed deliveries (70,673) arrived 8 or more days early.

**Delivery time, on-time deliveries only**

| Delivery time | Reviewed deliveries | Bad-review rate | 95% CI |
|---|---:|---:|---|
| 0–7 days | 30,442 | 7.54% | 7.24–7.84% |
| 8–14 days | 37,361 | 8.86% | 8.58–9.16% |
| 15–21 days | 15,414 | 11.03% | 10.54–11.53% |
| 22–30 days | 5,171 | 14.64% | 13.70–15.63% |
| 31+ days | 794 | 23.17% | 20.37–26.23% |

Slow deliveries go with more bad reviews even when they keep the promise.

**By delivery state** (21 states with 300+ reviewed deliveries, sorted by late rate)

| State | Region | Reviewed deliveries | Median days | Late rate | Bad-review rate (95% CI) | Expected from lateness | Excess (pp) |
|---|---|---:|---:|---:|---|---:|---:|
| AL | Northeast | 393 | 22 | 20.87% | 21.37% (17.61–25.69) | 20.34% | +1.03 |
| MA | Northeast | 709 | 19 | 17.21% | 20.03% (17.25–23.13) | 18.40% | +1.63 |
| SE | Northeast | 331 | 18 | 15.11% | 19.03% (15.17–23.61) | 17.28% | +1.75 |
| PI | Northeast | 470 | 16 | 13.83% | 16.17% (13.12–19.77) | 16.60% | −0.43 |
| CE | Northeast | 1,267 | 18 | 13.73% | 17.21% (15.23–19.38) | 16.55% | +0.66 |
| RJ | Southeast | 12,172 | 12 | 11.96% | 18.33% (17.65–19.03) | 15.61% | +2.72 |
| BA | Northeast | 3,226 | 17 | 11.90% | 17.02% (15.76–18.35) | 15.58% | +1.44 |
| PA | North | 929 | 21 | 10.76% | 17.98% (15.64–20.58) | 14.97% | +3.01 |
| ES | Southeast | 1,966 | 14 | 10.43% | 13.84% (12.38–15.43) | 14.79% | −0.95 |
| PB | Northeast | 511 | 18 | 10.18% | 14.87% (12.05–18.22) | 14.66% | +0.21 |
| MS | Center-West | 699 | 14 | 9.73% | 13.30% (10.99–16.02) | 14.42% | −1.12 |
| PE | Northeast | 1,573 | 16 | 9.47% | 14.81% (13.14–16.65) | 14.28% | +0.53 |
| RN | Northeast | 467 | 16 | 9.21% | 13.06% (10.30–16.42) | 14.14% | −1.08 |
| SC | South | 3,510 | 13 | 8.09% | 12.96% (11.89–14.11) | 13.55% | −0.59 |
| GO | Center-West | 1,939 | 14 | 6.40% | 13.20% (11.77–14.78) | 12.65% | +0.55 |
| RS | South | 5,309 | 13 | 6.05% | 11.92% (11.08–12.82) | 12.46% | −0.54 |
| MT | Center-West | 878 | 16 | 5.81% | 12.76% (10.71–15.13) | 12.34% | +0.42 |
| DF | Center-West | 2,064 | 11 | 5.72% | 13.18% (11.79–14.71) | 12.29% | +0.89 |
| MG | Southeast | 11,251 | 10 | 4.49% | 11.71% (11.13–12.32) | 11.63% | +0.08 |
| SP | Southeast | 40,171 | 7 | 4.44% | 10.66% (10.37–10.97) | 11.61% | −0.95 |
| PR | South | 4,880 | 10 | 3.98% | 10.86% (10.02–11.76) | 11.36% | −0.50 |

In four states, the expected rate falls outside the state's own 95% interval:

- RJ (+2.72 pp), PA (+3.01 pp) and BA (+1.44 pp) have more bad reviews than their lateness predicts.
- SP (−0.95 pp) has fewer.

In the other 17 states, the difference is within sampling noise. Two checks narrow the list:

- **Chance.** With 21 states each tested at 95%, about one would fall outside by chance alone. PA and BA are only just outside: their lower bounds are 15.64% and 15.76%, against expected rates of 14.97% and 15.58%.
- **Delivery time.** When the expected rate also accounts for delivery time (Method, point 5), RJ is still clearly above it: 18.33% against 16.45% expected, an excess of +1.88 pp, with an interval of 17.65–19.03%. PA (−1.77 pp) and BA (−0.88 pp) fall back within their intervals: their high rates are in line with their slow deliveries. SP's shortfall also disappears (+0.37 pp), as its deliveries are the fastest (median 7 days).

**Across states.** Over the 21 states, the late rate and the bad-review rate correlate at r = 0.937 (R² = 0.879). Average delivery days correlate less strongly, at r = 0.819. Each 10 pp of late rate goes with about 6.5 pp more bad reviews (a slope of 65.0 pp per 100 pp).

**Where the late deliveries are**

| State | Late reviewed deliveries | Late rate |
|---|---:|---:|
| SP | 1,783 | 4.44% |
| RJ | 1,456 | 11.96% |

SP has the most late reviewed deliveries, but at a 4.44% late rate it is one of the best-performing states. RJ comes second, with 2.7 times SP's late rate. Together they account for 3,239 of the 6,378 late reviewed deliveries.

**Sensitivity.** The national pattern does not depend on the parameter choices:

| Setting | Bad-review rate, late | Bad-review rate, on time | r across states |
|---|---:|---:|---:|
| Default: bad = 1-2 stars, complete months | 62.42% | 9.25% | 0.937 |
| Bad = 1 star (`bad_review_max_score=1`) | 53.76% | 6.60% | 0.908 |
| Bad = 1-3 stars (`bad_review_max_score=3`) | 73.30% | 17.32% | 0.887 |
| All months (`complete_months_only=false`) | 62.42% | 9.27% | 0.936 |

The states outside their interval change a little. RJ, PA and SP are outside in all four settings. BA is not when a bad review means 1 star only, and PR joins SP below its expected rate at 1-3 stars.

## Conclusion

- **Lateness is strongly associated with bad reviews.** The bad-review rate:
  - is flat while parcels arrive early (about 9–10%);
  - rises slightly on the estimated day (12.42%);
  - reaches 32.14% one to three days late;
  - passes two thirds from four days late (67.68%).

  How early a parcel arrives makes little difference: 15 or more days early scores the same as 8–14 days early (9.00% vs 8.90%). How long it takes does: on-time deliveries of 31 days or more get a bad review 23.17% of the time, against 7.54% within a week. Both the wait and the broken promise go with bad reviews, and the broken promise is the bigger step. This data cannot separate either from what else differs between fast and slow routes.
- **The late rate lines up with most of the difference between states.** Across states, it explains 88% of the variance in bad-review rates (R² = 0.879). That is a correlation over 21 state averages, though. It cannot separate lateness from everything else that differs between, say, Alagoas and São Paulo: distance, carriers, product mix, prices and customer expectations.
- **RJ has more bad reviews than its lateness and delivery times predict.** Its excess is +2.72 pp against lateness alone and +1.88 pp once delivery time is also accounted for. Both lie beyond its 95% interval, and the first holds in every sensitivity setting. PA's and BA's excess is in line with their slow deliveries, and BA's also disappears when a bad review means 1 star. In RJ, both groups of deliveries do worse than the national rate:

  | RJ deliveries | RJ bad-review rate (95% CI) | National rate (95% CI) |
  |---|---|---|
  | On time | 10.89% (10.31–11.49%) | 9.25% (9.06–9.44%) |
  | Late | 73.08% (70.74–75.29%) | 62.42% (61.22–63.60%) |

  The cause is not visible in the marts at state level.
- **RJ combines volume with a high rate.** It has 12,172 reviewed deliveries, an 11.96% late rate and a 2.72 pp excess. The Northeast states have the highest late rates (AL 20.87%, MA 17.21%, SE 15.11%), but small volumes: 1,433 reviewed deliveries between them.

## Recommendations

**R1. Start the carrier and route review in RJ.**

- **Who:** Ops / logistics lead.
- **What:** Review carrier performance and routes for RJ deliveries first. Look at transit times by carrier and by city (Rio metro vs the interior), and at where parcels wait between carrier pickup and delivery.
- **Why RJ before the Northeast:** The two rankings disagree:
  - Ranking states by late rate puts AL, MA and SE first.
  - Ranking them by the number of late deliveries puts SP and RJ first.

  RJ ranks second by count and sixth of 21 by late rate. It is also the only state whose excess holds up under every check above. Over the 20 complete months, RJ alone had 1,456 late reviewed deliveries, against 254 for AL, MA and SE combined.
- **Expected impact:** Nationally, late deliveries get bad reviews 62.42% of the time and on-time ones 9.25%. If the association were fully causal, every 100 late deliveries turned on-time would mean about 53 fewer bad reviews. Treat that as an upper bound.
- **How to measure:** Track the monthly late rate and bad-review rate for RJ deliveries against MG and SP over the same months, so seasonal swings cancel out.
- **Risk:** RJ's excess exists even for on-time deliveries, so faster delivery alone may not close the gap. A carrier change costs money and takes time to show in reviews.

**R2. In the Northeast, check the delivery estimate before changing carriers.**

- **Who:** Ops / logistics lead, with whoever owns the delivery estimate shown at checkout.
- **What:** In AL, MA and SE, between one delivery in five and one in seven arrives after its estimate. Nationally, 74% arrive 8 or more days early. Make the estimate route-specific so it is realistic in these states, instead of padding it everywhere.
- **Expected impact:** Fewer deliveries cross the promised date in these states. The absolute effect on reviews is small: the three states had 1,433 reviewed deliveries over 20 months.
- **How to measure:** Compare the late rate and bad-review rate in the three states before and after the change. Also track checkout conversion, because a longer promised date can lose sales. Conversion is not in this dataset.
- **Risk:** Moving the target changes the "late" metric without changing delivery speed. Report delivery days next to the late rate, so the improvement is not only in the definition. Slow deliveries get more bad reviews even when on time, so a later promise alone may not move reviews much.

## Next step to validate

1. **Rule out product and seller mix (a few days, marts only).** Fit a logistic model of bad review on late delivery, with delivery state, delivery days, product category (`fct_order_items` → `dim_products`), price, freight and seller state as controls.
   - If RJ keeps its excess, product and seller mix do not explain it, and the carrier and route review in R1 is the right place to look.
   - If the excess disappears, it lies in what customers there buy, and from whom.
2. **Test a late-delivery notice (an experiment).** On each order's estimated date, take the orders that are still undelivered. Send half of them, chosen at random, a proactive message with a new date, and leave the other half as today. Compare the bad-review rates. This tests the cheapest lever, communication, without changing carriers. The required sample, with 80% power and a two-sided 5% test, at about 500 late deliveries a month (4,078 in January–August 2018, but anywhere from 71 to 1,328 in a single month, so the collection times are rough):

   | Effect to detect (bad-review rate, late deliveries) | Late deliveries per arm | Time to collect |
   |---|---:|---|
   | 62.42% → 57.42% | 1,507 | about six months |
   | 62.42% → 52.42% | 383 | about 1.5 months |

## How to reproduce

```bash
uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql
uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql --var bad_review_max_score=1
uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql --var bad_review_max_score=3
uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql --var complete_months_only=false
uv run python scripts/run_sql.py analyses/q1_delivery_vs_reviews_by_state.sql --var min_orders_per_state=0   # all 27 states
```

The app's Business questions page (tab Q1) runs the same file, and its controls set the three parameters. The scatter there plots the state table against the expected-from-lateness line.

Some numbers above are not in the file's output. The three queries below reuse the file's `q1_population` view and Wilson macros, so run them in the same DuckDB session after the file. For example, open the warehouse with `duckdb -readonly data/warehouse/olist.duckdb` and `.read` the file first.

- **Bad-review rates by state for late and on-time deliveries, with intervals.**

  ```sql
  select
      delivery_state,
      count(*) filter (where is_late_delivery) as late_deliveries,
      count(*) filter (where is_late_delivery and is_bad) as late_bad,
      round(100.0 * late_bad / late_deliveries, 2) as late_bad_pct,
      round(100 * wilson_low(late_bad::double, late_deliveries), 2) as late_ci_low_pct,
      round(100 * wilson_high(late_bad::double, late_deliveries), 2) as late_ci_high_pct,
      count(*) filter (where not is_late_delivery) as on_time_deliveries,
      count(*) filter (where not is_late_delivery and is_bad) as on_time_bad,
      round(100.0 * on_time_bad / on_time_deliveries, 2) as on_time_bad_pct,
      round(100 * wilson_low(on_time_bad::double, on_time_deliveries), 2) as on_time_ci_low_pct,
      round(100 * wilson_high(on_time_bad::double, on_time_deliveries), 2) as on_time_ci_high_pct
  from q1_population
  group by delivery_state
  order by late_deliveries desc;
  ```
- **Bad-review rate by delivery time, on-time deliveries only.**

  ```sql
  select
      case
          when delivery_days <= 7 then '0-7 days'
          when delivery_days <= 14 then '8-14 days'
          when delivery_days <= 21 then '15-21 days'
          when delivery_days <= 30 then '22-30 days'
          else '31+ days'
      end as delivery_time,
      count(*) as reviewed_deliveries,
      count(*) filter (where is_bad) as bad_reviews,
      round(100.0 * bad_reviews / reviewed_deliveries, 2) as bad_review_rate_pct,
      round(100 * wilson_low(bad_reviews::double, reviewed_deliveries), 2) as ci_low_pct,
      round(100 * wilson_high(bad_reviews::double, reviewed_deliveries), 2) as ci_high_pct
  from q1_population
  where not is_late_delivery
  group by delivery_time
  order by min(delivery_days);
  ```
- **Expected rate from lateness and delivery time, by state.**

  ```sql
  with

  weeks as (
      select *, least(delivery_days // 7, 6) as delivery_week  -- 0-6, 7-13, ..., 42+ days
      from q1_population
  ),

  national as (
      select is_late_delivery, delivery_week, avg(is_bad::int) as bad_rate
      from weeks
      group by is_late_delivery, delivery_week
  )

  select
      weeks.delivery_state,
      count(*) as reviewed_deliveries,
      round(100 * avg(weeks.is_bad::int), 2) as bad_review_rate_pct,
      round(100 * wilson_low(sum(weeks.is_bad::int)::double, count(*)), 2) as ci_low_pct,
      round(100 * wilson_high(sum(weeks.is_bad::int)::double, count(*)), 2) as ci_high_pct,
      round(100 * avg(national.bad_rate), 2) as expected_from_lateness_and_days_pct,
      round(bad_review_rate_pct - expected_from_lateness_and_days_pct, 2) as excess_pp
  from weeks
  inner join national
      on weeks.is_late_delivery = national.is_late_delivery
      and weeks.delivery_week = national.delivery_week
  group by weeks.delivery_state
  having count(*) >= getvariable('min_orders_per_state')
  order by excess_pp desc;
  ```
- **Review coverage (99.3%).** `count(*) filter (where has_review)` over `marts.fct_orders where is_late_delivery is not null`.
- **Late deliveries in 2018 (4,078).** `count(*) filter (where is_late_delivery)` over `marts.fct_orders` joined to `marts.dim_date`, for complete-month orders purchased from 2018-01-01. Group by `dim_date.year_month` for the monthly range (71 to 1,328).
- **Sample sizes.** The standard two-proportion formula: two-sided α = 0.05, power 0.80.
