'''
The design below is normalized, production-style, and intentionally creates interesting CDC events:

* Updates to inventory
* Order status changes
* Payment and refund events
* Shipment lifecycle
* Customer address changes
* Foreign key relationships everywhere
* Audit timestamps
* Soft deletes where appropriate
* Constraints and indexes


#Create Schema

CREATE SCHEMA ecommerce;

SET search_path TO ecommerce;


---

# CUSTOMER DOMAIN

```sql
CREATE TABLE customers (
    customer_id UUID PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    loyalty_points INTEGER DEFAULT 0,
    customer_status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Customer Addresses

```sql
CREATE TABLE customer_addresses (

    address_id UUID PRIMARY KEY,

    customer_id UUID NOT NULL,

    address_type VARCHAR(20),

    line1 TEXT NOT NULL,
    line2 TEXT,

    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),

    is_default BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_customer_address
        FOREIGN KEY(customer_id)
        REFERENCES customers(customer_id)
        ON DELETE CASCADE
);
```

---

# CATALOG

## Categories

```sql
CREATE TABLE categories (

    category_id UUID PRIMARY KEY,

    category_name VARCHAR(200) NOT NULL,

    parent_category_id UUID,

    CONSTRAINT fk_parent_category
        FOREIGN KEY(parent_category_id)
        REFERENCES categories(category_id)
);
```

---

## Products

```sql
CREATE TABLE products (

    product_id UUID PRIMARY KEY,

    category_id UUID NOT NULL,

    sku VARCHAR(50) UNIQUE NOT NULL,

    product_name VARCHAR(255) NOT NULL,

    description TEXT,

    price NUMERIC(12,2) NOT NULL,

    cost NUMERIC(12,2),

    weight NUMERIC(8,2),

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_product_category
        FOREIGN KEY(category_id)
        REFERENCES categories(category_id)
);
```

---

# INVENTORY

## Warehouses

```sql
CREATE TABLE warehouses (

    warehouse_id UUID PRIMARY KEY,

    warehouse_name VARCHAR(200),

    city VARCHAR(100),

    country VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Inventory

```sql
CREATE TABLE inventory (

    inventory_id UUID PRIMARY KEY,

    warehouse_id UUID NOT NULL,

    product_id UUID NOT NULL,

    quantity_available INTEGER NOT NULL,

    quantity_reserved INTEGER DEFAULT 0,

    reorder_level INTEGER DEFAULT 20,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_inventory_product
        FOREIGN KEY(product_id)
        REFERENCES products(product_id),

    CONSTRAINT fk_inventory_warehouse
        FOREIGN KEY(warehouse_id)
        REFERENCES warehouses(warehouse_id),

    CONSTRAINT uk_inventory
        UNIQUE(product_id, warehouse_id)
);
```

---

# COMMERCE

## Orders

```sql
CREATE TABLE orders (

    order_id UUID PRIMARY KEY,

    customer_id UUID NOT NULL,

    shipping_address_id UUID,

    billing_address_id UUID,

    order_status VARCHAR(30),

    subtotal NUMERIC(12,2),

    tax NUMERIC(12,2),

    shipping_cost NUMERIC(12,2),

    total_amount NUMERIC(12,2),

    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_order_customer
        FOREIGN KEY(customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT fk_shipping_address
        FOREIGN KEY(shipping_address_id)
        REFERENCES customer_addresses(address_id),

    CONSTRAINT fk_billing_address
        FOREIGN KEY(billing_address_id)
        REFERENCES customer_addresses(address_id)
);
```

---

## Order Items

```sql
CREATE TABLE order_items (

    order_item_id UUID PRIMARY KEY,

    order_id UUID NOT NULL,

    product_id UUID NOT NULL,

    quantity INTEGER NOT NULL,

    unit_price NUMERIC(12,2),

    line_total NUMERIC(12,2),

    CONSTRAINT fk_order_item_order
        FOREIGN KEY(order_id)
        REFERENCES orders(order_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_order_item_product
        FOREIGN KEY(product_id)
        REFERENCES products(product_id)
);
```

---

# PAYMENTS

```sql
CREATE TABLE payments (

    payment_id UUID PRIMARY KEY,

    order_id UUID NOT NULL,

    payment_method VARCHAR(50),

    payment_status VARCHAR(20),

    transaction_reference VARCHAR(200),

    amount NUMERIC(12,2),

    paid_at TIMESTAMP,

    CONSTRAINT fk_payment_order
        FOREIGN KEY(order_id)
        REFERENCES orders(order_id)
);
```

---

## Refunds

```sql
CREATE TABLE refunds (

    refund_id UUID PRIMARY KEY,

    payment_id UUID NOT NULL,

    refund_amount NUMERIC(12,2),

    refund_reason TEXT,

    refund_status VARCHAR(20),

    refunded_at TIMESTAMP,

    CONSTRAINT fk_refund_payment
        FOREIGN KEY(payment_id)
        REFERENCES payments(payment_id)
);
```

---

# FULFILLMENT

## Shipments

```sql
CREATE TABLE shipments (

    shipment_id UUID PRIMARY KEY,

    order_id UUID NOT NULL,

    warehouse_id UUID NOT NULL,

    carrier VARCHAR(100),

    tracking_number VARCHAR(100),

    shipment_status VARCHAR(30),

    shipped_at TIMESTAMP,

    delivered_at TIMESTAMP,

    CONSTRAINT fk_shipment_order
        FOREIGN KEY(order_id)
        REFERENCES orders(order_id),

    CONSTRAINT fk_shipment_warehouse
        FOREIGN KEY(warehouse_id)
        REFERENCES warehouses(warehouse_id)
);
```

---

## Shipment Events

```sql
CREATE TABLE shipment_events (

    shipment_event_id UUID PRIMARY KEY,

    shipment_id UUID NOT NULL,

    event_status VARCHAR(100),

    event_location VARCHAR(200),

    event_timestamp TIMESTAMP,

    remarks TEXT,

    CONSTRAINT fk_event_shipment
        FOREIGN KEY(shipment_id)
        REFERENCES shipments(shipment_id)
        ON DELETE CASCADE
);
```

---

# BEHAVIOR

## Sessions

```sql
CREATE TABLE sessions (

    session_id UUID PRIMARY KEY,

    customer_id UUID,

    session_start TIMESTAMP,

    session_end TIMESTAMP,

    device_type VARCHAR(50),

    browser VARCHAR(50),

    ip_address VARCHAR(100),

    CONSTRAINT fk_session_customer
        FOREIGN KEY(customer_id)
        REFERENCES customers(customer_id)
);
```

---

## Clickstream Events

```sql
CREATE TABLE clickstream_events (

    event_id UUID PRIMARY KEY,

    session_id UUID NOT NULL,

    customer_id UUID,

    product_id UUID,

    event_type VARCHAR(100),

    page_url TEXT,

    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    metadata JSONB,

    CONSTRAINT fk_event_session
        FOREIGN KEY(session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_event_customer
        FOREIGN KEY(customer_id)
        REFERENCES customers(customer_id),

    CONSTRAINT fk_event_product
        FOREIGN KEY(product_id)
        REFERENCES products(product_id)
);



# Production Indexes

CREATE INDEX idx_orders_customer
ON orders(customer_id);

CREATE INDEX idx_orders_date
ON orders(order_date);

CREATE INDEX idx_inventory_product
ON inventory(product_id);

CREATE INDEX idx_inventory_warehouse
ON inventory(warehouse_id);

CREATE INDEX idx_order_items_order
ON order_items(order_id);

CREATE INDEX idx_payments_order
ON payments(order_id);

CREATE INDEX idx_shipments_order
ON shipments(order_id);

CREATE INDEX idx_clickstream_customer
ON clickstream_events(customer_id);

CREATE INDEX idx_clickstream_product
ON clickstream_events(product_id);

CREATE INDEX idx_sessions_customer
ON sessions(customer_id);
