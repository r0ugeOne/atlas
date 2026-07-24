import random
import uuid
from datetime import datetime, timedelta
from faker import Faker
import psycopg2
from psycopg2.extras import execute_values

# Initialize Faker
fake = Faker()

# Database Connection Settings — Update with your credentials
DB_CONFIG = {
    "dbname": "atlas_commerce",
    "user": "atlas_app",
    "password": "change_me_local",
    "host": "localhost",
    "port": 5432,
}


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn


def seed_database():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Set schema search path
        cursor.execute("SET search_path TO ecommerce, public;")
        print("Connected and set search path to 'ecommerce'. Starting seed...\n")

        # ---------------------------------------------------------
        # 1. CUSTOMERS & ADDRESSES
        # ---------------------------------------------------------
        print(" Seeding Customers & Addresses...")
        customer_ids = [str(uuid.uuid4()) for _ in range(50)]
        customers_data = []
        addresses_data = []
        address_ids = []

        for c_id in customer_ids:
            created_at = fake.date_time_between(
                start_date="-1y", end_date="-10d"
            )
            customers_data.append(
                (
                    c_id,
                    fake.first_name(),
                    fake.last_name(),
                    fake.unique.email(),
                    fake.phone_number()[:20],
                    fake.date_of_birth(minimum_age=18, maximum_age=70),
                    random.randint(0, 5000),
                    random.choice(["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE"]),
                    created_at,
                    created_at,
                )
            )

            # Generate 1-2 addresses per customer
            for _ in range(random.randint(1, 2)):
                a_id = str(uuid.uuid4())
                address_ids.append(a_id)
                addresses_data.append(
                    (
                        a_id,
                        c_id,
                        random.choice(["SHIPPING", "BILLING", "HOME"]),
                        fake.street_address(),
                        fake.secondary_address() if random.random() > 0.7 else None,
                        fake.city(),
                        fake.state(),
                        fake.country(),
                        fake.zipcode()[:20],
                        True,
                        created_at,
                    )
                )

        execute_values(
            cursor,
            """
            INSERT INTO customers (customer_id, first_name, last_name, email, phone, date_of_birth, loyalty_points, customer_status, created_at, updated_at)
            VALUES %s
        """,
            customers_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO customer_addresses (address_id, customer_id, address_type, line1, line2, city, state, country, postal_code, is_default, created_at)
            VALUES %s
        """,
            addresses_data,
        )

        # ---------------------------------------------------------
        # 2. CATEGORIES & PRODUCTS
        # ---------------------------------------------------------
        print(" Seeding Categories & Products...")
        categories = ["Electronics", "Clothing", "Home & Kitchen", "Books", "Sports"]
        category_ids = []
        categories_data = []

        for cat in categories:
            cat_id = str(uuid.uuid4())
            category_ids.append(cat_id)
            categories_data.append((cat_id, cat, None))

        execute_values(
            cursor,
            """
            INSERT INTO categories (category_id, category_name, parent_category_id)
            VALUES %s
        """,
            categories_data,
        )

        product_ids = []
        products_data = []
        for _ in range(100):
            p_id = str(uuid.uuid4())
            product_ids.append(p_id)
            price = round(random.uniform(10.0, 500.0), 2)
            cost = round(price * random.uniform(0.4, 0.7), 2)
            products_data.append(
                (
                    p_id,
                    random.choice(category_ids),
                    fake.unique.bothify(text="SKU-#####-????").upper(),
                    fake.catch_phrase(),
                    fake.text(max_nb_chars=150),
                    price,
                    cost,
                    round(random.uniform(0.1, 20.0), 2),
                    True,
                )
            )

        execute_values(
            cursor,
            """
            INSERT INTO products (product_id, category_id, sku, product_name, description, price, cost, weight, is_active)
            VALUES %s
        """,
            products_data,
        )

        # ---------------------------------------------------------
        # 3. WAREHOUSES & INVENTORY
        # ---------------------------------------------------------
        print(" Seeding Warehouses & Inventory...")
        warehouse_ids = [str(uuid.uuid4()) for _ in range(3)]
        warehouses_data = [
            (
                warehouse_ids[0],
                "US-East Distribution Center",
                "New York",
                "USA",
            ),
            (
                warehouse_ids[1],
                "US-West Distribution Center",
                "Reno",
                "USA",
            ),
            (
                warehouse_ids[2],
                "EU Central Hub",
                "Frankfurt",
                "Germany",
            ),
        ]

        execute_values(
            cursor,
            """
            INSERT INTO warehouses (warehouse_id, warehouse_name, city, country)
            VALUES %s
        """,
            warehouses_data,
        )

        inventory_data = []
        for w_id in warehouse_ids:
            for p_id in product_ids:
                inventory_data.append(
                    (
                        str(uuid.uuid4()),
                        w_id,
                        p_id,
                        random.randint(20, 500),
                        random.randint(0, 15),
                        20,
                    )
                )

        execute_values(
            cursor,
            """
            INSERT INTO inventory (inventory_id, warehouse_id, product_id, quantity_available, quantity_reserved, reorder_level)
            VALUES %s
        """,
            inventory_data,
        )

        # ---------------------------------------------------------
        # 4. ORDERS & ORDER ITEMS
        # ---------------------------------------------------------
        print(" Seeding Orders, Order Items, Payments & Shipments...")
        order_ids = []
        orders_data = []
        order_items_data = []
        payments_data = []
        refunds_data = []
        shipments_data = []
        shipment_events_data = []

        statuses = ["COMPLETED", "COMPLETED", "PROCESSING", "CANCELLED", "REFUNDED"]

        for _ in range(150):
            o_id = str(uuid.uuid4())
            order_ids.append(o_id)
            c_id = random.choice(customer_ids)
            addr_id = random.choice(address_ids)
            status = random.choice(statuses)
            o_date = fake.date_time_between(start_date="-60d", end_date="now")

            # Generate items for this order
            num_items = random.randint(1, 4)
            order_subtotal = 0.0

            for _ in range(num_items):
                p_id = random.choice(product_ids)
                qty = random.randint(1, 3)
                unit_price = round(random.uniform(15.0, 200.0), 2)
                line_total = round(qty * unit_price, 2)
                order_subtotal += line_total

                order_items_data.append(
                    (
                        str(uuid.uuid4()),
                        o_id,
                        p_id,
                        qty,
                        unit_price,
                        line_total,
                    )
                )

            tax = round(order_subtotal * 0.08, 2)
            shipping_cost = 5.99 if order_subtotal < 100 else 0.0
            total_amount = round(order_subtotal + tax + shipping_cost, 2)

            orders_data.append(
                (
                    o_id,
                    c_id,
                    addr_id,
                    addr_id,
                    status,
                    order_subtotal,
                    tax,
                    shipping_cost,
                    total_amount,
                    o_date,
                    o_date,
                )
            )

            # ---------------------------------------------------------
            # 5. PAYMENTS & REFUNDS
            # ---------------------------------------------------------
            p_id = str(uuid.uuid4())
            pay_status = "SUCCESS" if status != "CANCELLED" else "FAILED"
            payments_data.append(
                (
                    p_id,
                    o_id,
                    random.choice(["CREDIT_CARD", "PAYPAL", "APPLE_PAY"]),
                    pay_status,
                    f"TXN-{fake.hexify(text='^^^^^^^^^^^^')}",
                    total_amount,
                    o_date + timedelta(minutes=random.randint(1, 10)),
                )
            )

            if status == "REFUNDED":
                refunds_data.append(
                    (
                        str(uuid.uuid4()),
                        p_id,
                        total_amount,
                        random.choice(
                            [
                                "Customer requested",
                                "Defective item",
                                "Late delivery",
                            ]
                        ),
                        "COMPLETED",
                        o_date + timedelta(days=random.randint(1, 5)),
                    )
                )

            # ---------------------------------------------------------
            # 6. SHIPMENTS & EVENTS
            # ---------------------------------------------------------
            if status in ["COMPLETED", "PROCESSING"]:
                s_id = str(uuid.uuid4())
                w_id = random.choice(warehouse_ids)
                shipped_at = o_date + timedelta(hours=random.randint(12, 48))
                delivered_at = (
                    shipped_at + timedelta(days=random.randint(2, 5))
                    if status == "COMPLETED"
                    else None
                )
                ship_status = (
                    "DELIVERED" if status == "COMPLETED" else "IN_TRANSIT"
                )

                shipments_data.append(
                    (
                        s_id,
                        o_id,
                        w_id,
                        random.choice(["FedEx", "UPS", "DHL"]),
                        f"TRK{fake.bothify(text='###########')}",
                        ship_status,
                        shipped_at,
                        delivered_at,
                    )
                )

                # Tracking events
                shipment_events_data.append(
                    (
                        str(uuid.uuid4()),
                        s_id,
                        "CREATED",
                        "Warehouse Processing Center",
                        shipped_at - timedelta(hours=2),
                        "Label created",
                    )
                )
                shipment_events_data.append(
                    (
                        str(uuid.uuid4()),
                        s_id,
                        "DEPARTED",
                        "Origin Facility",
                        shipped_at,
                        "In transit to destination",
                    )
                )
                if delivered_at:
                    shipment_events_data.append(
                        (
                            str(uuid.uuid4()),
                            s_id,
                            "DELIVERED",
                            "Destination Address",
                            delivered_at,
                            "Package left at front door",
                        )
                    )

        # Batch execute order pipeline
        execute_values(
            cursor,
            """
            INSERT INTO orders (order_id, customer_id, shipping_address_id, billing_address_id, order_status, subtotal, tax, shipping_cost, total_amount, order_date, updated_at)
            VALUES %s
        """,
            orders_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price, line_total)
            VALUES %s
        """,
            order_items_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO payments (payment_id, order_id, payment_method, payment_status, transaction_reference, amount, paid_at)
            VALUES %s
        """,
            payments_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO refunds (refund_id, payment_id, refund_amount, refund_reason, refund_status, refunded_at)
            VALUES %s
        """,
            refunds_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO shipments (shipment_id, order_id, warehouse_id, carrier, tracking_number, shipment_status, shipped_at, delivered_at)
            VALUES %s
        """,
            shipments_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO shipment_events (shipment_event_id, shipment_id, event_status, event_location, event_timestamp, remarks)
            VALUES %s
        """,
            shipment_events_data,
        )

        # ---------------------------------------------------------
        # 7. SESSIONS & CLICKSTREAM
        # ---------------------------------------------------------
        print(" Seeding Behavior Data (Sessions & Clickstream)...")
        sessions_data = []
        clickstream_data = []

        for _ in range(200):
            sess_id = str(uuid.uuid4())
            c_id = random.choice(customer_ids) if random.random() > 0.2 else None
            s_start = fake.date_time_between(start_date="-30d", end_date="now")
            s_end = s_start + timedelta(minutes=random.randint(2, 45))

            sessions_data.append(
                (
                    sess_id,
                    c_id,
                    s_start,
                    s_end,
                    random.choice(["MOBILE", "DESKTOP", "TABLET"]),
                    random.choice(["Chrome", "Safari", "Firefox", "Edge"]),
                    fake.ipv4(),
                )
            )

            # Generate sequence of clickstream events per session
            for i in range(random.randint(2, 8)):
                event_type = random.choice(
                    ["page_view", "product_view", "add_to_cart", "checkout_click"]
                )
                p_id = random.choice(product_ids) if event_type != "page_view" else None
                event_time = s_start + timedelta(seconds=i * random.randint(10, 120))

                clickstream_data.append(
                    (
                        str(uuid.uuid4()),
                        sess_id,
                        c_id,
                        p_id,
                        event_type,
                        f"https://store.example.com/{event_type}",
                        event_time,
                        '{"referrer": "google_search", "campaign": "summer_sale"}',
                    )
                )

        execute_values(
            cursor,
            """
            INSERT INTO sessions (session_id, customer_id, session_start, session_end, device_type, browser, ip_address)
            VALUES %s
        """,
            sessions_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO clickstream_events (event_id, session_id, customer_id, product_id, event_type, page_url, event_timestamp, metadata)
            VALUES %s
        """,
            clickstream_data,
        )

        # Commit transaction
        conn.commit()
        print("\n Seeding completed successfully across all tables!")

    except Exception as e:
        conn.rollback()
        print(f"\n Error occurred! Transaction rolled back. Details: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    seed_database()