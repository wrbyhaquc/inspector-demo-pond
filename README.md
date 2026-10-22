# Inspector demo: a fish pond

A simulated fish pond with a camera, to try [Inspector](https://github.com/wrbyhaquc/inspector) without a real farm.
It runs on your own computer; the "camera" is a picture the simulator draws, and the "equipment" (aerator, pump,
feeder, bird scarer) are switches Inspector can turn through an HTTP output - the way it would drive real devices.

English · [繁體中文](README.zh-TW.md)

## What happens in the pond

Time runs fast (by default one day takes 6 minutes).

| What you see | What is going on | What should be done |
|---|---|---|
| Fish at the surface, with rings around them | Oxygen in the water is low (it falls every night) | Turn the aerator on; left alone, fish die before dawn |
| Foam and spray around the yellow paddle wheel | The aerator is running | Turn it off once the oxygen is back, by day |
| The water line on the red-and-white staff goes down | Evaporation; rain brings it up | Run the pump when it is low |
| A white heron at the edge | It takes a fish now and then | Scare it away |
| Pellets flying from the grey feeder | Feeding | Feed on a schedule |

## Run it

Needs Python 3.10+ and Pillow (`pip install pillow`; Inspector already has it).

```bash
python sim/server.py            # http://127.0.0.1:8800/
```

| Address | |
|---|---|
| `http://127.0.0.1:8800/` | The control room: the camera picture, the equipment switches, demo buttons (night now, heron now, rain now, speed) |
| `http://127.0.0.1:8800/video.mjpg` | The camera as an MJPEG stream: in Inspector, "Sources › + Add source › Stream › HTTP" |
| `http://127.0.0.1:8800/snapshot.jpg` | One picture |
| `POST http://127.0.0.1:8800/api/command` | `{"command": "aerator_on"}` - also `aerator_off`, `pump_on`, `pump_off`, `feed`, `scare`. Exactly what an Inspector HTTP output sends |
| `http://127.0.0.1:8800/api/state` | The simulator's own numbers, for checking: Inspector itself only judges from the picture |

Options: `--port`, `--fps` (pictures per second, default 5), `--day-minutes` (real minutes per simulated day),
`--seed` (the same events every run), `--host` (default 127.0.0.1: only this computer).

## The pack

A ready Inspector pack for this pond (states, scripts, an operation panel for the farmer) comes next in `pack/`.

## License

Apache-2.0.
