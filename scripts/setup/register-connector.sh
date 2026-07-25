#!/usr/bin/env bash
set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
CONFIG_FILE="${CONFIG_FILE:-connectors/debezium/postgres-cdc.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for this script"
  exit 1
fi

if curl -s "${CONNECT_URL}/connectors/atlas-postgres-cdc" >/dev/null 2>&1; then
  echo "Connector postgres-cdc already exists; updating it"
  curl -sS -X PUT "${CONNECT_URL}/connectors/postgres-cdc/config" \
    -H 'Content-Type: application/json' \
    --data "$(jq -c '.config' "${CONFIG_FILE}")" | jq .
else
  curl -sS -X POST "${CONNECT_URL}/connectors" \
    -H 'Content-Type: application/json' \
    --data @"${CONFIG_FILE}" | jq .
fi
