# tests/AI_CONTEXT.md — Engine Deep Reference

This file is the AI session context for working inside `tests/`.
It is the **definitive technical reference** for the offline CP2077 engine simulator.
Start here before reading any source file.

---

## Architecture in One Paragraph

`GameSimulation` (in `simulation.py`) is the root test object. It owns one instance
of every game system, stores them as attributes (`self.des`, `self.god_mode`, …),
and also writes them into module-level globals in `game_instance.py` (`gi`). This
dual-reference pattern lets both direct test code (`sim.des.IsPopulated(…)`) and
mod-ported Lua/Redscript code (`GameInstance.GetDynamicEntitySystem()`) reach the
same object. Every `TestCase` creates one `GameSimulation`, calls `start_session`,
runs assertions, then calls `teardown()` which resets all globals and TweakDB.

---

## File Map

```
tests/
├── AI_CONTEXT.md           ← this file
├── README.md           ← public API docs (for humans and AI)
├── run_tests.py        ← unittest discovery runner
├── __init__.py         ← empty
│
├── engine/
│   ├── __init__.py     ← SINGLE IMPORT SURFACE — re-exports everything
│   ├── simulation.py   ← GameSimulation (the test orchestrator)
│   ├── game_instance.py← GameInstance facade + globals + GetPlayer/FindEntityByID
│   ├── types.py        ← Vector4, Quaternion, EntityID, CName, FixedPoint, EInputKey
│   ├── entity.py       ← Entity hierarchy: PlayerPuppet, NPCPuppet, DynamicEntitySpec
│   ├── systems.py      ← DynamicEntitySystem, DelaySystem, CallbackSystem, ScriptableSystem
│   ├── tweakdb.py      ← TweakDB, TweakDBID (FNV-1a), 60+ seeded records
│   ├── stats.py        ← CharacterStats, NPCStats, StatsSystem, preset builds
│   ├── combat.py       ← DamageSystem, HitFlag, StatusEffectController, WeaponState
│   ├── inventory.py    ← TransactionSystem, EquipmentSystem, StreetCredSystem, ItemID
│   ├── quests.py       ← QuestSystem, QuestPhase, QuestNode, FactManager, JournalManager
│   ├── ai.py           ← EAIAttitude, AttitudeAgent, AIControllerComponent, all roles + commands
│   ├── appearance.py   ← AppearanceComponent, AppearanceDatabase, AppearanceTriggerSystem
│   └── world.py        ← GodModeSystem, TeleportationFacility, StaticEntitySystem,
│                          WorkspotSystem, TargetingSystem, MappinSystem,
│                          WeatherSystem, GameTimeSystem, GameplayStatusEffectSystem,
│                          ObserverRegistry
│
└── mods/
    ├── test_amm_full.py              15 suites, 155 tests — full AMM mod
    ├── test_amm_companion_close.py   10 suites,  84 tests — AMM companion
    ├── test_combat_system.py         10 suites,  53 tests
    ├── test_inventory_system.py       6 suites,  71 tests
    ├── test_stats_system.py          10 suites,  58 tests
    └── test_tweakdb.py                3 suites,  42 tests
```

---

## System-by-System Reference

### `GameSimulation` (simulation.py)

The root object for every test. Key attributes:

```python
sim.des             # DynamicEntitySystem
sim.delay           # DelaySystem
sim.callback        # CallbackSystem
sim.player          # PlayerPuppet (set after start_session)
sim.tweakdb         # TweakDB instance
sim.transaction     # TransactionSystem
sim.equipment       # EquipmentSystem
sim.quests          # QuestSystem
sim.street_cred     # StreetCredSystem
sim.player_stats    # CharacterStats
sim.god_mode        # GodModeSystem
sim.teleport        # TeleportationFacility
sim.static_entities # StaticEntitySystem
sim.workspot        # WorkspotSystem
sim.targeting       # TargetingSystem
sim.mappins         # MappinSystem
sim.weather         # WeatherSystem
sim.time_system     # GameTimeSystem
sim.status_effects  # GameplayStatusEffectSystem
sim.observers       # ObserverRegistry
sim.appearance_db   # AppearanceDatabase
sim.appearance_triggers  # AppearanceTriggerSystem
```

