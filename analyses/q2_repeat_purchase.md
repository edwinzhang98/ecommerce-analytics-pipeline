# Q2. What share of customers buy again, and how quickly?

**Answer: few.** 2.17% of customers (2,065 of the 94,990 people with a net order) bought on two or more different days. In cohorts observed for the full window, 2.00% (95% CI 1.89–2.12%) came back within 180 days of their first purchase. Returns are spread over months: among customers observed for at least a year, those who came back within that year took a median of 125 days.

A late or badly reviewed first order goes with a return rate about 0.4–0.5 percentage points lower. Even if those gaps were causal, closing them would add about one or two repeat customers a month (late first deliveries) or about three (bad first reviews) at current volumes. First-order experience is not a retention lever worth funding on its own.

SQL: [`q2_repeat_purchase.sql`](q2_repeat_purchase.sql). Numbers come from the build of 2026-11-03, with the default `repeat_window_days = 180`.

## Question

What share of customers buy again, and how quickly do they come back? Does the experience of the first order go with coming back?

## Decision it supports

Whether the next marketing budget leans towards retention (CRM) or acquisition, and whether fixing first-order experience is worth funding as a retention measure. Owner: CRM manager.

## Data and population

- **Tables.** `fct_orders` (net orders) and `customer_360`, which has one row per person with `days_to_second_purchase`, `first_net_order_month` and `rfm_reference_date`.
- **Customer.** A person: `customer_unique_id`. The source's `customer_id` is issued per order, so counting on it gives a 0% repeat rate ([`sql/metrics/03_customer_key_trap_on_raw.sql`](../sql/metrics/03_customer_key_trap_on_raw.sql), DQ-01). The marts do not expose it ([ADR 0003](../docs/adr/0003-grain-fan-out-and-customer-identity.md)).
- **Repeat customer.** Net orders on 2 or more distinct purchase days (`dim_customers.is_repeat_customer`).
- **Population.** 94,990 people with at least one net order. Another 1,106 people only ever had canceled or unavailable orders.
- **Cohort.** The month of a person's first net order, 2017-01 to 2018-08.
- **Reference date.** 2018-09-03, the last net-order purchase date in the data (`rfm_reference_date`). Observation windows are measured up to this date, not up to today.
- **Parameter.** `repeat_window_days` (default 180), used by the cohort and first-experience results.

## Method

