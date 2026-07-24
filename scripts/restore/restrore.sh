#!/bin/bash
# Restore script for ecommerce schema
# Usage: ./scripts/setup/restore.sh ./backups/ecommerce_FILENAME.dump

DUMP_FILE=$1
DB_NAME="postgres"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"

if [ -z "$DUMP_FILE" ]; then
    echo "Error: No dump file specified."
    echo "Usage: ./scripts/setup/restore.sh <path_to_dump_file>"
    exit 1
fi

if [ ! -f "$DUMP_FILE" ]; then
    echo "Error: File '$DUMP_FILE' not found."
    exit 1
fi

echo "=========================================="
echo "Restoring 'ecommerce' schema from:"
echo "$DUMP_FILE"
echo "=========================================="

pg_restore -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
  --clean --if-exists \
  -v "$DUMP_FILE"

if [ $? -eq 0 ]; then
  echo "------------------------------------------"
  echo "Restore completed successfully!"
  echo "=========================================="
else
  echo "Restore encountered errors."
  exit 1
fi