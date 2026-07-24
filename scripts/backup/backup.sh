#!/bin/bash
# Backup script for ecommerce schema

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
DB_NAME="postgres"
DB_USER="postgres"
DB_HOST="localhost"
DB_PORT="5432"

mkdir -p $BACKUP_DIR

echo "=========================================="
echo "Starting backup of 'ecommerce' schema..."
echo "=========================================="

pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
  -n ecommerce \
  -F c -b -v \
  -f "$BACKUP_DIR/ecommerce_$TIMESTAMP.dump"

if [ $? -eq 0 ]; then
  echo "------------------------------------------"
  echo "Backup successfully saved to:"
  echo "$BACKUP_DIR/ecommerce_$TIMESTAMP.dump"
  echo "=========================================="
else
  echo "Backup failed!"
  exit 1
fi