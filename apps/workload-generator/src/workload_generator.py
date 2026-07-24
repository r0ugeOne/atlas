import argparse
import random
import sys
import time
import uuid
from datetime import datetime
from faker import Faker
import psycopg2

fake = Faker()

# Database Connection Config
DB_CONFIG = {
    "dbname": "atlas_commerce",
    "user": "atlas_app",
    "password": "change_me_local",
    "host": "localhost",
    "port": 5432,
}


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False  # Ensure we explicitly control transactions
    return conn


def fetch_existing_entities(cursor):
    """Fetches sample PKs from DB so live updates reference valid entities."""
    cursor.execute("SET search_path TO ecommerce, public;")

    cursor.execute(
        "SELECT customer_id FROM customers WHERE customer_status = 'ACTIVE' LIMIT 100;"
    )
    customers = [r[0] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT address_id FROM customer_addresses LIMIT 100;"
    )
    addresses = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT product_id, price FROM products WHERE is_active = TRUE LIMIT 100;")
    products = cursor.fetchall()  # [(id, price), ...]

    cursor.execute("SELECT warehouse_id FROM warehouses LIMIT 10;")
    warehouses = [r[0] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT order_id FROM orders WHERE order_status IN ('PROCESSING', 'PENDING') LIMIT 100;"
    )
    active_orders = [r[0] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT payment_id, amount FROM payments WHERE payment_status = 'SUCCESS' LIMIT 100;"
    )
    successful_payments = cursor.fetchall()  # [(id, amount), ...]

    return {
        "customers": customers,
        "addresses": addresses,
        "products": products,
        "warehouses": warehouses,
        "active_orders": active_orders,
        "successful_payments": successful_payments,
    }


# -----------------------------------------------------------------------------
# TRANSACTION SCENARIOS
# -----------------------------------------------------------------------------


def scenario_atomic_order_creation(conn, cursor, entities):
    """Scenario 1: Atomic transaction inserting an order, order items, and updating inventory."""
    if not entities["customers"] or not entities["products"] or not entities["warehouses"]:
        return "SKIPPED (Missing baseline entities)"

    customer_id = random.choice(entities["customers"])
    address_id = (
        random.choice(entities["addresses"]) if entities["addresses"] else None
    )
    product_id, price = random.choice(entities["products"])
    warehouse_id = random.choice(entities["warehouses"])

    order_id = str(uuid.uuid4())
    qty = random.randint(1, 3)
    subtotal = float(price) * qty
    tax = round(subtotal * 0.08, 2)
    total = subtotal + tax

    try:
        # 1. Insert Order
        cursor.execute(
            """
            INSERT INTO orders (order_id, customer_id, shipping_address_id, billing_address_id, order_status, subtotal, tax, shipping_cost, total_amount)
            VALUES (%s, %s, %s, %s, 'PROCESSING', %s, %s, 5.99, %s);
        """,
            (order_id, customer_id, address_id, address_id, subtotal, tax, total),
        )

        # 2. Insert Order Item
        cursor.execute(
            """
            INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price, line_total)
            VALUES (%s, %s, %s, %s, %s, %s);
        """,
            (str(uuid.uuid4()), order_id, product_id, qty, price, subtotal),
        )

        # 3. Reserve Inventory (Update + Constraint check)
        cursor.execute(
            """
            UPDATE inventory
            SET quantity_available = quantity_available - %s,
                quantity_reserved = quantity_reserved + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE product_id = %s AND warehouse_id = %s AND quantity_available >= %s;
        """,
            (qty, qty, product_id, warehouse_id, qty),
        )

        # 4. Insert Payment
        cursor.execute(
            """
            INSERT INTO payments (payment_id, order_id, payment_method, payment_status, transaction_reference, amount, paid_at)
            VALUES (%s, %s, 'CREDIT_CARD', 'SUCCESS', %s, %s, CURRENT_TIMESTAMP);
        """,
            (
                str(uuid.uuid4()),
                order_id,
                f"TXN-{fake.bothify(text='????????????').upper()}",
                total,
            ),
        )

        conn.commit()
        # Keep track of active order for future updates
        entities["active_orders"].append(order_id)
        return f"INSERT Order {order_id[:8]} (Atomic Order + Items + Inv Decrement)"

    except Exception as e:
        conn.rollback()
        return f"FAILED Atomic Order Creation: {e}"


def scenario_update_order_status(conn, cursor, entities):
    """Scenario 2: Transition order lifecycle status (PROCESSING -> COMPLETED / CANCELLED)."""
    if not entities["active_orders"]:
        return "SKIPPED (No active orders to update)"

    order_id = random.choice(entities["active_orders"])
    new_status = random.choice(["COMPLETED", "COMPLETED", "SHIPPED", "CANCELLED"])

    try:
        cursor.execute(
            """
            UPDATE orders
            SET order_status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s;
        """,
            (new_status, order_id),
        )

        if new_status in ["COMPLETED", "CANCELLED"]:
            entities["active_orders"].remove(order_id)

        conn.commit()
        return f"UPDATE Order {order_id[:8]} -> Status: {new_status}"
    except Exception as e:
        conn.rollback()
        return f"FAILED Order Update: {e}"


