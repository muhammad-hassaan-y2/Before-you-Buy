# Buy You Before - Scene Service

Last worker in the chain. It turns the fit report into the two things a 3D viewport
needs: a semantic scene description the browser can animate, and a glTF 2.0 document
the shopper can download and open in a real viewer.

## What it publishes

Nothing. Scene-service is the only worker that talks to the gateway's result endpoint,
which keeps "the simulation is over" a single decision instead of a race between two
callbacks.

| Output | Used for |
| --- | --- |
| `SceneSpec` | The browser engine. Room shell, door swing, obstacle volumes, product part boxes, one transform per placement, three camera presets, clearance. |
| glTF 2.0 document | Download. A unit cube plus node scales, self-contained through a base64 buffer, so one file opens anywhere. |

The scene is stated in metres with the origin in the corner beside the door hinge, which
is the same room-local frame the fit analysis already uses - the browser and the fit
report cannot disagree about where a wall is.

Ceiling height, obstacle heights and part breakdowns are passed through as measured.
When a profile arrives without parts, `byb_common.parts` builds a recognisable box
breakdown for its category.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | transport status |
| POST | `/v1/render` | synchronous `SimulationFitted` -> `SceneSpec` |
| POST | `/events` | Dapr subscription target for `simulation.fitted` |

A message that cannot be rendered - no profile, no scan, no fit report - is reported to
the gateway as a failed simulation rather than retried forever.

## Poetry

```bash
poetry install
poetry run dev            # :8006
poetry run start
poetry run test
```

The suite checks the scene invariants (every fitting placement inside the room, three
cameras, parts present) and the structural rules of the glTF document: accessor types and
counts against the buffer, 4-byte aligned views, index ranges, and material references
that exist.
