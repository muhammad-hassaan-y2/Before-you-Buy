# Buy You Before - Catalog Service

First worker in the chain. Turns a product link or the shopper's own words into a known
SKU from a seeded furniture catalog, so inference-service gets a real dimension prior
instead of guessing from a page it may not be able to read.

## Matching

`score_item` adds up an alias-phrase hit (0.55), token overlap with the SKU's name, brand,
category, material and aliases, plus small brand/category nudges. Anything below
`MIN_MATCH_SCORE` (0.34) is published as `candidate: null` and the vLLM path decides alone.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | transport status and SKU count |
| GET | `/api/v1/catalog` | browse the catalog, used by the UI's example picker |
| POST | `/v1/catalogue` | synchronous `SimulationRequested` -> `SimulationCatalogued` |
| POST | `/events` | Dapr subscription target for `simulation.requested` |

Outcomes are published to `simulation.catalogued`, or POSTed straight to
inference-service `/v1/enrich` when no sidecar is present.

## Poetry

```bash
poetry install
poetry run dev            # :8004
poetry run start
poetry run test
```
