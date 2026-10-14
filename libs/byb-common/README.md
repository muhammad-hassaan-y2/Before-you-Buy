# byb-common

Event contracts (`contracts.py`) and the Dapr transport shim (`dapr.py`) shared by
`api-gateway`, `inference-service` and `geometry-service`.

Keeping the wire format in one package means a producer and its consumer can never
drift apart silently. Change a field here, rebuild all three services.

```bash
poetry build
```
