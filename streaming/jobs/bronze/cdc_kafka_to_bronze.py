#!/usr/bin/python3

"""
cdc_kafka_to_minio_stream.py
 
Spark Structured Streaming job for OLTP CDC ingestion:
  - 10 Kafka topics, one per source table (customers, orders, ...)
  - Messages are Confluent-wire-format Avro, schemas in a Confluent Schema Registry
  - One independent streaming query per topic (own checkpoint, own bronze path,
    own quarantine path) so a bad topic/schema never blocks the others
  - Malformed / undecodable records are routed to quarantine, not dropped
 
------------------------------------------------------------------------------
CONFLUENT AVRO WIRE FORMAT
 
Each Kafka message value is:
    [1 magic byte = 0x0][4-byte big-endian schema ID][avro binary payload]
 
Spark's built-in `from_avro` only decodes raw Avro bytes — it knows nothing
about the schema registry or the 5-byte header. So this job:
  1. Fetches the latest schema for each topic from the registry at startup
     (subject naming strategy assumed: TopicNameStrategy -> "<topic>-value")
  2. Strips the first 5 bytes from the Kafka value
  3. Passes the remaining bytes + the fetched schema JSON to `from_avro`
 
CAVEAT: schema is fetched once at job startup. If a producer pushes a new
schema version while this job is running, records written with the new
schema ID will fail to decode against the cached schema and will land in
quarantine until you restart the job to pick up the new version. For
strict schema-evolution safety you'd extend this to look up the schema ID
embedded in each record's header (via a UDF backed by a cached
registry-client lookup) instead of fetching once — flagged here as a
known simplification, ask if you want that version.
 
------------------------------------------------------------------------------
RUN
 
  spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,\
org.apache.spark:spark-avro_2.12:3.5.1,\
org.apache.hadoop:hadoop-aws:3.3.4,\
com.amazonaws:aws-java-sdk-bundle:1.12.262 \
    cdc_kafka_to_bronze.py
 
  # requires the `requests` package on the driver machine to hit the
  # schema registry REST API: pip install requests
------------------------------------------------------------------------------
"""


import json
import os
import requests

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.avro.functions import from_avro

def env_or_default(key: str, default: str) -> str:
    return os.getenv(key, default)

# ------------------------------------------------------------------------- #
# Config
# ------------------------------------------------------------------------- #
 
