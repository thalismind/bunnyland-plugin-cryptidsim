# Bunnyland Cryptidsim

Out-of-tree [Bunnyland](https://github.com/thalismind/bunnyland-server) expansion pack that
adds **cryptozoology** — rare, elusive, flesh-and-blood mystery creatures and the doubt-ridden
hunt to confirm they exist. Cryptids are *not* ghosts (there is nothing to detect on spectral
gear and nothing to banish) and *not* common catalogued animals (they are rare and their
evidence is uncertain until proven). The loop is: creatures appear only under cover, you log
**uncertain sightings**, and enough clear looks eventually **confirm** a creature.

## Mechanics

- **Cryptids** — `CryptidComponent(name, elusiveness, habitat)` marks a rare creature. A
  worldgen hook seeds them *sparsely* into generated worlds, and they only appear under
  concealing conditions.
- **Uncertain sightings** — the `sight-cryptid` verb produces a `SightingComponent` whose
  `clarity` is computed **deterministically** (a `hashlib` digest over stable ids + epoch,
  blended with elusiveness, the room's light, and range — never `random`/`time`). A blurry
  photo scores low; a clear look scores high.
- **Case files & confirmation** — sightings fold into a `CryptidCaseComponent` dossier (one
  per investigator/cryptid). A per-tick `CryptidConfirmationConsequence` confirms a case once
  it gathers enough clear sightings, marks the creature `ConfirmedCryptidComponent`, and emits
  a `CryptidConfirmedEvent` with a reputation/discovery reward. Low-clarity cases stay open.
- **Field reports** — `cryptidsim_fragments` render eerie, hedged prompt lines for unconfirmed
  creatures ("something large moves beyond the treeline — you can't be sure") and plain,
  definitive lines once a cryptid is confirmed.
- **Conditions gate** — `is_concealing` enforces that cryptids are only sightable at night, in
  fog/obscuring weather, or in the dark, so time and weather actually matter.

This repo intentionally keeps all cryptid work outside the main `bunnyland-server` repo and
depends on neither spectersim nor loresim.

## Layout

- `server/` - Python Bunnyland plugin package with the cryptid/sighting/case components, the
  confirmation consequence, prompt fragments, a worldgen enrichment hook, the sighting verb, a
  spawn factory, and tests.

## Server Plugin

The plugin exposes `bunnyland_cryptidsim.bunnyland_plugins()` and contributes:

- `CryptidComponent`, `SightingComponent`, `CryptidCaseComponent`, `ConfirmedCryptidComponent`.
- `sight-cryptid` - the investigate verb for the holder (human or AI).
- `CryptidConfirmationConsequence` - confirms cases that gather enough clear sightings, with
  `SightingRecordedEvent` and `CryptidConfirmedEvent`.
- `cryptidsim_fragments` - hedged/confirmed field-report lines for prompts.
- `CryptidWorldgenHook` - seeds rare cryptids into generated worlds.
- `spawn_cryptid` - spawn factory.

## Running

This package builds no containers. It is loaded into the stock server via `--module`:

```bash
bunnyland serve --module bunnyland_cryptidsim
```

`default_enabled=True`, so no `--plugin` flag is required once the module is imported. The
`bunnyland_cryptidsim` package must be importable by the server (installed into the server's
environment, or on `PYTHONPATH`).

## Development

Run server tests against a sibling `bunnyland-server` checkout (no install required —
`server/tests/conftest.py` puts both packages on `sys.path`). From `server/`:

```bash
uv run --project ../../bunnyland-server -m pytest
uv run --project ../../bunnyland-server ruff check src tests
```

See [`server/README.md`](server/README.md) for more detail.

## Contributing & Conduct

This plugin follows the Bunnyland project's
[contribution guidelines](CONTRIBUTING.md) and [code of conduct](CODE_OF_CONDUCT.md),
which point back to the `bunnyland-server` repository.

## License

Licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
