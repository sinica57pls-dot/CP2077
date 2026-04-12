# RED4 Engine Test Framework

Offline test framework for Cyberpunk 2077 mods. Tests mod logic against a simulated RED4 engine **without launching the game**.

Built from the actual Codeware C++ source (`src/App/World/DynamicEntitySystem.cpp`) and RedScript API stubs (`scripts/`).

## Quick Start

```bash
# Run all tests (requires Python 3.9+, zero dependencies)
python tests/run_tests.py

# Run a single mod's tests
python -m unittest tests.mods.test_amm_companion_close -v
```

## What's Simulated

The `tests/engine/` package recreates these RED4 engine subsystems:

| System | Source | Simulation |
|--------|--------|------------|
| **DynamicEntitySystem** | `src/App/World/DynamicEntitySystem.cpp` | Tag-based entity registry, `IsPopulated()`, `GetTagged()`, session cleanup |
| **Entity** | `scripts/Entity/Entity.reds` | Position, orientation, `SetWorldTransform()`, `GetWorldOrientation()`, `IsA()` RTTI |
| **DelaySystem** | `scripts/Scheduling/DelaySystem.reds` | Time-stepped callback scheduling with self-rescheduling |
| **CallbackSystem** | `scripts/Callback/CallbackSystem.reds` | Input/Key and Session event dispatch |
| **WorldTransform** | `scripts/Base/Addons/WorldTransform.reds` | FixedPoint position + Quaternion orientation |
| **GameInstance** | Redscript builtins | Global system access, `GetPlayer()`, `ModLog()`, `SqrtF()` |

## Adding Tests for a New Mod

1. Create `tests/mods/test_your_mod.py`
2. Port your mod's core logic to Python (it talks to the same simulated engine)
3. Write `unittest.TestCase` classes

### Minimal Example

```python
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import GameSimulation, Vector4

class TestMyMod(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_npc_spawns_at_position(self):
        npc = self.sim.spawn_npc(tags=["AMM"], pos=(10, 5, 0))
        pos = npc.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 10.0)
        self.assertAlmostEqual(pos.Y, 5.0)

    def test_tick_advances_time(self):
        self.sim.tick(count=4, interval=0.25)  # 1 second of game time
        self.assertAlmostEqual(self.sim.delay.current_time, 1.0)

if __name__ == '__main__':
    unittest.main()
```

### Key Simulation Methods

```python
sim = GameSimulation()

# Session lifecycle
sim.start_session(player_pos=(x, y, z), player_yaw=90)
sim.end_session()

# Spawn entities
npc = sim.spawn_npc(tags=["AMM", "Companion"], pos=(10, 0, 0), yaw=45)

# Time & ticks
sim.tick(count=4, interval=0.25)    # 4 ticks at 0.25s each
sim.advance_time(1.0)               # advance by 1 second

# Input
sim.press_key(EInputKey.IK_F6)

# Player movement
sim.move_player(pos=(50, 50, 0), yaw=180)

# Log inspection
messages = sim.get_log()             # list of ModLog output strings
sim.clear_log()

# Cleanup (call in tearDown!)
sim.teardown()
```

## Extending the Engine Simulation

If your mod uses engine features not yet simulated:

1. Add the mock class to the appropriate module in `tests/engine/`
   - `types.py` -- value types (Vector4, Quaternion, etc.)
   - `entity.py` -- entity hierarchy and components
   - `systems.py` -- game systems (DES, DelaySystem, etc.)
   - `game_instance.py` -- global accessors
2. Re-export it in `tests/engine/__init__.py`
3. Wire it into `GameSimulation` if it needs lifecycle management

## What's NOT Simulated

- UI / ink widget system (ImGui overlay)
- AI behavior trees / NPC navigation
- Physics / raycasting / collision
- TweakDB record queries
- Audio / visual effects
- File I/O / save system internals
