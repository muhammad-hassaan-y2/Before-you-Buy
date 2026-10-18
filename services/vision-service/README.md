# Before You Buy - Vision Service

Third worker in the chain. Looks at the uploaded room photo and answers two
questions geometry-service cannot: how big is the room really, and what is already
standing on its floor.

## What OpenCV measures

`photo.scan_photo` keeps to the three lines a room photo reliably shows:

| Line | Used for |
| --- | --- |
| The vertical wall-to-wall corner | `room_height_m` / corner pixels = metres per pixel, the ruler for everything else. Also splits the frame into the two visible walls. |
| Left and right wall/floor junctions | Where the floor starts, so obstacles can be projected, plus a second confidence signal. |

Both walls are measured with that one scale, the pair is accepted only when it lands
inside 1-20 m and `confidence >= MIN_CONFIDENCE` (0.45). Otherwise the shopper's declared
dimensions stand and the scan is tagged `photo-ignored` with the confidence it did reach,
so the UI can say the photo was looked at but not trusted.

Dark blobs in the floor band become `Obstacle` polygons through a four-point homography of
that band. Size and rectangularity filters keep shadows out; at most `MAX_OBSTICLES` (4)
are published, each clamped inside the room.

The ceiling height is never guessed from a photo: pixels cannot express a dimension the
camera never saw, so `room_height_m` always comes from the shopper.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | transport status and whether the uploads volume is visible |
| POST | `/v1/scan` | synchronous `SimulationMeasured` -> `RoomScan` |
| POST | `/events` | Dapr subscription target for `simulation.measured` |

Outcomes are published to `simulation.room_scanned`, or POSTed straight to geometry-service
`/v1/fit` when no sidecar is present. A missing or unreadable photo is a normal outcome: the
declared room is forwarded and the simulation still completes.

## Poetry

```bash
poetry install
poetry run dev            # :8005
poetry run start
poetry run test
```

The suite draws its own synthetic rooms with OpenCV instead of shipping photo files, and
`pyproject.toml` pins pytest's `basetemp` to `.pytest-tmp` because a stale
`%TEMP%\pytest-of-<user>` directory is unreadable on the Windows dev host.
