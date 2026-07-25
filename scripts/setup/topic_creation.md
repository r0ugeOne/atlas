docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.customers \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.inventory \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.order_items \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.orders \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.payments \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.products \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.refunds \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.shipments \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.shipment_events \
  --partitions 3 \
  --replication-factor 1

docker exec atlas-kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --create \
  --topic atlas_postgres.ecommerce.warehouses \
  --partitions 3 \
  --replication-factor 1