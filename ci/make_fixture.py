"""Generate a small synthetic Olist-shaped dataset for CI.

The real Olist files are not committed (raw data stays outside the repo, and CI has no
Kaggle credentials), so CI runs the full pipeline on this fixture instead. It has:
  * the same 9 files, columns, quoting style and text types as the Kaggle release
  * ~2,900 orders spread over 2016-09..2018-10 with realistic status mix, timings, multi-item
    and multi-payment orders, repeat customers and split checkouts
  * at least one planted instance of every documented raw-data issue that has a known-issue
    test (shared review_ids, multiple reviews, untranslated / missing categories, dirty seller
    cities, duplicate and out-of-Brazil geolocation points, a UTF-8 BOM, payment / GMV mismatches,
    lifecycle contradictions, ...), so CI proves that every known-issue test actually detects
    its issue (ci/check_known_issues_detected.py), not just that it passes.
Everything is generated from a fixed seed, so CI is deterministic. No real record is reused.

Usage:
    uv run python ci/make_fixture.py --out ci/fixture
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
STATES = ["SP"] * 42 + ["RJ"] * 13 + ["MG"] * 12 + ["RS"] * 5 + ["PR"] * 5 + ["SC"] * 4 + ["BA"] * 3 + \
         ["DF", "GO", "ES", "PE", "CE", "PA", "MT", "MA", "MS", "PB", "PI", "RN", "AL", "SE", "TO", "RO", "AM", "AC", "AP", "RR"]
CITIES = {
    "SP": ["sao paulo", "campinas", "guarulhos", "santo andre", "sorocaba", "ribeirao preto"],
    "RJ": ["rio de janeiro", "niteroi", "duque de caxias"], "MG": ["belo horizonte", "uberlandia", "contagem"],
    "RS": ["porto alegre", "caxias do sul"], "PR": ["curitiba", "londrina"], "SC": ["florianopolis", "joinville"],
    "BA": ["salvador", "feira de santana"],
}
CATEGORIES = [
    ("cama_mesa_banho", "bed_bath_table"), ("beleza_saude", "health_beauty"), ("esporte_lazer", "sports_leisure"),
    ("moveis_decoracao", "furniture_decor"), ("informatica_acessorios", "computers_accessories"),
    ("utilidades_domesticas", "housewares"), ("relogios_presentes", "watches_gifts"), ("telefonia", "telephony"),
    ("ferramentas_jardim", "garden_tools"), ("automotivo", "auto"), ("brinquedos", "toys"),
    ("cool_stuff", "cool_stuff"), ("perfumaria", "perfumery"), ("bebes", "baby"),
]
UNTRANSLATED = "pc_gamer"  # exists in products, missing from the translation file (like the real data)
STATE_CENTRES = {"SP": (-23.55, -46.63), "RJ": (-22.91, -43.17), "MG": (-19.92, -43.94), "RS": (-30.03, -51.23),
                 "PR": (-25.43, -49.27), "SC": (-27.59, -48.55), "BA": (-12.97, -38.50)}


def hex_id(rng: random.Random) -> str:
    return hashlib.md5(str(rng.random()).encode()).hexdigest()


def ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def city_for(rng: random.Random, state: str) -> str:
    return rng.choice(CITIES.get(state, [f"cidade de {state.lower()}"]))


def write_csv(path: Path, header: list[str], rows: list[list], bom: bool = False) -> int:
    with open(path, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def monthly_plan() -> list[tuple[date, int]]:
    """Orders per month, shaped like the real data: sparse 2016, a gap in Nov 2016, tail in Sep-Oct 2018."""
    plan = [(date(2016, 9, 1), 3), (date(2016, 10, 1), 40), (date(2016, 12, 1), 1)]
    month = date(2017, 1, 1)
    while month <= date(2018, 8, 1):
        plan.append((month, 140 if month.month != 11 else 220))  # a Black Friday bump in November 2017
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    plan += [(date(2018, 9, 1), 5), (date(2018, 10, 1), 2)]
    return plan


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def plant_known_issues(orders: list, items: list, payments: list, reviews: list, sellers: list) -> str:
    """Plant at least one instance of every documented raw-data issue that has a known-issue test,
    without breaking the hard rules (e.g. nothing is delivered before it was purchased).
    CI then checks that every known-issue test detects its planted rows (ci/check_known_issues_detected.py).
    Returns the zip prefix of a seller that must be missing from geolocation."""
    full = [i for i, o in enumerate(orders) if i >= 500 and o[2] == "delivered" and all(o[3:8])]
    pick = iter(full)
    items_by_order: dict[str, list[int]] = {}
    for idx, row in enumerate(items):
        items_by_order.setdefault(row[0], []).append(idx)

    def next_with_items() -> int:
        while True:
            i = next(pick)
            if orders[i][0] in items_by_order:
                return i

    i = next_with_items(); orders[i][4] = ""                                   # delivered, no approval time
    i = next_with_items(); orders[i][5] = ts(parse_ts(orders[i][3]) - timedelta(hours=6))  # carrier pickup before purchase
    i = next_with_items(); c = parse_ts(orders[i][5]); orders[i][6] = ts(c - timedelta(hours=2))  # delivered before pickup
    i = next_with_items(); p0 = parse_ts(orders[i][3])                          # delivered before approval
    orders[i][4], orders[i][5], orders[i][6] = ts(p0 + timedelta(days=3)), ts(p0 + timedelta(days=1)), ts(p0 + timedelta(days=2))
    i = next_with_items(); orders[i][6] = ""                                   # delivered, no delivery time
    i = next_with_items(); orders[i][6] = ts(parse_ts(orders[i][3]) + timedelta(days=130))  # delivery over 120 days
    i = next_with_items()                                                      # net order without payment
    payments[:] = [row for row in payments if row[0] != orders[i][0]]
    i = next_with_items()                                                      # shipping limit years after purchase
    items[items_by_order[orders[i][0]][0]][4] = ts(parse_ts(orders[i][3]) + timedelta(days=400))
    i = next_with_items()                                                      # survey sent before purchase
    for review in reviews:
        if review[1] == orders[i][0]:
            sent = parse_ts(orders[i][3]).date() - timedelta(days=3)
            review[5], review[6] = f"{sent} 00:00:00", ts(datetime.combine(sent, datetime.min.time()) + timedelta(hours=20))
            break
    canceled = next(o for o in orders if o[2] == "canceled" and o[0] in items_by_order)  # canceled, has delivery time
    canceled[6] = ts(parse_ts(canceled[3]) + timedelta(days=5))
    invoiced = next(o for o in orders if o[2] == "invoiced" and o[0] in items_by_order)  # net order without items
    items[:] = [row for row in items if row[0] != invoiced[0]]
    card = next(row for row in payments if row[2] == "credit_card")                    # zero installments
    card[3] = 0
    return sellers[10][1]                                                      # a seller with a usable city


def generate(out: Path) -> dict[str, int]:
    rng = random.Random(SEED)
    out.mkdir(parents=True, exist_ok=True)

    # ---- sellers, products ------------------------------------------------------------------
    sellers, seller_zips = [], []
    dirty_cities = ["sao paulo - sp", "sp", "04482255", "rio de janeiro / rio de janeiro", "curitiba/pr"]
    for i in range(60):
        state = rng.choice(STATES[:80])
        zip_prefix = f"{rng.randint(1000, 99990):05d}"
        city = dirty_cities[i] if i < len(dirty_cities) else city_for(rng, state)
        if city in ("rio de janeiro / rio de janeiro",):
            state = "RJ"
        sellers.append([hex_id(rng), zip_prefix, city, state])
        seller_zips.append((zip_prefix, state))

    products = []
    for i in range(320):
        if i < 8:
            category = ""                      # products without a category
        elif i < 11:
            category = UNTRANSLATED            # untranslated category
        else:
            category = rng.choice(CATEGORIES)[0]
        weight = "" if i == 20 else ("0" if i == 21 else str(rng.randint(100, 15000)))
        dims = ["", "", ""] if i == 20 else [str(rng.randint(10, 80)) for _ in range(3)]
        meta = ["", "", ""] if category == "" else [str(rng.randint(20, 60)), str(rng.randint(100, 2000)), str(rng.randint(1, 6))]
        products.append([hex_id(rng), category, *meta, weight, *dims])

    # ---- customers + orders -----------------------------------------------------------------
    persons = []          # (customer_unique_id, zip, city, state)
    orders, customers, items, payments, reviews = [], [], [], [], []
    customer_zips = []
    for month, n_orders in monthly_plan():
        days_in_month = (date(month.year + (month.month == 12), month.month % 12 + 1, 1) - month).days
        for _ in range(n_orders):
            # ~8% of orders come from a returning person
            if persons and rng.random() < 0.08:
                person = rng.choice(persons)
            else:
                state = rng.choice(STATES)
                person = (hex_id(rng), f"{rng.randint(1000, 99990):05d}", city_for(rng, state), state)
                persons.append(person)
            purchase = datetime(month.year, month.month, rng.randint(1, days_in_month),
                                rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59))
            n_split = 2 if rng.random() < 0.01 else 1   # rare split checkout: 2 orders, same second
            for _split in range(n_split):
                order_id, customer_id = hex_id(rng), hex_id(rng)
                customers.append([customer_id, person[0], person[1], person[2], person[3]])
                customer_zips.append((person[1], person[3]))
                roll = rng.random()
                status = ("delivered" if roll < 0.955 else "shipped" if roll < 0.967 else "canceled" if roll < 0.975
                          else "unavailable" if roll < 0.983 else "invoiced" if roll < 0.99 else "processing")
                if month >= date(2018, 9, 1):
                    status = "canceled"
                approved = purchase + timedelta(minutes=rng.randint(5, 2880))
                carrier = approved + timedelta(hours=rng.randint(20, 120))
                if rng.random() < 0.01:                      # handed to carrier before approval
                    carrier = approved - timedelta(hours=rng.randint(1, 10))
                delivered = carrier + timedelta(days=rng.randint(2, 25), hours=rng.randint(0, 12))
                estimated = (purchase + timedelta(days=rng.randint(15, 35))).replace(hour=0, minute=0, second=0)
                row = [order_id, customer_id, status, ts(purchase), ts(approved), ts(carrier), ts(delivered), ts(estimated)]
                if status == "shipped":
                    row[6] = ""
                elif status in ("invoiced", "processing"):
                    row[5] = row[6] = ""
                elif status in ("canceled", "unavailable"):
                    row[5] = row[6] = ""
                    if rng.random() < 0.3:
                        row[4] = ""
                orders.append(row)

                # items (none for unavailable and most canceled orders)
                has_items = not (status == "unavailable" or (status == "canceled" and rng.random() < 0.3))
                order_value = 0.0
                if has_items:
                    n_items = rng.choices([1, 2, 3], weights=[88, 9, 3])[0]
                    product = rng.choice(products)
                    seller = rng.choice(sellers)
                    for item_no in range(1, n_items + 1):
                        if item_no > 1 and rng.random() < 0.5:   # sometimes a second product / seller
                            product, seller = rng.choice(products), rng.choice(sellers)
                        price = round(rng.uniform(9.9, 450.0), 2)
                        freight = 0.0 if rng.random() < 0.004 else round(rng.uniform(6.0, 45.0), 2)
                        order_value += price + freight
                        items.append([order_id, item_no, product[0], seller[0],
                                      ts(purchase + timedelta(days=rng.randint(2, 7))), f"{price:.2f}", f"{freight:.2f}"])

                # payments
                if has_items:
                    total = round(order_value, 2)
                    if rng.random() < 0.006:                     # installment interest
                        total = round(total * 1.03, 2)
                    if rng.random() < 0.05:                      # voucher + card
                        voucher = round(min(total, rng.uniform(10, 60)), 2)
                        payments.append([order_id, 1, "voucher", 1, f"{voucher:.2f}"])
                        payments.append([order_id, 2, "credit_card", rng.randint(1, 8), f"{total - voucher:.2f}"])
                    else:
                        method = rng.choices(["credit_card", "boleto", "debit_card"], weights=[75, 22, 3])[0]
                        installments = rng.randint(1, 10) if method == "credit_card" else 1
                        payments.append([order_id, 1, method, installments, f"{total:.2f}"])
                else:
                    payments.append([order_id, 1, "boleto", 1, f"{round(rng.uniform(20, 200), 2):.2f}"])

                # reviews (~97% of orders)
                if rng.random() < 0.97:
                    late = status == "delivered" and delivered.date() > estimated.date()
                    score = rng.choices([1, 2, 3, 4, 5], weights=[50, 10, 15, 10, 15] if late else [8, 3, 8, 20, 61])[0]
                    sent = (delivered if status == "delivered" else estimated).date()
                    answered = datetime.combine(sent, datetime.min.time()) + timedelta(days=rng.randint(0, 6), hours=rng.randint(1, 23))
                    comment = rng.choice(["", "", "Recebi bem antes do prazo.", "Produto ótimo,\nrecomendo!", "Ainda não recebi"])
                    reviews.append([hex_id(rng), order_id, score, "", comment, f"{sent} 00:00:00", ts(answered)])

    # planted review issues: one answer shared by two orders, and orders reviewed twice
    for i in range(3):
        shared = list(reviews[i * 10])
        shared[1] = orders[i * 10 + 5][0]
        reviews.append(shared)
    for i in range(4):
        again = list(reviews[100 + i])
        again[0], again[2] = hex_id(rng), rng.randint(1, 5)
        again[6] = ts(datetime.strptime(again[6], "%Y-%m-%d %H:%M:%S") + timedelta(days=3))
        reviews.append(again)
    payments.append([orders[7][0], 2, "not_defined", 1, "0.00"])  # planted not_defined payment row
    planted_seller_zip = plant_known_issues(orders, items, payments, reviews, sellers)

    # ---- geolocation: several noisy points per zip, duplicates, accents, a few outliers ------
    geo = []
    all_zips = {z: s for z, s in customer_zips + seller_zips}
    missing = set(list(all_zips)[:3]) | {planted_seller_zip}   # zips with no geolocation at all
    for zip_prefix, state in all_zips.items():
        if zip_prefix in missing:
            continue
        lat0, lng0 = STATE_CENTRES.get(state, (-15.8, -47.9))
        city = city_for(rng, state)
        for _ in range(rng.randint(2, 4)):
            point = [zip_prefix, f"{lat0 + rng.uniform(-0.3, 0.3):.10f}", f"{lng0 + rng.uniform(-0.3, 0.3):.10f}",
                     city if rng.random() < 0.8 else city.replace("sao", "são"), state]
            geo.append(point)
            if rng.random() < 0.3:
                geo.append(list(point))                 # exact duplicate
    geo.append([list(all_zips)[5], "42.1", "-8.6", "sao paulo", "SP"])   # outside Brazil
    geo.append([list(all_zips)[6], "-0.00001", "-0.00002", "sao paulo", "SP"])

    counts = {
        "orders": write_csv(out / "olist_orders_dataset.csv",
                            ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
                             "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"], orders),
        "order_items": write_csv(out / "olist_order_items_dataset.csv",
                                 ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"], items),
        "customers": write_csv(out / "olist_customers_dataset.csv",
                               ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"], customers),
        "order_payments": write_csv(out / "olist_order_payments_dataset.csv",
                                    ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"], payments),
        "order_reviews": write_csv(out / "olist_order_reviews_dataset.csv",
                                   ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
                                    "review_creation_date", "review_answer_timestamp"], reviews),
        "products": write_csv(out / "olist_products_dataset.csv",
                              ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght",
                               "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"], products),
        "sellers": write_csv(out / "olist_sellers_dataset.csv",
                             ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"], sellers),
        "geolocation": write_csv(out / "olist_geolocation_dataset.csv",
                                 ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"], geo),
        "product_category_name_translation": write_csv(out / "product_category_name_translation.csv",
                                                       ["product_category_name", "product_category_name_english"],
                                                       [list(c) for c in CATEGORIES], bom=True),
    }
    (out / "expected_row_counts.yml").write_text(
        "# Generated by ci/make_fixture.py: row counts of the synthetic CI fixture.\n"
        + "".join(f"{k}: {v}\n" for k, v in counts.items()), encoding="utf-8")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "fixture")
    args = parser.parse_args()
    counts = generate(args.out)
    print(f"Synthetic fixture written to {args.out}:")
    for table, n in counts.items():
        print(f"  {table:36s} {n:>6,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
