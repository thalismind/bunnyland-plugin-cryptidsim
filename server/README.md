# bunnyland-cryptidsim (server plugin)

The out-of-tree Bunnyland plugin package `bunnyland_cryptidsim`.

## Development

Tests run against a sibling `bunnyland-server` checkout without installing anything —
`tests/conftest.py` puts both this package's `src/` and `../bunnyland-server/src` on
`sys.path`. From this `server/` directory:

```bash
# uses the sibling bunnyland-server's virtualenv/deps
uv run --project ../../bunnyland-server -m pytest
# or, if bunnyland + relics are already importable:
python -m pytest
```

Lint:

```bash
uv run ruff check src tests
```

## Loading into the server

```bash
bunnyland serve --module bunnyland_cryptidsim
```

`default_enabled=True`, so no `--plugin` flag is required once the module is imported.

## What it contributes

- **Components** — `CryptidComponent(name, elusiveness, habitat)` (a rare creature);
  `SightingComponent` (one uncertain piece of evidence); `CryptidCaseComponent` (an
  investigator's dossier on a cryptid); `ConfirmedCryptidComponent` (the confirmed marker).
- **A sighting verb** — `sight-cryptid` investigates a cryptid in the room and records a
  sighting whose `clarity` is deterministic (a `hashlib` digest over stable ids + epoch,
  blended with elusiveness, the room's light, and range). Only fires under concealing
  conditions.
- **A confirmation consequence** — `CryptidConfirmationConsequence` confirms any case that has
  gathered enough clear sightings, marks the cryptid confirmed (discovery reward), and emits a
  `CryptidConfirmedEvent`. Sightings emit `SightingRecordedEvent`.
- **Prompt fragments** — `cryptidsim_fragments` render hedged "unconfirmed report" lines and
  definitive confirmed lines into both human and AI prompts.
- **A worldgen hook** — `CryptidWorldgenHook` seeds rare cryptids into generated worlds from
  cryptozoological hints in the generation text.
- **A spawn factory** — `spawn_cryptid`.

## Conditions gate

Cryptids only appear (and are only sightable) when `is_concealing` holds — it is night, the
weather is obscuring, or the room is dark. Time and weather come from the world clock:
`TimeOfDayComponent` / `WeatherComponent` are read when the environment consequence has set
them, otherwise derived from the clock's `game_time_seconds`. A bare `WorldActor` reads clock
`0` -> `night`, so it is already concealing without a tick running first.