Key methods:
```python
sim.start_session(player_pos=(0,0,0), player_yaw=0.0)
sim.end_session()
sim.teardown()          # ALWAYS call in tearDown()

sim.tick(count=1, interval=0.25)    # fires DelaySystem + StatusEffects
sim.advance_time(seconds)           # same but single step

sim.spawn_npc(tags, pos, yaw=0, npc_stats=None, appearance="default")
sim.spawn_npc_bulk(count, base_tags, base_pos)  # stress test helper
sim.despawn_npc(npc)                # removes mappin + DES entry

sim.set_companion(npc, player=None, follow_distance=2.0)
sim.toggle_hostile(npc)
sim.set_god_mode(npc, immortal=True)
sim.issue_follow_command(npc, distance=2.0)
sim.update_follow_distances(companions)   # tiered: ≤2→2m, 3→3.5m, 4+→5m
sim.check_companion_distances(companions, threshold=15.0)

sim.change_appearance(npc, app_name, prefetch=True)
sim.teleport_entity(entity, pos, yaw=0.0)
sim.teleport_npc_via_command(npc, pos, yaw=0.0)

sim.set_player_invisible(True/False)
sim.is_player_invisible()

sim.give_item(entity_id, record_path, amount=1)
sim.give_money(entity_id, amount)
sim.equip_item(entity_id, record_path, slot)
sim.resolve_hit(weapon_record_path, target_stats, flags, rng_seed)

sim.set_fact(name, value)
sim.get_fact(name)
sim.press_key(EInputKey.IK_F6)
sim.move_player(pos, yaw=None)

sim.timed(fn, label="", warn_ms=500.0)   # returns (result, elapsed_ms)
sim.get_log()   # captured ModLog calls
sim.clear_log()
```

---

### `DynamicEntitySystem` (systems.py)

Dual-index implementation:
- `_tags_to_ids`: `Dict[str, Set[EntityID]]` — forward index
- `_ids_to_tags`: `Dict[EntityID, Set[str]]` — reverse index (O(1) `GetTags`)

Key operations:
```python
des.IsPopulated("TagName")          # True if any live entity has this tag
des.GetTagged("TagName")            # List[Entity]
des.GetTaggedIDs("TagName")         # List[EntityID]
des.GetTags(eid)                    # List[CName] — O(1) via reverse index
des.IsManaged(eid)
des.IsSpawned(eid)
des.GetEntity(eid)
des.AddEntity(entity, tags)
des.DeleteEntity(eid)               # O(T) — only touches tags on this entity
des.CreateEntity(spec)              # returns (EntityID, NPCPuppet)
des.AssignTag(eid, tag)
des.UnassignTag(eid, tag)
des.DeleteTagged("TagName")
des.GetEntityCount()
des.GetAllEntities()
```

---

### `DelaySystem` (systems.py)

heapq-based; `Tick(dt)` is O(k log n):
```python
seq_id = delay.DelayCallback(cb, delay=1.0)   # schedule; returns sequence ID
delay.DelayCallbackNextFrame(cb)
delay.CancelCallback(seq_id)
delay.Tick(dt)                                 # returns count fired
delay.current_time                             # current simulated time
delay.pending_count
```

`DelayCallback` subclass pattern:
```python
class MyCallback(DelayCallback):
    def Call(self):
        # your logic

delay.DelayCallback(MyCallback(), delay=2.5)
sim.advance_time(3.0)   # fires it
```

---

### `TweakDB` (tweakdb.py)

