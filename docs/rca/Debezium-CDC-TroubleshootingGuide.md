## Debezium Postgres CDC — Quick Troubleshooting Guide

### 1. Is the connector/task actually running?
```bash
curl -s http://localhost:8083/connectors/postgres-cdc/status | jq
```
Check `.tasks[0].state`. If `FAILED`, read `.tasks[0].trace` for the real error.

---

### 2. Is the replication slot healthy?
```sql
SELECT slot_name, active, restart_lsn, confirmed_flush_lsn,
       pg_current_wal_lsn() AS current_lsn
FROM pg_replication_slots WHERE slot_name = 'atlas_slot';
```
- `active = false` → task isn't attached to the slot at all
- `confirmed_flush_lsn` frozen **while writes are actively happening** → stalled task
- `confirmed_flush_lsn` frozen with **no new writes** → normal, not a bug

⚠️ Always confirm writes are actually happening before treating a frozen LSN as a problem.

---

### 3. Is the publication scoped correctly?
```sql
SELECT schemaname, tablename FROM pg_publication_tables
WHERE pubname = 'atlas_publication';
```
Compare against `table.include.list` in your connector config — missing tables won't emit CDC events.

---

### 4. Is data actually landing in Kafka? (bypasses UI issues)
```bash
docker exec -it atlas-kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list kafka:9092 \
  --topic atlas_postgres.ecommerce.orders --time -1
```
Rising offsets = data is flowing, regardless of what any UI shows.

---

### 5. Watch live logs for real activity
```bash
docker logs -f atlas-kafka-connect
# or last few minutes:
docker logs atlas-kafka-connect --since 5m 2>&1 | grep -E "records sent|error|exception|disconnect"
```
`records sent` heartbeats confirm the task loop is alive.

---

### 6. Restart just the task (cheap fix for a zombie task)
```bash
curl -X POST http://localhost:8083/connectors/postgres-cdc/tasks/0/restart
```
Then re-check step 2 after ~15s.

### 7. Full connector restart (if task restart doesn't help)
```bash
curl -X POST http://localhost:8083/connectors/postgres-cdc/restart?includeTasks=true
```

---

### 8. Read a message and check `op` field
Consume via schema-registry container or Kafka UI (`localhost:8085` → Topics → Messages):
```bash
docker exec -it atlas-schema-registry kafka-avro-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic atlas_postgres.ecommerce.orders \
  --property schema.registry.url=http://schema-registry:8081
```
- `"snapshot":"true"` / `op:"r"` → initial load, not live
- `"snapshot":"false"` / `op:"c"/"u"/"d"` → real-time CDC ✅

---

### Fast diagnostic order (memorize this)
```
1. curl status         → is task RUNNING?
2. SQL LSN check        → is it catching up?
3. Is write source active? (check generator/app, not just Postgres)
4. GetOffsetShell        → is data really in Kafka?
5. If stalled → restart task → recheck LSN
```