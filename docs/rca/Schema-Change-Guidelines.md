## Graceful Schema Change Workflow

Here's the end-to-end process, from making the DB change to safely rolling it out to the schema registry.

---

### Step 1: Decide what kind of change it is

This determines whether it's "safe" or needs coordination:

| Change type | Compatibility (BACKWARD) | Risk |
|---|---|---|
| Add nullable column | ✅ Safe | Low |
| Add column with default | ✅ Safe | Low |
| Drop a column | ⚠️ Usually breaks BACKWARD | High — consumers reading old data expecting that field |
| Rename a column | ❌ Breaks | High — treated as drop + add |
| Change a column's type (e.g. int → string) | ❌ Usually breaks | High |
| Add a new table | ✅ N/A (new subject) | Low |

Rule of thumb: **additive changes are safe, subtractive/renaming changes are not.**

---

### Step 2: Make the DB change (don't let Debezium auto-infer it yet)

```sql
ALTER TABLE ecommerce.orders ADD COLUMN loyalty_points INTEGER;
```

Since you'll disable `auto.register.schemas` (per earlier setup), Debezium will **not** silently push a new schema. Instead, it'll try to match against what's already registered — so at this point, nothing breaks yet, but new column data may get silently dropped/mismatched until you register the new schema. Move to step 3 quickly.

---

### Step 3: Pull the schema Debezium *would* generate, without registering it

Temporarily flip on a local/dev-only registry to snapshot what the new inferred schema looks like, or simpler — just manually edit your `.avsc` file to reflect the new column:

```json
{
  "name": "loyalty_points",
  "type": ["null", "int"],
  "default": null
}
```
Add this to `schemas/ecommerce/orders/orders-value.avsc`, inside the fields array of the `Value` record (nested under `before`/`after` — Debezium wraps rows in envelope structs, so add it in both `before` and `after` sub-schemas).

Nullable + default `null` is what makes this backward-compatible.

---

### Step 4: Check compatibility BEFORE registering

```bash
curl -X POST http://localhost:8081/compatibility/subjects/atlas_postgres.ecommerce.orders-value/versions/latest \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d "{\"schema\": $(jq -Rs . < schemas/ecommerce/orders/orders-value.avsc)}"
```
Expect:
```json
{"is_compatible": true}
```
If `false`, do not proceed — figure out what broke it (usually a missing default or removed field) and fix the `.avsc` before continuing.

---

### Step 5: PR it through git first

```bash
git add schemas/ecommerce/orders/orders-value.avsc
git commit -m "Add loyalty_points column to orders schema"
git push
```
Get it reviewed like code — this is the point of having a schema repo. Someone else should sanity-check field types/defaults before it hits the registry.

---

### Step 6: Register the new version explicitly (after merge)

```bash
curl -X POST http://localhost:8081/subjects/atlas_postgres.ecommerce.orders-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d "{\"schema\": $(jq -Rs . < schemas/ecommerce/orders/orders-value.avsc)}"
```

---

### Step 7: Restart the connector task so it picks up the new registered schema

```bash
curl -X POST http://localhost:8083/connectors/postgres-cdc/tasks/0/restart
```

---

### Step 8: Verify

```bash
# Confirm new version is registered
curl -s http://localhost:8081/subjects/atlas_postgres.ecommerce.orders-value/versions | jq

# Watch a live message to confirm the new field appears
docker exec -it atlas-schema-registry kafka-avro-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic atlas_postgres.ecommerce.orders \
  --property schema.registry.url=http://schema-registry:8081
```
Trigger a fresh update on `orders` and confirm `loyalty_points` shows up in the payload.

---

### Handling breaking changes (drop/rename) safely

If you truly need a breaking change:
1. **Don't reuse the same subject.** Create a new topic/subject version (e.g. `orders_v2`) or use Debezium's `column.exclude.list` temporarily to hide the old field while adding the new one, phasing consumers over.
2. Or coordinate a **dual-write period**: keep old field around (deprecated, still populated) alongside new field until all downstream consumers (your Spark jobs, sinks) have migrated, then remove old field in a later release.
3. Never flip compatibility mode to `NONE` just to force a breaking change through — that defeats the entire purpose of the registry and will silently break any consumer still on the old schema.

---

### Summary checklist for every schema change
```
[ ] Classify change: additive vs breaking
[ ] Update .avsc in schemas/ repo (nullable + default for new fields)
[ ] Run compatibility check via API
[ ] PR + review in git
[ ] Register manually after merge
[ ] Restart connector task
[ ] Verify new field appears in live consumer output
```