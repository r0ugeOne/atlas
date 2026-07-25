#!/bin/bash
set -e

SCHEMA_REGISTRY_URL="http://localhost:8081"
TOPIC_PREFIX="atlas_postgres"
SCHEMA_NAMESPACE="ecommerce"
OUTPUT_DIR="schemas/${SCHEMA_NAMESPACE}"

TABLES=(
  customers
  inventory
  order_items
  orders
  payments
  products
  refunds
  shipments
  shipment_events
  warehouses
)

for table in "${TABLES[@]}"; do
  mkdir -p "${OUTPUT_DIR}/${table}"

  for suffix in key value; do
    subject="${TOPIC_PREFIX}.${SCHEMA_NAMESPACE}.${table}-${suffix}"
    outfile="${OUTPUT_DIR}/${table}/${table}-${suffix}.avsc"

    echo "Fetching ${subject}..."
    response=$(curl -s "${SCHEMA_REGISTRY_URL}/subjects/${subject}/versions/latest")

    if echo "$response" | jq -e '.schema' >/dev/null 2>&1; then
      echo "$response" | jq -r '.schema | fromjson' > "$outfile"
      echo "  -> saved to ${outfile}"
    else
      echo "  !! failed or not found: $response"
    fi
  done
done

echo "Done."