Singleton; call `TweakDB.Reset()` between sessions (done in `GameSimulation.__init__`
and `teardown()`):
```python
db = TweakDB.Get()

db.GetRecord("Items.Preset_Yukimura_Default")  # gamedataRecord
db.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")  # float/str/etc
db.SetFlat(flat_id, value)             # runtime override
db.CloneRecord(new_id, source_id)       # used by AMM to create custom characters
db.SetFlatNoUpdate(flat_id, value)      # set without notifying listeners
db.Update(record_id)                    # notify listeners; marks WasUpdated
db.WasUpdated(record_id)               # test helper

# Seeded top-level keys (partial list):
# Weapons:   "Items.Preset_Yukimura_Default", "Items.Preset_Masamune_Default",
#            "Items.Preset_Overture_Default", "Items.Preset_Militech_Lexington_Default"
# Armor:     "Items.Preset_Biker_Jacket_Default", "Items.Preset_Kabuki_Samurai_Mask"
# Cyberware: "Items.AdvancedMantisBlades", "Items.SandevistanMKI"
# Consumables: "Items.MaxDOC", "Items.BerserkMKI"
# Characters: "Character.Judy_Judy", "Character.Panam_Palmer",
#             "Character.Johnny_Silverhand", "Character.Rogue_Amendiares",
#             "Character.V_Default", "Character.V_Default_Female",
#             "Character.Base_NPC"
# AMM clones: "AMM_Character.Judy", "AMM_Character.Panam",
#             "AMM_Character.Johnny", "AMM_Character.Rogue",
#             "AMM_Character.Player_Male", "AMM_Character.Player_Female"
```

`gamedataRecord.GetFlat(key)` and `.SetFlat(key, value)` for per-record access.

---

### `NPCPuppet` (entity.py)

Carries subsystems as instance attributes:
```python
npc._ai_ctrl       # AIControllerComponent
npc._attitude      # AttitudeAgent
npc._appearance    # AppearanceComponent
npc._is_companion  # bool
npc._mappin_id     # int (-1 = none)
npc._npc_stats     # NPCStats | None

# Public API:
npc.GetEntityID()
npc.GetWorldPosition()          # Vector4
npc.GetWorldOrientation()       # Quaternion
npc.IsDefined()
npc.Invalidate()

npc.GetAIControllerComponent()  # AIControllerComponent
npc.GetAttitudeAgent()          # AttitudeAgent

npc.GetCurrentAppearanceName()
npc.GetAppearanceHistory()      # delegates to _appearance.GetChangeHistory()
npc.PrefetchAppearanceChange(app_name)
npc.ScheduleAppearanceChange(app_name)

npc.SetIsCompanion(flag)
npc.IsCompanion()
npc.SetMappin(mappin_id)
npc.GetMappin()
```

---

### `AIControllerComponent` (ai.py)

```python
ctrl = npc.GetAIControllerComponent()

# Role management
ctrl.SetAIRole(role)            # AIFollowerRole / AINoRole / AIRole
ctrl.GetAIRole()

# Command queue (newest sent = active)
ctrl.SendCommand(cmd)           # AICommand; cancels previous command of same type
ctrl.GetActiveCommand()         # most recently sent command
ctrl.GetLastCommandOfType(AICommandType.Follow)
ctrl.GetCommandHistory()        # List[AICommand]
ctrl.CancelActiveCommands()

# Predicates
ctrl.IsFollower()   # role is AIFollowerRole
ctrl.IsHostile()    # role is AIRole with hostile group
ctrl.IsNeutral()    # role is AINoRole

# Command factories (all return AICommand):
AIFollowTargetCommand(target, distance=2.0, radius=0.5)
AITeleportCommand(position, yaw=0.0)
AIMoveToCommand(position, tolerance=0.5)
AIHoldPositionCommand()
AIPlayAnimationCommand(anim_name, looping=False)
AIPlayVoiceOverCommand(vo_name)
AITriggerCombatCommand(target)
```

---

### `AttitudeAgent` (ai.py)

```python
agent = npc.GetAttitudeAgent()

agent.SetAttitudeGroup("PlayerAllies")    # sets default group attitude
agent.GetAttitudeGroup()

agent.SetAttitudeTowards(other_agent, EAIAttitude.AIA_Friendly)
agent.GetAttitudeTowards(other_agent)

# EAIAttitude values:
EAIAttitude.AIA_Friendly   # companion / ally
EAIAttitude.AIA_Neutral    # bystander
EAIAttitude.AIA_Hostile    # enemy
```

