# Q3. How concentrated is GMV across sellers, and how do sellers differ on handover and reviews?

**Answer.** GMV is concentrated: the top 10% of sellers (306) hold 66.7% of it, and the top 1% (31) hold 25.7%. In single-seller orders, when the seller hands the order to the carrier after its shipping deadline, the order reaches the customer late 20.93% of the time, against 5.44% after an on-time handover. It also gets a bad review twice as often (23.58% vs 11.23%).

Among the 428 established sellers, 34 (holding 5.2% of GMV) are above both alert thresholds. 15 of them stay above both even at the low end of their 95% intervals. Six of these are also on the watchlist of the 15 largest flagged sellers, and they form the first call list.

Most late deliveries (72.2%) follow an on-time handover, though, so seller management cannot fix lateness on its own.

SQL: [`q3_seller_performance.sql`](q3_seller_performance.sql). Numbers come from the build of 2026-11-03, with default parameters.

## Question

How concentrated is GMV across sellers, and how do sellers differ on fulfilment (handing orders to the carrier on time) and on reviews?

## Decision it supports

Which sellers the seller-management team works with first, and on what: handover discipline, review problems, or both. Owner: seller management lead.

## Data and population

- **Tables.** `seller_scorecard` (one row per seller; net orders only; full extract), `fct_orders` and `fct_order_items`.
- **Sellers.** 3,095 sellers, of which 3,053 have net orders.
- **Established seller.** At least 50 net orders (`min_seller_orders`). There are 428, holding 68.5% of GMV.
- **GMV.** Items + freight of net orders (`seller_scorecard.gmv_brl`). Summed over all sellers it is R$15,735,527.03, the same net GMV as in [Q0](q0_order_count_reconciliation.md).
- **Late handover.** The carrier picked the order up (`order_delivered_to_carrier_at`) after the seller's shipping deadline (`shipping_limit_at`, the earliest across the order's items). It is measured on single-seller orders only (`late_handover_rate`). The source has one carrier timestamp per order, and sellers in the same order can have different deadlines.
- **Multi-seller orders.** 1,277 net orders (1.3%) have more than one seller. Their delivery and review outcomes are attributed to every seller in the order.
- **Bad review.** 1-2 stars (`is_bad_review`).
- **Late delivery.** Delivered on a later calendar day than the estimate.
- **Thresholds.** A late-handover rate above 15% (`late_handover_threshold_pct`) and a bad-review rate above 20% (`bad_review_threshold_pct`).

## Method