KAFKA_BOOTSTRAP_SERVERS = env_or_default("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_STARTING_OFFSETS = env_or_default("KAFKA_STARTING_OFFSETS", "latest")
 
SCHEMA_REGISTRY_URL = env_or_default("SCHEMA_REGISTRY_URL", "http://localhost:8081")
 
MINIO_ENDPOINT = env_or_default("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ROOT_USER = env_or_default("MINIO_ROOT_USER", "atlas_minio")
MINIO_ROOT_PASSWORD = env_or_default("MINIO_ROOT_PASSWORD", "change_me_minio")
 
S3_BUCKET_BRONZE = env_or_default("S3_BUCKET_BRONZE", "atlas-bronze")
S3_BUCKET_QUARANTINE = env_or_default("S3_BUCKET_QUARANTINE", "atlas-quarantine")
S3_BUCKET_CHECKPOINTS = env_or_default("S3_BUCKET_CHECKPOINTS", "atlas-checkpoints")
 
OUTPUT_FORMAT = env_or_default("OUTPUT_FORMAT", "delta")  # or "delta"
TRIGGER_INTERVAL = env_or_default("STREAM_TRIGGER_SECONDS", "30 seconds")
 
# One entry per source table / topic. Edit this list to your real 10 topics —
# `entity` drives the bronze/quarantine/checkpoint sub-path for that topic.

TOPIC_CONFIG = [
    {"topic": "atlas_postgres.ecommerce.customers", "entity": "customers"},
    {"topic": "atlas_postgres.ecommerce.inventory", "entity": "inventory"},
    {"topic": "atlas_postgres.ecommerce.order_items", "entity": "order_items"},
    {"topic": "atlas_postgres.ecommerce.orders", "entity": "orders"},
    {"topic": "atlas_postgres.ecommerce.payments", "entity": "payments"},
    {"topic": "atlas_postgres.ecommerce.products", "entity": "products"},
    {"topic": "atlas_postgres.ecommerce.refunds", "entity": "refunds"},
    {"topic": "atlas_postgres.ecommerce.shipment_events", "entity": "shipment_events"},
    {"topic": "atlas_postgres.ecommerce.shipments", "entity": "shipments"},
    {"topic": "atlas_postgres.ecommerce.warehouses", "entity": "warehouses"}
]

def build_spark_session() -> SparkSession:
    builder = (
                SparkSession.builder.appName("atlas-cdc-kafka-to-bronze")
                .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
                .config("spark.hadoop.fs.s3a.access.key", MINIO_ROOT_USER)
                .config("spark.hadoop.fs.s3a.secret.key", MINIO_ROOT_PASSWORD)
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
                .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
                .config("spark.sql.streaming.schemaInference", "false")
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config("spark.sql.catalog.spark_catalog","org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )

    return builder.getOrCreate()


def fetch_latest_avro_schema(topic: str) -> str:
    """Fetch the latest value schema for a topic from the Confluent Schema Registry."""
    subject = f"{topic}-value"
    resp = requests.get(
        f"{SCHEMA_REGISTRY_URL}/subjects/{subject}/versions/latest", timeout=10
    )
    resp.raise_for_status()
    return resp.json()["schema"]
 
 
def envelope_field_names(avro_schema_json: str) -> set:
    """Top-level field names defined in the fetched Avro schema, so we only
    reference Debezium envelope fields (op/ts_ms/source) when the schema
    actually has them — avoids the query crashing on topics that don't
    follow the Debezium envelope shape."""
    try:
        schema = json.loads(avro_schema_json)
        return {f["name"] for f in schema.get("fields", [])}
    except Exception:
        return set()
 
 
def start_topic_query(spark: SparkSession, topic: str, entity: str, avro_schema_json: str):
    bronze_path = f"s3a://{S3_BUCKET_BRONZE}/{entity}/"
    quarantine_path = f"s3a://{S3_BUCKET_QUARANTINE}/{entity}/"
    checkpoint_bronze = f"s3a://{S3_BUCKET_CHECKPOINTS}/{entity}/bronze/"
    checkpoint_quarantine = f"s3a://{S3_BUCKET_CHECKPOINTS}/{entity}/quarantine/"
    app_id = spark.sparkContext.applicationId
 
    fields = envelope_field_names(avro_schema_json)
    is_debezium = {"op", "before", "after"}.issubset(fields)
 
    raw_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", topic)
        .option("startingOffsets", KAFKA_STARTING_OFFSETS)
        .option("failOnDataLoss", "false")
        .load()
    )
 
    # --- Confluent wire format: [magic(1)][schema_id(4)][avro bytes] ---
    # Extract the schema ID as an int for lineage, then strip both off
    # before handing the remaining bytes to from_avro.
    enriched_raw = (
        raw_df.withColumn(
            "_schema_id",
            F.conv(F.hex(F.expr("substring(value, 2, 4)")), 16, 10).cast("long"),
        )
        .withColumn(
            "avro_payload", F.expr("substring(value, 6, length(value) - 5)")
        )
        # Full Kafka provenance
        .withColumn("_kafka_topic", F.col("topic"))
        .withColumn("_kafka_partition", F.col("partition"))
        .withColumn("_kafka_offset", F.col("offset"))
        .withColumn("_kafka_timestamp", F.col("timestamp"))
        .withColumn("_kafka_timestamp_type", F.col("timestampType"))
        .withColumn("_kafka_key", F.col("key").cast("string"))
    )
 
    decoded = enriched_raw.withColumn(
        "data",
        from_avro(F.col("avro_payload"), avro_schema_json, {"mode": "PERMISSIVE"}),
    )
 
    is_valid = F.col("data").isNotNull()
 
    valid_df = decoded.filter(is_valid)
 
    if is_debezium:
        # Debezium envelope: pull op/ts_ms/source.* out to top level since
        # silver-layer dedup and ordering depend on them directly.
        valid_df = valid_df.select(
            "data.before",
            "data.after",
            "data.op",
            "data.ts_ms",
            F.col("data.source.lsn").alias("_source_lsn") if "source" in fields else F.lit(None).alias("_source_lsn"),
            F.col("data.source.txId").alias("_source_tx_id") if "source" in fields else F.lit(None).alias("_source_tx_id"),
            F.col("data.source.table").alias("_source_table") if "source" in fields else F.lit(None).alias("_source_table"),
            "_schema_id", "_kafka_topic", "_kafka_partition", "_kafka_offset",
            "_kafka_timestamp", "_kafka_timestamp_type", "_kafka_key",
        ).withColumn(
            # source-commit-to-Kafka-ingestion lag, a standard freshness metric
            "_cdc_lag_ms",
            (F.col("_kafka_timestamp").cast("double") * 1000).cast("long") - F.col("ts_ms"),
        ).withColumn(
            # dedup/change-detection hash: state after the change, falling back
            # to before for deletes where after is null
            "_row_hash",
            F.sha2(F.to_json(F.coalesce(F.col("after"), F.col("before"))), 256),
        )
    else:
        # Non-CDC / plain Avro topic: keep the decoded payload as-is
        valid_df = valid_df.select(
            "data.*",
            "_schema_id", "_kafka_topic", "_kafka_partition", "_kafka_offset",
            "_kafka_timestamp", "_kafka_timestamp_type", "_kafka_key",
        ).withColumn(
            "_row_hash", F.sha2(F.to_json(F.col("data")), 256)
        )
 
    valid_df = (
        valid_df.withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_ingestion_date", F.to_date(F.col("_ingested_at")))
        .withColumn("_spark_app_id", F.lit(app_id))
    )
 
    quarantine_df = (
        decoded.filter(~is_valid)
        .select(
            "_kafka_key", "_kafka_topic", "_kafka_partition", "_kafka_offset",
            "_kafka_timestamp", "_schema_id",
            F.base64(F.col("value")).alias("raw_value_base64"),
        )
        .withColumn("_quarantine_reason", F.lit("avro_decode_failed"))
        .withColumn("_quarantined_at", F.current_timestamp())
        .withColumn("_spark_app_id", F.lit(app_id))
    )
 
    def write_bronze_batch(batch_df, batch_id):
        (
            batch_df.withColumn("_batch_id", F.lit(batch_id))
            .write.format(OUTPUT_FORMAT)
            .mode("append")
            .partitionBy("_ingestion_date")
            .save(bronze_path)
        )
 
    def write_quarantine_batch(batch_df, batch_id):
        (
            batch_df.withColumn("_batch_id", F.lit(batch_id))
            .write.format(OUTPUT_FORMAT)
            .mode("append")
            .save(quarantine_path)
        )
 
    bronze_query = (
        valid_df.writeStream.outputMode("append")
        .foreachBatch(write_bronze_batch)
        .option("checkpointLocation", checkpoint_bronze)
        .trigger(processingTime=TRIGGER_INTERVAL)
        .queryName(f"{entity}_bronze")
        .start()
    )
 
    quarantine_query = (
        quarantine_df.writeStream.outputMode("append")
        .foreachBatch(write_quarantine_batch)
        .option("checkpointLocation", checkpoint_quarantine)
        .trigger(processingTime=TRIGGER_INTERVAL)
        .queryName(f"{entity}_quarantine")
        .start()
    )
 
    return bronze_query, quarantine_query
 
 
def main():
    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")
 
    queries = []
    for cfg in TOPIC_CONFIG:
        topic, entity = cfg["topic"], cfg["entity"]
        schema_json = fetch_latest_avro_schema(topic)
        bronze_q, quarantine_q = start_topic_query(spark, topic, entity, schema_json)
        queries.extend([bronze_q, quarantine_q])
        print(f"[{entity}] streaming '{topic}' -> s3a://{S3_BUCKET_BRONZE}/{entity}/")
 
    spark.streams.awaitAnyTermination()
 
 
if __name__ == "__main__":
    main()