---

### `AppearanceComponent` (appearance.py)

Two-step pipeline (prefetch = load assets, schedule = apply):
```python
comp = npc._appearance   # direct access in tests

comp.PrefetchAppearanceChange("judy_casual")   # doesn't switch
comp.ScheduleAppearanceChange("judy_casual")   # switches immediately in sim
comp.GetCurrentAppearanceName()
comp.GetChangeHistory()   # List[str] — all appearances (including initial)
comp.GetChangeCount()     # int
comp.RegisterCustomAppearance(AppearanceRecord(...))
comp.GetCustomAppearance(name)
comp.GetCustomAppearanceNames()
```

---

### `GodModeSystem` (world.py)

Multi-reason tracking — entity stays immortal until ALL reasons are cleared:
```python
gm.AddGodMode(eid, gameGodModeType.Immortal, "reason_key")
gm.ClearGodMode(eid, "reason_key")
gm.HasGodMode(eid)          # True if any reason active
gm.IsImmortal(eid)          # True if any Immortal reason active
gm.GetGodModeType(eid, reason)   # gameGodModeType or None
gm.GetImmortalCount()       # count of entities with active god mode
```

---

### `GameplayStatusEffectSystem` (world.py)

```python
sfx.ApplyStatusEffect(eid, effect_id, source="", duration=-1.0)
#   duration=-1 → permanent; duration>0 → expires after Tick()

sfx.RemoveStatusEffect(eid, effect_id)
sfx.ObjectHasStatusEffect(entity_or_eid, effect_id)
sfx.ObjectHasStatusEffectWithTag(entity_or_eid, tag_prefix)
sfx.GetActiveEffectCount(eid)
sfx.Tick(dt)                # called by sim.tick() and sim.advance_time()

# GameplayRestriction constants:
GameplayRestriction.NoMovement       = "GameplayRestriction.NoMovement"
GameplayRestriction.NoCameraControl  = "GameplayRestriction.NoCameraControl"
GameplayRestriction.NoAI             = "GameplayRestriction.NoAI"
GameplayRestriction.Invisible        = "GameplayRestriction.Invisible"
GameplayRestriction.NoHUD            = "GameplayRestriction.NoHUD"
```

---

### `WeatherSystem` (world.py)

```python
weather.SetWeather(WeatherID.Rain, blend_time=5.0)
weather.GetActiveWeather()       # WeatherID
weather.GetBlendTime()           # float
weather.GetWeatherHistory()      # List[WeatherID]

# WeatherID values:
WeatherID.Clear / .Overcast / .Rain / .HeavyRain / .Fog / .Storm / .Sandstorm
```

---

### `MappinSystem` (world.py)

```python
mid = mappins.RegisterMappin(MappinData(label="NPC"), position=Vector4(...))
mid = mappins.RegisterMappinWithObject(MappinData(label="NPC"), entity)
mappins.UnregisterMappin(mid)
mappins.HasMappin(mid)
mappins.GetMappinCount()
mappins.GetPinForEntity(entity)     # returns mid or None
```

---

### `StaticEntitySystem` (world.py) — AMM scene builder

Props: no AI, no animations. Independent ID counter starting at 9000.
```python
eid, ent = ses.CreateEntity(StaticEntitySpec(
    entity_path="base\\props\\chair.ent",
    appear_name="red",
    position=Vector4(5, 0, 0, 0)))

ses.DeleteEntity(eid)
ses.GetEntity(eid)
ses.GetAllEntities()
ses.GetEntityCount()
ses.ClearAll()

# StaticEntity methods:
ent.GetEntityID()
ent.GetWorldPosition()
ent.GetScale()
ent.SetScale(Vector3(2, 2, 2))
ent.IsDefined()
ent.Dispose()
```

---

### `ObserverRegistry` (world.py) — CET hook simulation

