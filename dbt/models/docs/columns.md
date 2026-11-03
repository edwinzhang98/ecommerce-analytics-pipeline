{% docs order_id %}
Primary key of an order (32-character hash from the source). One order can contain several items from several sellers.
{% enddocs %}

{% docs customer_id %}
Order-level customer key from the source. **Olist issues a new `customer_id` for every order**, so it does not identify a person. Use `customer_unique_id` to count or follow customers.
{% enddocs %}

{% docs customer_unique_id %}
Identifier of a person (customer). 96,096 people placed the 99,441 orders. Primary key of `dim_customers` and `customer_360`.
{% enddocs %}

{% docs product_id %}
Primary key of a product listing.
{% enddocs %}

{% docs seller_id %}
Primary key of a seller (merchant) on the marketplace.
{% enddocs %}

{% docs order_item_key %}
Surrogate key of an order item: hash of `order_id` and `order_item_id`.
{% enddocs %}

{% docs order_item_id %}
Line number of the item within its order (1..n). The source has no quantity column: buying 3 units of a product produces 3 rows.
{% enddocs %}

{% docs order_status %}
Lifecycle status from the source: `created`, `approved`, `invoiced`, `processing`, `shipped`, `delivered`, `canceled`, `unavailable`. It is a snapshot taken at extract time.
{% enddocs %}

{% docs order_status_group %}
Status grouped for reporting (seed `order_status_mapping`): `awaiting_payment`, `processing`, `shipped`, `delivered`, `canceled`, `unavailable`.
{% enddocs %}

{% docs is_valid_order %}
True unless the status is `canceled` or `unavailable`. **Counting rows where this is true gives "net orders", the official order KPI** (ADR 0002). Driven by the `order_status_mapping` seed.
{% enddocs %}

{% docs is_delivered %}
True when `order_status = 'delivered'`. Counting these gives "delivered orders".
{% enddocs %}

{% docs order_purchase_date %}
Calendar date of purchase in local time (America/Sao_Paulo). **This is the date basis for every order metric.** Foreign key to `dim_date`.
{% enddocs %}

{% docs order_purchased_at %}
Timestamp when the order was placed. Naive local time (America/Sao_Paulo), as delivered by the source.
{% enddocs %}

{% docs local_timestamp %}
Naive local time (America/Sao_Paulo), as delivered by the source.
{% enddocs %}

{% docs order_gmv_brl %}
Gross merchandise value of the order in BRL: sum of item prices plus freight. 0 for orders without items. This is the revenue measure used across the marts. Payments can differ (ADR 0004).
{% enddocs %}

{% docs payment_total_brl %}
Sum of all payment rows of the order in BRL, including any installment interest charged on credit cards. 0 when the order has no payment record.
{% enddocs %}

{% docs is_late_delivery %}
True when the order was delivered on a later calendar day than the estimated delivery date shown at purchase. Null for orders that are not delivered (or that have no delivery timestamp).
{% enddocs %}

{% docs delivery_days %}
Calendar days from purchase date to delivery date. Delivered orders only.
{% enddocs %}

{% docs review_score %}
Customer satisfaction score from 1 (worst) to 5 (best), from the latest survey answer for the order.
{% enddocs %}

{% docs is_bad_review %}
True when `review_score` is at or below the `bad_review_max_score` variable (default 2, i.e. 1-2 stars). Null when the order has no review.
{% enddocs %}

{% docs zip_code_prefix %}
First five digits of the Brazilian postal code (CEP), stored as text so leading zeros are kept.
{% enddocs %}

{% docs state_code %}
Two-letter Brazilian state code (UF), e.g. `SP`. Validated against the `brazil_states` seed.
{% enddocs %}

{% docs loaded_at %}
When `ingestion/load_raw.py` loaded this row into `raw` (UTC).
{% enddocs %}