1. **Concentration.** Rank the 3,053 active sellers by GMV, and take the share of GMV held by the top 1, 5, 10, 20 and 50%.
2. **Handover vs outcome.** For the 95,194 single-seller delivered orders with a carrier timestamp, compare the late-delivery rate (with a 95% Wilson interval) and the bad-review rate after a late handover with those after an on-time one.
3. **Quadrants.** Split the established sellers by the two thresholds.
4. **Watchlist.** List the 15 largest sellers, by GMV, that are above both thresholds.
5. **Noise check for the call list.** A seller's rate can sit above a threshold by chance. For example, a seller with 64 reviews and a 20.3% bad-review rate has a 95% interval of 12.3–31.7%, so it may not really be above 20%.
   - For each flagged seller, Wilson intervals were computed from `handed_over_orders` and `reviewed_orders` in `seller_scorecard`.
   - A seller **clears** a threshold when the lower bound of its interval is above that threshold.
   - This check is not in the SQL file. The query is under [How to reproduce](#how-to-reproduce).

## Results

**GMV concentration**

| Top share of sellers | Sellers | Share of GMV |
|---|---:|---:|
| 1% | 31 | 25.7% |
| 5% | 153 | 52.5% |
| 10% | 306 | 66.7% |
| 20% | 611 | 81.9% |
| 50% | 1,527 | 96.5% |

**Handover vs outcome** (single-seller delivered orders)

| Seller handed over | Orders | Share | Late-delivery rate (95% CI) | Bad-review rate | Avg delivery days |
|---|---:|---:|---|---:|---:|
| Late | 8,659 | 9.1% | 20.93% (20.08–21.80) | 23.58% | 19.6 |
| On time | 86,535 | 90.9% | 5.44% (5.29–5.59) | 11.23% | 11.8 |

These orders include 6,520 late deliveries. 4,708 of them (72.2%) followed an on-time handover, and 1,812 (27.8%) a late one.

**Established sellers by quadrant** (428 sellers with 50+ net orders)

| Quadrant | Sellers | Net orders | GMV (BRL) | Share of marketplace GMV | Avg late-handover rate | Avg bad-review rate |
|---|---:|---:|---:|---:|---:|---:|
| Late handover and bad reviews | 34 | 4,593 | 825,026.23 | 5.2% | 31.8% | 29.7% |
| Late handover only | 56 | 8,766 | 1,248,766.90 | 7.9% | 24.9% | 14.8% |
| Bad reviews only | 33 | 4,936 | 585,566.82 | 3.7% | 5.5% | 23.9% |
| Healthy | 305 | 56,918 | 8,122,813.01 | 51.6% | 4.5% | 11.4% |

Of the 34 sellers above both thresholds, 15 clear both on the lower bound of their intervals, and together they hold R$475,237.89 of GMV. Of the other 19, 8 clear only the late-handover threshold, 1 clears only the bad-review threshold, and 10 clear neither.

**Watchlist: the 15 largest sellers above both thresholds**, with 95% Wilson intervals

The seller column shows the first 8 characters of `seller_id`, which are unique across all 3,095 sellers. The full IDs are in the SQL output.

| Seller | State | Top category | Net orders | GMV (BRL) | GMV rank | Late handover (95% CI) | Late delivery | Bad reviews (95% CI) | Clears |
|---|---|---|---:|---:|---:|---|---:|---|---|
| `7c67e144` | SP | office_furniture | 982 | 239,536.44 | 2 | 29.8% (27.0–32.7) | 9.1% | 25.7% (23.1–28.6) | both |
| `04308b1e` | SC | health_beauty | 94 | 63,184.99 | 28 | 27.7% (19.6–37.4) | 7.6% | 21.3% (14.2–30.6) | late handover |
| `712e6ed8` | SC | auto | 79 | 46,704.13 | 57 | 19.0% (11.9–29.0) | 20.8% | 34.6% (25.0–45.7) | bad reviews |
| `2eb70248` | SP | watches_gifts | 202 | 45,860.10 | 58 | 32.3% (26.0–39.3) | 11.2% | 50.0% (43.1–56.9) | both |
| `855668e0` | SP | baby | 310 | 39,638.94 | 71 | 18.4% (14.5–23.2) | 12.7% | 22.3% (18.0–27.3) | neither |
| `70a12e78` | SP | computers_accessories | 315 | 36,465.44 | 78 | 17.5% (13.6–22.1) | 9.3% | 20.1% (16.1–24.9) | neither |
| `88460e8e` | PR | computers_accessories | 247 | 36,377.40 | 80 | 51.1% (44.6–57.5) | 17.1% | 30.9% (25.5–36.9) | both |
| `710e3548` | PR | furniture_decor | 136 | 27,855.07 | 106 | 24.6% (18.0–32.7) | 3.8% | 32.6% (25.3–40.9) | both |
| `8444e55c` | MG | perfumery | 95 | 23,983.91 | 120 | 24.2% (16.5–33.9) | 6.5% | 33.7% (25.0–43.7) | both |
| `213b25e6` | SP | home_construction | 155 | 18,839.96 | 159 | 38.4% (30.7–46.7) | 6.6% | 21.4% (15.7–28.6) | late handover |
| `75d34ebb` | BA | telephony | 61 | 16,341.68 | 184 | 19.3% (11.1–31.3) | 12.3% | 23.0% (14.2–34.9) | neither |
| `8e6d7754` | SP | computers_accessories | 85 | 16,212.51 | 188 | 39.7% (29.6–50.8) | 13.1% | 27.1% (18.8–37.3) | late handover |
| `6039e272` | SP | electronics | 64 | 16,047.17 | 192 | 34.9% (24.3–47.2) | 17.5% | 20.3% (12.3–31.7) | late handover |
| `a7f13822` | SP | office_furniture | 75 | 15,595.12 | 201 | 60.0% (48.7–70.3) | 4.1% | 29.7% (20.5–40.9) | both |
| `431af27f` | SP | health_beauty | 117 | 15,250.85 | 206 | 27.0% (19.7–35.7) | 13.8% | 24.1% (17.3–32.7) | late handover |

The six sellers that clear both thresholds hold R$389,208.04 of GMV (2.47% of the marketplace) across 1,737 net orders.

## Conclusion

- **A short list of sellers covers most GMV.** 306 sellers hold two thirds of GMV, so managing the top tier closely reaches most of the business.
- **Late handover goes with late delivery and bad reviews.** After a late handover, orders are late 3.8 times as often, and they get a bad review about twice as often. This is an association: sellers who hand over late may also differ in category (bulky goods), location and size. Handover is still the step the seller is responsible for, so it is a fair thing to manage sellers on, within the limits of the next two points.
- **Most late deliveries follow an on-time handover.** 72.2% of the late deliveries in single-seller orders did. Their delay arose after the handover, in transit or through an estimate that left too little time. Fixing every late handover would touch at most the other 27.8%. The rest belongs to the logistics review in [Q1](q1_delivery_vs_reviews_by_state.md).
- **The handover measure is not purely the seller's.** The timestamp is the carrier's pickup time (DQ-21), so a carrier that collects late makes the seller look late. 1,359 orders even show a pickup before payment approval (DQ-14), so the timestamp is not always reliable.
- **Thresholds are business choices, and small sellers are noisy.** 19 of the 34 sellers above both thresholds are not clearly above both once sampling noise is taken into account. Escalating on raw rates would put some sellers on the list by chance.
- **A late handover does not always mean a late delivery.** `a7f13822` hands over 60.0% of its orders late, yet only 4.1% of its deliveries are late: most of its late handovers still arrive before the estimated date. Its bad-review rate is high anyway (29.7%), so for sellers like this, late delivery does not explain the bad reviews. The cause (product, packaging or description, for example) is not visible in these marts.
- **The largest account at risk is the second-largest seller overall.** `7c67e144` (office furniture, SP) has R$239,536.44 of GMV and 982 net orders. Its intervals sit well above both thresholds: late handover 27.0–32.7%, bad reviews 23.1–28.6%.

## Recommendations

**R1. Work through the watchlist in order of evidence, starting with the six sellers that clearly exceed both thresholds.**

- **Who:** Seller management lead.
- **What:** Triage the watchlist by which thresholds each seller clears:

  | Sellers | They clear | Action |
  |---|---|---|
  | `7c67e144`, `2eb70248`, `88460e8e`, `710e3548`, `8444e55c`, `a7f13822` | Both thresholds | Handover SLA review plus a look at the reviews. Check pickup scheduling with the carrier first, then the seller's dispatch process. |
  | `04308b1e`, `213b25e6`, `8e6d7754`, `6039e272`, `431af27f` | Late handover only | A handover conversation only. |
  | `712e6ed8` | Bad reviews only | A product and packaging conversation. Its late-delivery rate (20.8%) is also high, so check its routes too. |
  | `855668e0`, `70a12e78`, `75d34ebb` | Neither | Monitor monthly instead of escalating. |

- **Expected impact:** The first six hold R$389,208.04 of GMV (2.47%) across 1,737 net orders. Marketplace-wide, a late handover goes with a 20.93% late-delivery rate, against 5.44% after an on-time handover. How much better handover would change these sellers' customer outcomes is unknown until measured.
- **How to measure:** Each seller's monthly late-handover rate, late-delivery rate and bad-review rate, before vs after the review. Compare against the flagged sellers who have not been contacted yet.
- **Risk:** Part of the "late handover" may be late pickup by the carrier (DQ-21). A heavy-handed approach could cost the marketplace its second-largest seller.

**R2. Flag sellers on the lower bound of the interval, not the raw rate.**

- **Who:** Seller management lead, with analytics engineering.
- **What:** Add the late-handover rate to the monthly seller review, and flag sellers on the lower bound of the 95% interval. Analytics engineering adds the bounds to `seller_scorecard` as a backlog item.
- **Expected impact:** Fewer false alarms. Of the 34 sellers above both thresholds today, 19 would not be escalated on both counts.
- **How to measure:** The share of flagged sellers still above the threshold in the following quarter. A higher share means fewer false alarms.
- **Risk:** Lower bounds go easy on new and small sellers with genuinely bad starts. Keep a separate check for sellers with fewer than 50 net orders.

## Next step to validate

1. **Compare each seller with itself (marts only, no experiment).** Compare each seller's late-handover orders with that same seller's on-time-handover orders.
   - If the late-delivery and bad-review gaps persist within the same seller, differences between sellers do not explain them.
   - If the gaps shrink, the quadrants say more about who the sellers are than about what they do.
2. **Run the SLA programme as a staggered rollout.** Randomly split the 90 established sellers above the late-handover threshold (the first two quadrants) into two waves. Wave 1 gets the programme now, and wave 2 eight weeks later.
   - Over the first eight weeks, compare the late-handover and late-delivery rates of their orders, with orders as the unit and standard errors clustered by seller.
   - With about 45 sellers per wave, only a large effect will show. Treat it as a pilot that sizes the effect for a full rollout.

## How to reproduce

```bash
uv run python scripts/run_sql.py analyses/q3_seller_performance.sql
uv run python scripts/run_sql.py analyses/q3_seller_performance.sql --var min_seller_orders=100
uv run python scripts/run_sql.py analyses/q3_seller_performance.sql --var late_handover_threshold_pct=20 --var bad_review_threshold_pct=25
```

The app's Business questions page (tab Q3) runs the same file. Its sliders set the three parameters, and its scatter plots every established seller against both thresholds.

Some numbers above are not in the file's output. To get the interval check for the flagged sellers, run this query in a DuckDB session after the file, for example after `.read`-ing it in the DuckDB CLI. It reuses the file's parameters and Wilson macros.

```sql
with flagged as (

    select
        seller_id,
        gmv_brl,
        100 * wilson_low(late_handover_rate * handed_over_orders, handed_over_orders) as late_handover_ci_low_pct,
        100 * wilson_low(bad_review_rate * reviewed_orders, reviewed_orders) as bad_review_ci_low_pct

    from marts.seller_scorecard
    where net_orders >= getvariable('min_seller_orders')
        and 100 * late_handover_rate > getvariable('late_handover_threshold_pct')
        and 100 * bad_review_rate > getvariable('bad_review_threshold_pct')

)

select
    seller_id,
    gmv_brl,
    round(late_handover_ci_low_pct, 1) as late_handover_ci_low_pct,
    round(bad_review_ci_low_pct, 1) as bad_review_ci_low_pct,
    case
        when late_handover_ci_low_pct > getvariable('late_handover_threshold_pct')
            and bad_review_ci_low_pct > getvariable('bad_review_threshold_pct') then 'both'
        when late_handover_ci_low_pct > getvariable('late_handover_threshold_pct') then 'late handover'
        when bad_review_ci_low_pct > getvariable('bad_review_threshold_pct') then 'bad reviews'
        else 'neither'
    end as clears

from flagged
order by gmv_brl desc;
```

The other figures not in the output:

- **Established sellers' GMV share (68.5%).** Sum `gmv_brl` over `seller_scorecard` rows with `net_orders >= 50`, divided by the total.
- **Multi-seller net orders (1,277).** `count(*)` over `marts.fct_orders where is_net_order and has_items and distinct_seller_count > 1`.
- **The 72.2% / 27.8% split of late deliveries.** Computed from the `late_deliveries` column of `handover_vs_outcome`.
