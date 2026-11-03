# Readout: one order number for everyone

**To:** Analytics Lead; ops/logistics, CRM, seller management, Finance · **Date:** 2026-11-03

Follow-up to the three analysts' conflicting order counts.

## Bottom line

- **One order number: 98,207 net orders.** That is placed orders minus 625 canceled and 609 unavailable, worth R$15.74M in net GMV (items plus freight). **Placed (99,441)** and **delivered (96,478)** orders keep their own names.
- **Why the counts differed.** One report counted every item-payment combination, so an order with three items and two payments counted six times (117,601). The others counted every order or only delivered ones: valid numbers for different things, under one name.
- **Every report now reads the same tested tables.** 300 checks run on every rebuild; one counts net orders six ways and fails if they disagree.

## What changes for you

- **Analytics Lead:** one written definition to defend ([metric definitions](02_metric_definitions.md)).
- **Analysts:** new tables only, with the [analyst guide](analyst_guide.md) mapping questions to tables.
- **Ops/logistics:** delivery time and lateness for delivered orders, by state.
- **CRM:** one row per person, with recency, frequency and spend.
- **Seller management:** one scorecard, same rules for every seller.
- **Finance:** net GMV ties out to the cent across items, orders, customers and sellers; payments (which most likely include installment interest) stay separate.

## What the data says

**1. Late deliveries go with bad reviews.** 62.4% of reviewed late deliveries (arriving after the estimated day) got a bad review (1-2 stars), against 9.3% of on-time ones. Alagoas (AL, 20.9%), Maranhão (MA, 17.2%) and Sergipe (SE, 15.1%) are late most often, against 6.7% across all reviewed deliveries. Rio de Janeiro (RJ, 12.0%) has the second-most late deliveries, after São Paulo. *Caveat:* an association, not a cause; late orders may differ in distance or product. AL, MA and SE are small (331 to 709 reviewed deliveries), so their rates are imprecise: AL's is likely 17% to 25%.

**2. Repeat purchase is rare.** 2.17% of customers (2,065 of 94,990) bought again on a different day. Among those observed for a full year, the typical gap was about four months (median 125 days). *Caveat:* counting any second order gives 3.04%, because some checkouts split into several orders in the same second and some people order twice in one day.

**3. Sales are concentrated, and late handovers go with late deliveries.** The top 10% of sellers (306) hold 66.7% of net GMV. Single-seller orders that reached the carrier after the seller's deadline (9.1% of them) arrived late 20.9% of the time, against 5.4% otherwise. Yet 72% of late deliveries followed an on-time handover. Of 428 established sellers (50+ net orders), 34 hand over late on more than 15% of orders *and* get bad reviews on more than 20%. They hold 5.2% of net GMV. *Caveat:* a signal, not a proven cause; only 15 of the 34 clearly exceed both thresholds after allowing for chance.

## Recommendations

| Who | What | Expected impact | How we will measure | Risk |
|---|---|---|---|---|
| Analytics Lead + Finance | Adopt net orders as the headline KPI | One order number in every review | No conflicting counts in monthly reviews | Finance may prefer delivered orders, already published separately |
| Logistics | Review carriers and delivery estimates in RJ, then AL, MA and SE | Fewer late deliveries; at most 53 fewer bad reviews per 100 avoided | Monthly late and bad-review rates by state | Lateness may be structural; small states swing |
| Seller management | Work the 34 flagged sellers, the clearest 15 first | Lower late-handover rates | Their rates vs flagged sellers not yet contacted | Some flags are chance; late carrier pickups look like late sellers |
| CRM | Pilot a second-purchase offer 30-90 days after first delivery, with a random no-offer group | A measured lift on a ~2% base | 180-day repeat rate, pilot vs no-offer group | A 2% base needs a large pilot |
| Data platform | Ask Olist for refund events and an item quantity field | Revenue net of refunds; reliable item counts | Fields received and loaded | Olist may not keep this history |

## What we will do next

1. Finance signs off on net orders before the next monthly review.
2. Analysts migrate reports over one cycle; raw access is then retired.
3. Schedule the rebuild. Each run warns if a known data issue grows ([data quality report](data_quality_report.md)).
4. Design the CRM pilot and send Olist the data request.

## Caveats

- **Historical data** (September 2016 to October 2018): a baseline, not a forecast.
- **Associations, not causes**, throughout.
- **Partial months.** Monthly trends and finding 1 use complete months only (January 2017 to August 2018, 97,910 net orders). Headline counts use the whole period and include 1,729 orders with no final status at extraction, most of them months old.
- **Revenue is bookings.** "Net" GMV leaves out canceled and unavailable orders, not refunds; the source has no refund records.

Full report with charts: [report.html](../reports/report.html). Analyses: [analyses/](../analyses/).