```python
obs.Observe("MyClass::MyMethod", lambda self, *a: None)
obs.ObserveAfter("MyClass::MyMethod", lambda self, *a: None)
obs.Override("MyClass::MyMethod", lambda self, *a: None)
obs.Fire("MyClass::MyMethod", target_obj, *args)   # used in tests
obs.GetObservers("MyClass::MyMethod")              # list of registered hooks
obs.Clear("MyClass::MyMethod")
```

---

## Global State Pattern

```
GameSimulation.__init__()
  └── creates system instances
  └── writes them to game_instance.py globals:
        gi._current_des = self.des
        gi._current_god_mode = self.god_mode
        ...etc...

GameInstance.GetDynamicEntitySystem()
  └── returns gi._current_des (same object)

GameSimulation.teardown()
  └── gi._reset_globals()   → sets all to None
  └── TweakDB.Reset()       → fresh singleton
```

This means: if a module uses `GameInstance.GetXxx()`, it receives the same system
object that `sim.xxx` holds. Tests can use either access path interchangeably.

---

## Performance Characteristics

| Operation | Complexity | Notes |
|---|---|---|
| `DES.GetTags(eid)` | O(1) | reverse index `_ids_to_tags` |
| `DES.DeleteEntity(eid)` | O(T) | T = tag count on entity |
| `DES.GetTagged(tag)` | O(k) | k = matching entities |
| `DelaySystem.Tick(dt)` | O(k log n) | heapq; k fired, n pending |
| `DelaySystem.DelayCallback` | O(log n) | heapq push |
| `DelaySystem.CancelCallback` | O(n) | filter + heapify |

---

## How to Add a New Engine System

1. **Implement** the class in an existing `engine/*.py` file (or a new one)
2. **Export** it from `engine/__init__.py`
3. **Instantiate** in `GameSimulation.__init__`:
   ```python
   self.my_system = MySystem()
   ```
4. **Wire to globals** in `GameSimulation.__init__`:
   ```python
   gi._current_my_system = self.my_system
   ```
5. **Declare the global** in `game_instance.py`:
   ```python
   _current_my_system = None
   ```
6. **Add accessor** to `GameInstance` in `game_instance.py`:
   ```python
   @staticmethod
   def GetMySystem():
       return _current_my_system
   ```
7. **Reset** in `game_instance._reset_globals()`:
   ```python
   _current_my_system = None
   ```

---

## Writing a New Mod Test File

Template (`tests/mods/test_<modname>.py`):
```python
"""
<ModName> Test Suite
Covers: <brief description>
Source: <link to mod repo if applicable>
"""

import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation,
    # import only what you use
)


class TestCore(unittest.TestCase):
    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_example(self):
        npc = self.sim.spawn_npc(tags=["MyMod_NPC"], pos=(5, 0, 0))
        self.assertTrue(self.sim.des.IsPopulated("MyMod_NPC"))


if __name__ == '__main__':
    unittest.main()
```

`run_tests.py` auto-discovers any `test_*.py` file in `tests/mods/`.

---

## Debugging Tips

- `sim.get_log()` — returns all `ModLog()` calls made during the test
- `sim.clear_log()` — clears the log buffer
- `npc.GetAIControllerComponent().GetCommandHistory()` — sent command history
- `npc._appearance.GetChangeHistory()` — appearance change history
- `sim.delay.pending_count` — callbacks still queued
- `sim.delay.current_time` — simulated clock value
- `sim.des.GetEntityCount()` — total live entities
- `sim.god_mode.GetImmortalCount()` — immortal entities
- `EntityID.reset_counter()` is called in `GameSimulation.__init__` — IDs restart from 1 each sim

---

## Known Limitations

- No navigation mesh / AI pathfinding (positions are snapped instantly)
- No physics; `Vector4` moves are teleports
- TweakDB seeded with ~60 records; extend with `CloneRecord` / `SetFlat`
- `ObserverRegistry.Fire()` must be called explicitly (no automatic dispatch)
- `DelaySystem.CancelCallback` is O(n) — avoid calling in tight loops
