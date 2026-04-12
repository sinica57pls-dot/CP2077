# AI_CONTEXT.md — AI Session Orientation

This file provides orientation context for any AI coding session working in this repository.
It gives you the essential context you need to work here effectively.

---

## What is this repository?

**Cyberpunk 2077 modding wiki and engine simulation framework.**

- The main content is a GitBook-style wiki for CP2077 mod creators
  (documentation, guides, TweakDB references — found in `for-mod-creators/`,
  `for-mod-creators-theory/`, `modding-guides/`, etc.)
- It also contains a **full offline CP2077 engine simulator** in `tests/`
  that lets you run and stress-test mod logic without launching the game.

The test engine is the most technically complex part of the repo and the most
likely thing a Claude session will be asked to work on.

---

## Offline Engine Simulator — Quick Reference

**Location:** `tests/`
**Run all tests:** `python tests/run_tests.py`
**Run one suite:** `python -m unittest tests.mods.test_amm_full -v`
**Requirements:** Python 3.9+, zero external dependencies

### What it simulates

The engine replicates the full RED4 (CP2077) runtime at the Python level,
so mod logic can be tested without the game:

| Module | What it provides |
|---|---|
| `tests/engine/simulation.py` | `GameSimulation` — the main test orchestrator; one instance per test |
| `tests/engine/entity.py` | `PlayerPuppet`, `NPCPuppet`, `DynamicEntitySpec` |
| `tests/engine/systems.py` | `DynamicEntitySystem` (dual-index), `DelaySystem` (heapq), `CallbackSystem` |
| `tests/engine/tweakdb.py` | `TweakDB` with `CloneRecord`, `SetFlatNoUpdate`, `Update`; 60+ seeded records |
| `tests/engine/stats.py` | All 5 attributes, 12 skills, 20+ perks, accurate HP/stamina/crit formulas |
| `tests/engine/combat.py` | Full 11-step damage pipeline, status effects, weapon state |
| `tests/engine/inventory.py` | `TransactionSystem`, `EquipmentSystem`, `StreetCredSystem` |
| `tests/engine/quests.py` | Facts, quest phases, journal objectives |
| `tests/engine/ai.py` | `AIFollowerRole`, `AINoRole`, `AIRole`; full command queue + history |
| `tests/engine/appearance.py` | `PrefetchAppearanceChange` / `ScheduleAppearanceChange` pipeline |
| `tests/engine/world.py` | `GodModeSystem`, `TeleportationFacility`, `StaticEntitySystem`, `WorkspotSystem`, `TargetingSystem`, `MappinSystem`, `WeatherSystem`, `GameTimeSystem`, `GameplayStatusEffectSystem`, `ObserverRegistry` |
| `tests/engine/game_instance.py` | `GameInstance` facade + `GetPlayer()`, `FindEntityByID()`, `ModLog()` |
| `tests/engine/types.py` | `Vector4`, `Quaternion`, `EntityID`, `CName`, `FixedPoint` |

The `tests/engine/__init__.py` re-exports **everything** — import from `engine`:
```python
from engine import GameSimulation, Vector4, NPCStats, TweakDB, AIFollowerRole, ...
```

### Minimal test pattern

```python
import unittest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import GameSimulation

class TestMyMod(unittest.TestCase):
    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()   # always call — resets global state

    def test_something(self):
        npc = self.sim.spawn_npc(tags=["MyTag"], pos=(5, 0, 0))
        self.assertTrue(self.sim.des.IsPopulated("MyTag"))
```

### Existing test suites (463 tests total)

| File | Suites | Tests |
|---|---|---|
| `tests/mods/test_amm_full.py` | 15 | 155 |
| `tests/mods/test_amm_companion_close.py` | 10 | 84 |
| `tests/mods/test_inventory_system.py` | 6 | 71 |
| `tests/mods/test_stats_system.py` | 10 | 58 |
| `tests/mods/test_combat_system.py` | 10 | 53 |
| `tests/mods/test_tweakdb.py` | 3 | 42 |

Full API documentation: `tests/README.md`
Deep engine reference (any AI session): `tests/AI_CONTEXT.md`

---

## Repository Layout

```
/workspace/project/
├── AI_CONTEXT.md                   ← you are here
├── SUMMARY.md                  ← GitBook table of contents
├── README.md                   ← project overview
│
├── tests/                      ← OFFLINE ENGINE SIMULATOR
│   ├── AI_CONTEXT.md               ← deep engine reference (read this for engine work)
│   ├── README.md               ← full API documentation
│   ├── run_tests.py            ← test runner
│   ├── engine/                 ← simulation modules (14 files)
│   └── mods/                   ← test suites (6 files, 463 tests)
│
├── for-mod-creators/           ← wiki: practical modding guides
├── for-mod-creators-theory/    ← wiki: theory (TweakDB, RED4 internals)
├── modding-guides/             ← wiki: step-by-step tutorials
├── modding-know-how/           ← wiki: reference material
├── scripts/                    ← REDscript source stubs (used as reference)
├── src/                        ← C++ engine source (read-only reference)
└── .github/workflows/          ← CI: GitBook publish
```

---

## Common Tasks

### Run the full test suite
```bash
python tests/run_tests.py
```

### Run a specific suite verbosely
```bash
python -m unittest tests.mods.test_amm_full -v
python -m unittest tests.mods.test_amm_companion_close -v
python -m unittest tests.mods.test_combat_system -v
```

### Add a test for a new mod
1. Create `tests/mods/test_<modname>.py`
2. Import `from engine import GameSimulation` (and whatever else you need)
3. Write `unittest.TestCase` subclasses
4. `run_tests.py` discovers it automatically

### Extend the engine with a new system
1. Add the system class to the appropriate `tests/engine/*.py` module
2. Export it from `tests/engine/__init__.py`
3. Instantiate it in `GameSimulation.__init__` in `tests/engine/simulation.py`
4. Wire its global into `game_instance.py` (follow the pattern of existing systems)
5. Reset it in `gi._reset_globals()` in `game_instance.py`
6. Add `teardown` / `gi` reset if needed

### Look up a specific engine system
- See `tests/AI_CONTEXT.md` for the full system-by-system reference
- See `tests/README.md` for the public API

---

## Key Conventions

- `GameSimulation` is **not** thread-safe; one instance per test, reset with `teardown()`
- `EntityID.reset_counter()` is called in `GameSimulation.__init__` — IDs start at 1 per sim
- `TweakDB.Reset()` is also called in `__init__` and `teardown()` — always isolated
- Global state lives in `tests/engine/game_instance.py` as module-level variables
- All positions are `Vector4(x, y, z, w=0)`; orientation is `Quaternion`
- The `gi` alias (used inside simulation.py) refers to `tests/engine/game_instance`

---

## What this repository is NOT

- Not a full game engine — physics, rendering, audio, navigation are absent
- Not a live-game connection — this is fully offline, no CET or REDscript runtime
- Not a wiki generator — the markdown files are source; GitBook publishes them

---

## If you're asked to…

| Task | Where to start |
|---|---|
| Test whether a mod mechanic works | `tests/engine/simulation.py` + `tests/mods/` |
| Add a missing game system | `tests/engine/world.py` or a new engine module |
| Understand TweakDB records | `tests/engine/tweakdb.py` — `_seed_records()` |
| Understand the AMM mod | `tests/mods/test_amm_full.py` has 155 tests covering every AMM system |
| Update wiki documentation | Edit markdown files in `for-mod-creators*/` or `modding-guides/` |
| Check what the engine exports | `tests/engine/__init__.py` — single import surface |
