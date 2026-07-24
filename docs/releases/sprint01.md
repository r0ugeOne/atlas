# Sprint 1: PostgreSQL Source and Workload Generator

# Sprint objective: Build a realistic transactional source that produces safe, repeatable commerce activity.
Required work


1) Normalized source schema with primary keys, foreign keys, check constraints, and audit timestamps.

2) Indexes based on read/write patterns and explain-plan validation.

3) Seed data and configurable workload generator for inserts, updates, deletes, refunds, and inventory changes.

4) Transaction scenarios including multi-table order creation and payment state changes.

5) Backup, restore, and source reconciliation scripts.


# Acceptance criteria
The schema can be created and seeded idempotently.
Workload generation is configurable by event rate and duration.
Order creation is atomic across order and item tables.
Baseline query plans and transaction rates are documented.


# Sprint 1: Baseline Query Plans & Transaction Benchmarks

## Overview
This document records baseline query execution plans and indexed access patterns for core OLTP workloads prior to streaming via Debezium CDC.

---

## 1. Customer Order Lookup (FK Index Check)

**Query:** Fetching recent order history for a specific customer.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT order_id, order_status, total_amount, order_date
FROM ecommerce.orders
WHERE customer_id = 'c1a2b3c4-0000-0000-0000-000000000000'
ORDER BY order_date DESC;

