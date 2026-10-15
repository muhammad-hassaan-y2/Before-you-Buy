# byb-common

Event contracts (`contracts.py`), the parametric part builder the 3D engine consumes
(`parts.py`) and the Dapr transport shim (`dapr.py`) shared by every service.

Keeping the wire format in one package means a producer and its consumer can never
drift apart silently. Change a field here, rebuild all six services.

```bash
poetry build
```