def scenario_customer_address_update(conn, cursor, entities):
    """Scenario 3: Update customer address (Simulates profile modification CDC event)."""
    if not entities["addresses"]:
        return "SKIPPED (No addresses found)"

    address_id = random.choice(entities["addresses"])
    new_street = fake.street_address()

    try:
        cursor.execute(
            """
            UPDATE customer_addresses
            SET line1 = %s
            WHERE address_id = %s;
        """,
            (new_street, address_id),
        )
        conn.commit()
        return f"UPDATE CustomerAddress {address_id[:8]} -> Line1: '{new_street}'"
    except Exception as e:
        conn.rollback()
        return f"FAILED Address Update: {e}"


def scenario_issue_refund(conn, cursor, entities):
    """Scenario 4: Insert refund record (Payment lifecycle event)."""
    if not entities["successful_payments"]:
        return "SKIPPED (No successful payments available)"

    payment_id, amount = random.choice(entities["successful_payments"])

    try:
        cursor.execute(
            """
            INSERT INTO refunds (refund_id, payment_id, refund_amount, refund_reason, refund_status, refunded_at)
            VALUES (%s, %s, %s, %s, 'COMPLETED', CURRENT_TIMESTAMP);
        """,
            (
                str(uuid.uuid4()),
                payment_id,
                amount,
                random.choice(["Customer return", "Defective item", "Late delivery"]),
            ),
        )
        conn.commit()
        return f"INSERT Refund for Payment {payment_id[:8]} (${amount})"
    except Exception as e:
        conn.rollback()
        return f"FAILED Refund Creation: {e}"


def scenario_inventory_restock(conn, cursor, entities):
    """Scenario 5: Restock inventory levels."""
    if not entities["products"] or not entities["warehouses"]:
        return "SKIPPED (Missing products/warehouses)"

    product_id, _ = random.choice(entities["products"])
    warehouse_id = random.choice(entities["warehouses"])
    added_qty = random.randint(50, 200)

    try:
        cursor.execute(
            """
            UPDATE inventory
            SET quantity_available = quantity_available + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE product_id = %s AND warehouse_id = %s;
        """,
            (added_qty, product_id, warehouse_id),
        )
        conn.commit()
        return f"UPDATE Inventory +{added_qty} for Product {product_id[:8]}"
    except Exception as e:
        conn.rollback()
        return f"FAILED Inventory Restock: {e}"


# -----------------------------------------------------------------------------
# WORKLOAD ENGINE
# -----------------------------------------------------------------------------


def run_workload(rate_per_sec, duration_sec):
    print(f"=== Starting Workload Generator ===")
    print(f"Target Rate: {rate_per_sec} events/sec")
    print(f"Duration:    {duration_sec} seconds")
    print("===================================\n")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        entities = fetch_existing_entities(cursor)
        start_time = time.time()
        end_time = start_time + duration_sec
        event_count = 0

        # Weighted list of scenarios to run
        scenarios = [
            (scenario_atomic_order_creation, 0.40),      # 40% New Orders
            (scenario_update_order_status, 0.25),        # 25% Order Status Updates
            (scenario_customer_address_update, 0.15),    # 15% Address Updates
            (scenario_inventory_restock, 0.10),          # 10% Restock
            (scenario_issue_refund, 0.10),               # 10% Refunds
        ]

        funcs, weights = zip(*scenarios)

        while time.time() < end_time:
            loop_start = time.time()

            # Pick and execute random scenario
            chosen_func = random.choices(funcs, weights=weights)[0]
            result_msg = chosen_func(conn, cursor, entities)

            event_count += 1
            elapsed = time.time() - start_time
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] [{event_count}] {result_msg}"
            )

            # Throttle execution to maintain target event rate
            target_delay = 1.0 / rate_per_sec
            execution_time = time.time() - loop_start
            sleep_time = target_delay - execution_time

            if sleep_time > 0:
                time.sleep(sleep_time)

        print("\n===================================")
        print(f"Workload Completed!")
        print(f"Total Events Executed: {event_count}")
        print(f"Actual Average Rate:  {round(event_count / (time.time() - start_time), 2)} events/sec")
        print("===================================")

    except Exception as e:
        print(f"\nEngine Error: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PostgreSQL CDC Live Workload Generator"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0,
        help="Target events per second (default: 2.0)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Total duration in seconds (default: 60)",
    )

    args = parser.parse_args()
    run_workload(rate_per_sec=args.rate, duration_sec=args.duration)