1. **Definition sensitivity.** The same people are counted under three definitions: 2+ net orders, 2+ checkouts (distinct purchase timestamps), and 2+ purchase days (the official one). One checkout can be split into several orders in the same second, mostly one per seller (DQ-05, 290 times), and the naive definition counts that as coming back. So does a second checkout on the same day.
2. **Time to second purchase.** Days from the first purchase day to the second, for all 2,065 repeat customers. This pools customers observed for anything from a few days to two years, and recent customers can only appear if they came back quickly. A check on customers observed for at least a year removes that bias (not in the SQL file; query under [How to reproduce](#how-to-reproduce)).
3. **Repeat within N days by cohort, fully observed cohorts only.** Someone who first bought in August 2018 has had only a few weeks to return. Recent cohorts therefore look worse purely because less time has passed (right-censoring).
   - A cohort counts only when its last customer has had the full N days before the reference date.
   - The SQL marks each cohort with `is_fully_observed`.
   - With N = 180, the cohorts 2017-01 to 2018-02 qualify.
4. **Repeat by first-order experience.** The share returning within N days, compared on two splits:
   - first net order delivered late vs on time;
   - first review bad (1-2 stars) vs not.

   Only customers whose first order was at least N days before the reference date are included (first orders up to 2018-03-07 for N = 180). Each group gets a 95% Wilson interval. The difference between two groups gets a 95% Newcombe interval, which combines the two Wilson intervals and can be computed from the four counts in the output.

## Results

**Definition sensitivity**

| Definition | Customers | Repeat customers | Repeat rate |
|---|---:|---:|---:|
| 2+ net orders | 94,990 | 2,888 | 3.04% |
| 2+ checkouts | 94,990 | 2,638 | 2.78% |
| 2+ purchase days (official) | 94,990 | 2,065 | 2.17% |

The naive definition reports 40% more repeat customers than the official one.

**Time to second purchase** (2,065 repeat customers; median 74 days)

| Second purchase day | Repeat customers | Share | Cumulative |
|---|---:|---:|---:|
| 1–7 days | 213 | 10.3% | 10.3% |
| 8–30 days | 402 | 19.5% | 29.8% |
| 31–90 days | 518 | 25.1% | 54.9% |
| 91–180 days | 434 | 21.0% | 75.9% |
| 181–365 days | 411 | 19.9% | 95.8% |
| Over 365 days | 87 | 4.2% | 100.0% |

This table overstates early returns: a customer who first bought in mid-2018 can only appear in it after a quick return. The 22,597 customers whose first net order was on or before 2017-09-03 were all observed for at least a year:

| Came back within | Customers | Share of the 22,597 | Share of those back within a year |
|---|---:|---:|---:|
| 90 days | 303 | 1.34% | 40.5% |
| 180 days | 479 | 2.12% | 64.0% |
| 365 days | 749 | 3.31% | 100% |

For them, the median time to the second purchase day is 125 days (among those back within a year), against 74 days in the pooled table.

**Repeat within 180 days, by first-purchase month**

| Cohort | Customers | Repeat customers | Rate | 95% CI | Fully observed |
|---|---:|---:|---:|---|---|
| 2017-01 | 752 | 13 | 1.73% | 1.01–2.94% | yes |
| 2017-02 | 1,690 | 28 | 1.66% | 1.15–2.38% | yes |
| 2017-03 | 2,571 | 47 | 1.83% | 1.38–2.42% | yes |
| 2017-04 | 2,325 | 47 | 2.02% | 1.52–2.68% | yes |
| 2017-05 | 3,541 | 85 | 2.40% | 1.95–2.96% | yes |
| 2017-06 | 3,102 | 71 | 2.29% | 1.82–2.88% | yes |
| 2017-07 | 3,822 | 78 | 2.04% | 1.64–2.54% | yes |
| 2017-08 | 4,130 | 102 | 2.47% | 2.04–2.99% | yes |
| 2017-09 | 4,075 | 106 | 2.60% | 2.16–3.14% | yes |
| 2017-10 | 4,392 | 78 | 1.78% | 1.43–2.21% | yes |
| 2017-11 | 7,190 | 132 | 1.84% | 1.55–2.17% | yes |
| 2017-12 | 5,439 | 91 | 1.67% | 1.36–2.05% | yes |
| 2018-01 | 6,951 | 123 | 1.77% | 1.49–2.11% | yes |
| 2018-02 | 6,357 | 125 | 1.97% | 1.65–2.34% | yes |
| 2018-03 | 6,931 | 105 | 1.51% | 1.25–1.83% | no |
| 2018-04 | 6,698 | 110 | 1.64% | 1.36–1.98% | no |
| 2018-05 | 6,586 | 93 | 1.41% | 1.15–1.73% | no |
| 2018-06 | 5,920 | 56 | 0.95% | 0.73–1.23% | no |
| 2018-07 | 6,016 | 52 | 0.86% | 0.66–1.13% | no |
| 2018-08 | 6,209 | 23 | 0.37% | 0.25–0.56% | no |

Pooled over the 14 fully observed cohorts, 1,126 of 56,337 customers returned: 2.00% (95% CI 1.89–2.12%). Individual cohorts range from 1.66% to 2.60%, and they are not flat:

| Cohorts | Customers | Repeat customers | Rate | 95% CI |
|---|---:|---:|---:|---|
| 2017-01 to 2017-04 | 7,338 | 135 | 1.84% | 1.56–2.17% |
| 2017-05 to 2017-09 | 18,670 | 442 | 2.37% | 2.16–2.60% |
| 2017-10 to 2018-02 | 30,329 | 549 | 1.81% | 1.67–1.97% |

The mid-2017 cohorts are above both neighbours: by 0.53 pp (95% CI 0.13–0.89) over the earlier block and by 0.56 pp (0.30–0.83) over the later one.

With a 90-day window (`--var repeat_window_days=90`), 17 cohorts are fully observed (2017-01 to 2018-05), and the pooled rate is 1.31% (1.23–1.39%).

**Repeat within 180 days, by first-order experience**

| First order | Customers | Repeat customers | Rate | 95% CI |
|---|---:|---:|---:|---|
| Delivered late | 4,127 | 64 | 1.55% | 1.22–1.98% |
| Delivered on time | 53,033 | 1,070 | 2.02% | 1.90–2.14% |
| Bad review (1-2 stars) | 8,543 | 139 | 1.63% | 1.38–1.92% |
| Review of 3-5 stars | 49,306 | 1,010 | 2.05% | 1.93–2.18% |

| Comparison | Difference | 95% CI (Newcombe) | Relative |
|---|---:|---|---:|
| Late vs on-time first delivery | −0.47 pp | −0.82 to −0.03 pp | −23% |
| Bad vs not-bad first review | −0.42 pp | −0.70 to −0.11 pp | −21% |

## Conclusion

- **Almost every customer buys once.** 92,925 people are one-time customers, against 2,065 repeat customers. With about 2% returning within 180 days, retention spending works on a small base. A 25% relative lift (2.0% → 2.5%) would add about 5 returning customers per 1,000 new customers.
- **The definition matters.** Counting orders instead of purchase days overstates repeat buying by 40%. Split checkouts account for the step from 3.04% to 2.78%, and separate checkouts on the same day for the step from 2.78% to 2.17%. The official definition treats neither as a return visit. Counting on `customer_id` brings the rate to 0%.
- **The repeat rate moves between cohorts, and the latest comparable ones sit at the low end.** The mid-2017 cohorts came back more often within 180 days (2.37%) than those before (1.84%) and after them (1.81%), by more than sampling noise. One year of comparable cohorts cannot tell whether that is seasonal, a change in who was acquired, or the start of a decline. The rates for the 2018-03 to 2018-08 cohorts (down to 0.37%) are no evidence either way: not all of those customers have had 180 days yet.
- **Returns are spread over the first year.** Among customers observed for at least a year, 40.5% of those who came back within the year did so within 90 days and 64.0% within 180 days (median 125 days). The pooled figure of 54.9% within 90 days overstates early returns. A contact in the first three months still comes before most second purchases.
- **First-order experience shows a small gap that cannot be separated from other factors.**
  - Customers with a late first delivery return 0.47 pp less often, and those with a bad first review 0.42 pp less often. Both intervals exclude zero, but their upper ends sit close to it (−0.03 and −0.11 pp).
  - The two comparisons are not independent: a late delivery is far more likely to get a bad review (62.42% vs 9.25%, Q1).
  - Late deliveries are more likely in states with long delivery times (Q1), and customers there may return less often for other reasons.
  - Even taken at face value, the gaps are tiny in absolute terms. In 2017-01 to 2018-08, about 317 customers a month had a late first delivery and about 653 a bad first review. Closing the gaps would add about 1–2 and about 3 repeat customers a month.

  The case for fixing lateness rests on reviews ([Q1](q1_delivery_vs_reviews_by_state.md)), not on retention.

## Recommendations

**R1. Plan retention with the official rate, and test before building a programme.**

- **Who:** CRM manager.
- **What:** Plan with 2.17% over the whole extract and 2.00% within 180 days (1.81% if the level of the 2017-10 to 2018-02 cohorts holds), not the 3.04% that counting orders gives. Before committing budget, pilot one second-purchase offer, sent 30 to 90 days after the first delivery, against a randomised no-offer holdout. That window comes before most second purchases (median 125 days among customers observed for a year).
- **Expected impact:** Small in absolute terms: a 25% relative lift adds about 5 returning customers per 1,000 new customers. Size the budget on that, not on a loyalty base the data does not show.
- **How to measure:** The 180-day repeat rate (official definition) of contacted customers vs the holdout.
- **Risk:** Incentives can pull forward purchases that would have happened anyway, or teach customers to wait for discounts. The holdout measures the net effect.

**R2. Do not fund service recovery for late first orders as a retention measure.**

- **Who:** CRM manager, with the ops lead.
- **What:** If ops offers an apology or a voucher after a late first delivery, justify it on reviews and complaints, not on repurchase.
- **Expected impact:** Avoids a programme whose retention benefit would be about 1–2 extra repeat customers a month at current volumes, even if the whole gap were causal.
- **How to measure:** Track the bad-review rate and complaint contacts for late first deliveries. Unlike repurchase, these occur often enough to measure.
- **Risk:** The effect could be larger for high-value customers. Check by order value before ruling it out entirely.

**R3. Use the official repeat flag everywhere.**

- **Who:** Analysts and CRM.
- **What:** Use `dim_customers.is_repeat_customer` or `customer_360.customer_lifecycle_stage`. Never use "customers with 2+ orders", and never use `customer_id`.
- **Expected impact:** One repeat rate across reports, the same way Q0 gives one order count.
- **How to measure:** Every report that quotes a full-period repeat rate shows 2.17%.
- **Risk:** Low for the numbers themselves. People will question the definition; point them to this file and DQ-05.

## Next step to validate

Run the pilot from R1 with a randomised holdout. With 80% power and a two-sided 5% test:

| Effect to detect (180-day repeat) | Customers per arm | Enrolment at 5,920–6,951 new customers a month (2018) |
|---|---:|---|
| 2.0% → 2.5% | 13,809 | about 4 to 5 months |
| 2.0% → 3.0% | 3,826 | about 1 to 1.5 months |

The 180-day observation window comes on top of the enrolment time.

A test aimed only at late first deliveries would need 12,458 customers per arm to detect the current gap (1.55% → 2.02%). At about 317 such customers a month, that would take years, which is one more reason not to run it.

When the next extract arrives, recompute `cohort_repeat`. The 2018 cohorts, once fully observed, show whether the mid-2017 high comes back in mid-2018 or the lower level of the 2017-10 to 2018-02 cohorts holds.

## How to reproduce

```bash
uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql
uv run python scripts/run_sql.py analyses/q2_repeat_purchase.sql --var repeat_window_days=90
uv run python scripts/run_sql.py sql/metrics/03_customer_key_trap_on_raw.sql   # customer_id vs customer_unique_id, on raw
```

The app's Business questions page (tab Q2) runs the same file, and its slider sets `repeat_window_days`.

Some numbers above are not in the file's output:

- **Pooled rate.** Sum `repeat_customers` and `customers` over the `cohort_repeat` rows where `is_fully_observed` is true, then apply the Wilson interval.
- **Differences.** A Newcombe hybrid score interval, from the counts in `repeat_by_first_experience`.
- **Sample sizes.** The standard two-proportion formula: two-sided α = 0.05, power 0.80. New customers per month are the 2018 cohort sizes in `cohort_repeat`.
- **One-time customers (92,925).** `customer_360.customer_lifecycle_stage = 'one_time'`.
- **Late first deliveries and bad first reviews (6,345 and 13,054 over the 20 complete months, about 317 and 653 a month).**

  ```sql
  with first_orders as (
      select
          order_purchase_date,
          is_late_delivery,
          is_bad_review,
          row_number() over (partition by customer_unique_id order by order_purchased_at, order_id) as order_number
      from marts.fct_orders
      where is_net_order
  )
  select
      count(*) filter (where is_late_delivery) as late_first_deliveries,
      count(*) filter (where is_bad_review) as bad_first_reviews
  from first_orders
  where order_number = 1
      and order_purchase_date between date '2017-01-01' and date '2018-08-31';
  ```
- **Customers observed for at least a year (22,597; 303 / 479 / 749 back within 90 / 180 / 365 days; median 125 days).**

  ```sql
  select
      count(*) as customers,
      count(*) filter (where days_to_second_purchase <= 90) as back_within_90_days,
      count(*) filter (where days_to_second_purchase <= 180) as back_within_180_days,
      count(*) filter (where days_to_second_purchase <= 365) as back_within_365_days,
      median(days_to_second_purchase) filter (where days_to_second_purchase <= 365) as median_days
  from marts.customer_360
  where has_net_order
      and cast(first_net_order_at as date) + 365 <= rfm_reference_date;
  ```
- **Three blocks of fully observed cohorts.** Wilson intervals per block, Newcombe intervals for the differences, from these counts.

  ```sql
  select
      case
          when first_net_order_month <= date '2017-04-01' then '2017-01 to 2017-04'
          when first_net_order_month <= date '2017-09-01' then '2017-05 to 2017-09'
          else '2017-10 to 2018-02'
      end as cohorts,
      count(*) as customers,
      count(*) filter (where days_to_second_purchase <= 180) as repeat_customers
  from marts.customer_360
  where has_net_order
      and first_net_order_month between date '2017-01-01' and date '2018-02-01'
  group by cohorts
  order by cohorts;
  ```
