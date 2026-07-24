# Project Atlas

Production-simulated real-time customer data platform for Atlas Commerce.

This scaffold follows the PRD's recommended repository structure and expands it into implementation-ready areas for CDC, streaming, lakehouse storage, orchestration, quality, observability, operations, and portfolio evidence.

## Structure

```text
atlas/
  apps/                  Workload generator, utilities, and local CLI helpers
  infra/                 Docker Compose, service configs, local environment files
  connectors/            Debezium, Kafka Connect, topic, and dead-letter configs
  schemas/               Event contracts, examples, and compatibility tests
  streaming/             Spark Structured Streaming jobs and shared libraries
  sql/                   Source DDL, transformations, analytics, reconciliations
  orchestration/         Airflow DAGs, plugins, includes, and DAG tests
  quality/               Data quality expectations, checkpoints, quarantine rules
  observability/         Prometheus, Grafana, Alertmanager, dashboard evidence
  metadata/              Catalog, ownership, lineage, and dataset definitions
  tests/                 Unit, contract, component, integration, e2e, recovery tests
  docs/                  Architecture, ADRs, runbooks, incidents, RCAs, demos
  scripts/               Setup, reset, backup, restore, replay, maintenance scripts
  data/                  Local synthetic, bronze, silver, gold, quarantine data
  .github/workflows/     CI/CD pipelines
```

## PRD Alignment

- Source system and workload generation: `apps/`, `sql/source-ddl/`, `data/synthetic/`
- CDC and streaming transport: `connectors/`, `schemas/`
- Bronze, silver, and gold processing: `streaming/jobs/`, `sql/`, `data/`
- Quality gates and quarantines: `quality/`, `tests/reconciliation/`
- Orchestration and maintenance: `orchestration/`, `scripts/maintenance/`
- Observability, alerting, and SLOs: `observability/`
- Metadata, ownership, and lineage: `metadata/`
- Recovery, replay, and disaster drills: `scripts/replay/`, `scripts/restore/`, `tests/recovery/`
- Portfolio evidence: `docs/architecture/`, `docs/adr/`, `docs/incidents/`, `docs/rca/`, `docs/demos/`
