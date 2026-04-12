# RED4 Engine Test Framework

Offline test framework for Cyberpunk 2077 mods.  Tests mod logic against a
simulated RED4 engine **without launching the game**.

Built from the actual Codeware C++ source (`src/App/World/DynamicEntitySystem.cpp`),
REDscript API stubs (`scripts/`), reverse-engineered game mechanics from
community research, and the real
[AppearanceMenuMod Lua source](https://github.com/MaximiliumM/appearancemenumod).

## Quick Start

```bash
# Run all tests (requires Python 3.9+, zero dependencies)
python tests/run_tests.py

# Run a single suite
python -m unittest tests.mods.test_amm_full              -v  # AMM (155 tests)
python -m unittest tests.mods.test_amm_companion_close   -v  # companion close-follow
python -m unittest tests.mods.test_tweakdb               -v  # TweakDB
python -m unittest tests.mods.test_stats_system          -v  # stats formulas
python -m unittest tests.mods.test_combat_system         -v  # damage pipeline
python -m unittest tests.mods.test_inventory_system      -v  # inventory / equipment
```

---

## What's Simulated

### Core Engine

| System | Source | Simulation |
|------|------|------|
| **DynamicEntitySystem** | `src/App/World/DynamicEntitySystem.cpp` | Dual-index (forward + reverse) tag registry; `IsPopulated()`, `GetTagged()`, session cleanup; O(1) `GetTags()` via reverse index |
| **Entity** | `scripts/Entity/Entity.reds` | Position, orientation, `SetWorldTransform()`, `GetWorldOrientation()`, `IsA()` RTTI |
| **DelaySystem** | `scripts/Scheduling/DelaySystem.reds` | heapq-backed O(k log n) timed callbacks; self-rescheduling; `CancelCallback()` |
| **CallbackSystem** | `scripts/Callback/CallbackSystem.reds` | Input/Key and Session event dispatch |
| **WorldTransform** | `scripts/Base/Addons/WorldTransform.reds` | FixedPoint position + Quaternion orientation |
| **GameInstance** | REDscript builtins | Global system access, `GetPlayer()`, `FindEntityByID()`, `ModLog()`, `SqrtF()` |

### Game Mechanics

| System | Module | What it simulates |
|------|------|------|
| **TweakDB** | `engine/tweakdb.py` | FNV-1a hashed record IDs; 60+ seeded records; `CloneRecord` / `SetFlatNoUpdate` / `Update` (AMM model-swap); `GetRecord` / `GetFlat` / `SetFlat` override API |
| **StatsSystem** | `engine/stats.py` | All 5 attributes (Body/Reflexes/Tech/Intel/Cool), 12 skills, 20+ perks, accurate HP/stamina/RAM/crit/armor formulas |
| **DamageSystem** | `engine/combat.py` | Full 11-step damage pipeline (weapon → skill → perk → crit → headshot → stealth → armor → resistance → final) |
| **StatusEffects (combat)** | `engine/combat.py` | Burning, Bleeding, Poison, Shock, EMP with correct tick intervals and damage values |
| **WeaponState** | `engine/combat.py` | Magazine, reload timer, fire rate enforcement |
| **TransactionSystem** | `engine/inventory.py` | Item add/remove/transfer/query; stackable vs unique; eddies currency |
| **EquipmentSystem** | `engine/inventory.py` | All equipment slots, armor value aggregation |
| **StreetCredSystem** | `engine/inventory.py` | Levels 1–50, XP thresholds from community data |
| **QuestSystem** | `engine/quests.py` | Facts (case-insensitive integer store), phase graphs, journal objectives |

### World Systems (AMM)

| System | Module | What it simulates |
|------|------|------|
| **AI Commands** | `engine/ai.py` | `AIFollowerRole`, `AINoRole`, `AIRole`; `SendCommand()` queue; `AIFollowTargetCommand`, `AITeleportCommand`, `AIMoveToCommand`, `AIHoldPositionCommand`, `AIPlayAnimationCommand`; history |
| **AttitudeAgent** | `engine/ai.py` | Per-entity attitude group + per-agent overrides; `EAIAttitude` (Friendly/Neutral/Hostile); `IsFollower()`, `IsHostile()` predicates |
| **AppearanceComponent** | `engine/appearance.py` | `PrefetchAppearanceChange` / `ScheduleAppearanceChange` two-step pipeline; history tracking; deferred-apply pattern |
| **AppearanceDatabase** | `engine/appearance.py` | Seeded with real AMM characters (Judy, Panam, Johnny, Rogue, V, Maelstrom gang) and their variant appearances |
| **AppearanceTriggerSystem** | `engine/appearance.py` | Zone / combat / stealth auto-switch rules |
| **GodModeSystem** | `engine/world.py` | `AddGodMode` / `ClearGodMode` with multi-reason tracking; `gameGodModeType.Immortal` |
| **TeleportationFacility** | `engine/world.py` | `Teleport(entity, Vector4, EulerAngles)` — direct position override |
| **StaticEntitySystem** | `engine/world.py` | Prop / scene object spawning; `SpawnEntity` / `DestroyEntity` / `GetSpawnedCount` |
| **WorkspotSystem** | `engine/world.py` | `IsActorInWorkspot()` guard before `AIPlayAnimationCommand` |
| **TargetingSystem** | `engine/world.py` | Look-at target assignment and lock; `GetLookAtTarget()` |
| **MappinSystem** | `engine/world.py` | Minimap pin registration / unregistration; `MappinData` with position, label, icon |
| **WeatherSystem** | `engine/world.py` | Named weather state transitions: `WeatherID.Clear`, `.Rain`, `.Fog`, `.Storm` |
| **GameTimeSystem** | `engine/world.py` | Time-of-day get/set in hours; day-night cycle queries |
| **GameplayStatusEffects** | `engine/world.py` | Apply / remove effects; duration expiry via `Tick(dt)`; `GameplayRestriction` constants |
| **ObserverRegistry** | `engine/world.py` | CET-style `Observe` / `ObserveAfter` / `Override` hook simulation |

### Character Visual Systems

| System | Module | What it simulates |
|------|------|------|
| **BodyType** | `engine/entity.py` | `WomanAverage`, `ManAverage`, `ManBig` body type enum; base body mesh path resolution |
| **BoneTransform** | `engine/entity.py` | Per-bone scale data (scaleX/Y/Z); identity check; bilateral mirroring (`_l` ↔ `_r`); Blender axis swap note |
| **DeformationRig** | `engine/entity.py` | Named set of bone transforms; symmetric bone scaling; TPP/FPP rig pair; clone, reset, modify |
| **MorphTargets** | `engine/entity.py` | `ApplyMorphTarget(target, region, value)` on `entMorphTargetSkinnedMeshComponent`; 0.0–1.0 clamping; entity-level lookup matching `EntityEx.cpp` |
| **VisualScale** | `engine/entity.py` | `Get/SetVisualScale(Vector3)` on all mesh component types; `RefreshAppearance()` trigger matching `VisualScaleEx.cpp` |
| **VisualSnapshot** | `engine/visual_snapshot.py` | Capture full visual state (body type, mesh components, scales, morphs, rig bones); `diff()` / `differs_from()` comparison; JSON-serializable |
| **SVG Skeleton** | `engine/skeleton.py` | 2D wireframe diagram from bone hierarchy; green/orange bone colouring; before/after comparison overlay |
| **glTF Export** | `engine/skeleton.py` | glTF 2.0 JSON with bone nodes, parent-child hierarchy, scale values, embedded cube mesh buffer; viewable in online 3D viewers |

---

## Test Coverage

| File | Suites | Tests | What's validated |
|------|--------|-------|------|
| `test_amm_full.py` | 15 | 155 | Full AMM mod — spawn, companions, AI commands, appearance, god mode, attitude, teleport, TweakDB clone, props, weather/time/mappins, status effects, stress (100 NPCs + 1000 callbacks), session lifecycle, end-to-end scenarios |
| `test_amm_companion_close.py` | 10 | 84 | AMM companion close-follow system (entity, lerp, teleport, sessions) |
| `test_tweakdb.py` | 3 | 42 | TweakDBID hashing, record lookup, GetFlat/SetFlat override |
| `test_stats_system.py` | 10 | 58 | HP/stamina/RAM/crit formulas, perks, preset builds, clamping |
| `test_combat_system.py` | 10 | 53 | Armor mitigation, hits, headshots, crits, status effects, weapon state |
| `test_inventory_system.py` | 6 | 71 | Inventory CRUD, equipment slots, eddies, street cred, facts, quests |
| `test_rig_visual.py` | 10 | 75 | Rig deformation (bone transforms, body types, deformation rigs, morph targets, visual scale, mesh components, NPC visual scale, body type switching) |
| `test_visual_verification.py` | 11 | 67 | Visual verification (snapshot capture/diff/compare, SVG skeleton diagrams, glTF 2.0 export, skeleton hierarchy validation) |
| **Total** | **75** | **605** | |

---

## AMM-Specific API

These methods mirror what `init.lua` in AppearanceMenuMod actually calls at runtime:

```python
sim = GameSimulation()
sim.start_session(player_pos=(0, 0, 0))

# ── Spawn / despawn ───────────────────────────────────────────────────────────
npc = sim.spawn_npc(tags=["AMM_NPC", "Companion"], pos=(5, 0, 0),
                    appearance="judy_default")
sim.despawn_npc(npc)   # also removes mappin

# Bulk spawn for stress tests
npcs = sim.spawn_npc_bulk(count=100, base_tags=["AMM_NPC"], base_pos=(0,0,0))

# ── Companion management ──────────────────────────────────────────────────────
npc = sim.set_companion(npc)          # AIFollowerRole + attitude Friendly
sim.toggle_hostile(npc)               # follower ↔ Ganger_Aggressive
sim.issue_follow_command(npc, distance=2.0)

# Tiered follow distances: 1-2 companions→2 m, 3→3.5 m, 4+→5 m
sim.update_follow_distances([npc1, npc2, npc3])

# Re-issue follow for any NPC that wandered > threshold
lagging = sim.check_companion_distances([npc1, npc2], threshold=15.0)

# ── God mode ──────────────────────────────────────────────────────────────────
sim.set_god_mode(npc, immortal=True)    # multi-reason: AMM_GodMode key
sim.set_god_mode(npc, immortal=False)   # clears AMM_GodMode reason

# Also available directly:
sim.god_mode.AddGodMode(eid, gameGodModeType.Immortal, "reason")
sim.god_mode.ClearGodMode(eid, "reason")
sim.god_mode.IsImmortal(eid)   # True only when ≥1 active reason

# ── Appearance ────────────────────────────────────────────────────────────────
sim.change_appearance(npc, "judy_summer", prefetch=True)  # prefetch then schedule
npc.GetCurrentAppearanceName()  # → "judy_summer"
npc.GetAppearanceHistory()      # → ["judy_default", "judy_summer"]

# ── Teleportation ─────────────────────────────────────────────────────────────
sim.teleport_entity(npc, pos=(50, 0, 0), yaw=90.0)          # via TeleportationFacility
sim.teleport_npc_via_command(npc, pos=(60, 0, 0), yaw=0.0)  # via AITeleportCommand

# ── TweakDB model swap (AMM's core AppearanceMenuMod mechanism) ───────────────
ok = sim.tweakdb.CloneRecord("AMM_Character.Judy", "Character.Judy_Judy")
sim.tweakdb.SetFlatNoUpdate("AMM_Character.Judy.entityTemplatePath",
                            "base\\characters\\main_npc\\judy\\judy.ent")
sim.tweakdb.Update("AMM_Character.Judy")
assert sim.tweakdb.WasUpdated("AMM_Character.Judy")

# ── Player invisibility (AMM passive mode) ────────────────────────────────────
sim.set_player_invisible(True)
sim.is_player_invisible()          # → True
sim.advance_time(5.0)              # status effects tick, duration effects may expire

# ── World systems ─────────────────────────────────────────────────────────────
sim.weather.SetWeather(WeatherID.Rain)
sim.weather.GetCurrentWeather()    # → WeatherID.Rain

sim.time_system.SetTime(20.0)      # 20:00 game time
sim.time_system.IsNight()          # → True

mappin_id = sim.mappins.RegisterMappin(MappinData(
    position=Vector4(5, 0, 0, 0), label="My NPC", icon="default"))
sim.mappins.UnregisterMappin(mappin_id)

# Props / scene building
spec = StaticEntitySpec(entity_path="base\\props\\chair.ent",
                         position=Vector4(10, 0, 0, 0))
prop_id, prop = sim.static_entities.SpawnEntity(spec)
sim.static_entities.DestroyEntity(prop_id)

# ── Performance measurement ───────────────────────────────────────────────────
result, elapsed_ms = sim.timed(lambda: sim.spawn_npc_bulk(100))
assert elapsed_ms < 1000, f"Spawn 100 NPCs took {elapsed_ms:.1f} ms"

# ── Rig deformation (V body shape mods) ──────────────────────────────────────
from engine import (BodyType, DeformationRig, BoneTransform, MorphTargetEntry,
                    VisualSnapshot, generate_skeleton_svg,
                    generate_skeleton_svg_comparison, export_gltf_json)

# Start with female V
sim.start_session(player_pos=(0, 0, 0), body_type=BodyType.WomanAverage)

# Create a deformation rig (mirrors community rig-deforming workflow)
rig = DeformationRig(name="curvy_v", body_type=BodyType.WomanAverage)
rig.SetBoneScaleSymmetric("Thigh_l", 1.25, 1.0, 1.15)  # both _l and _r
rig.SetBoneScale("Chest", 1.15, 1.0, 1.1)
sim.apply_deformation_rig(rig)           # auto-creates FPP variant too

# Apply morph targets and visual scale
sim.apply_player_morph("BodyFat", "UpperBody", 0.3)
sim.set_player_visual_scale(1.02, 1.0, 1.02)

# ── Visual verification ──────────────────────────────────────────────────────
# Snapshot: capture visual state as data, compare before/after
before = sim.capture_player_snapshot()
sim.set_player_visual_scale(1.5, 1.0, 1.5)
after = sim.capture_player_snapshot()
assert after.differs_from(before)        # proves V changed visually
diff = after.diff(before)                # structured delta dict

# SVG: 2D wireframe skeleton diagram (green = identity, orange = modified)
svg = generate_skeleton_svg(rig=rig, title="Curvy V Rig")
# write_svg(svg, "/tmp/skeleton.svg")   # open in any browser

# SVG comparison: before/after overlay (changed bones highlighted in red)
svg_cmp = generate_skeleton_svg_comparison(rig_before=None, rig_after=rig)

# glTF: export for 3D viewer (gltf-viewer.donmccurdy.com, Blender, three.js)
gltf_json = export_gltf_json(rig=rig, output_path="/tmp/skeleton.gltf")
```

---

## Adding Tests for a New Mod

1. Create `tests/mods/test_your_mod.py`
2. Port your mod's core logic to Python (it talks to the same simulated engine)
3. Write `unittest.TestCase` classes

### Minimal example (entity system)

```python
import unittest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import GameSimulation, Vector4

class TestMyMod(unittest.TestCase):
    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_npc_spawns(self):
        npc = self.sim.spawn_npc(tags=["MyTag"], pos=(10, 5, 0))
        pos = npc.GetWorldPosition()
        self.assertAlmostEqual(pos.X, 10.0)
```

### Full mechanics example

```python
from engine import (GameSimulation, CharacterStats, StatsSystem,
                    NPCStats, DamageSystem, HitFlag,
                    EquipmentSlot, TweakDB)

class TestWeaponMod(unittest.TestCase):
    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session()

    def tearDown(self):
        self.sim.teardown()

    def test_modded_weapon_deals_more_damage(self):
        # Override weapon damage via TweakDB SetFlat (like TweakXL does)
        self.sim.tweakdb.SetFlat(
            "Items.Preset_Yukimura_Default.damagePerHit", 500.0)

        target = NPCStats(max_health=1000.0, current_health=1000.0, armor=0.0)
        hit = self.sim.resolve_hit(
            "Items.Preset_Yukimura_Default", target, rng_seed=0)
        self.assertGreater(hit.damage_dealt, 400.0)

    def test_perk_increases_damage(self):
        self.sim.player_stats.add_perk("Perks.Assassin")
        target = NPCStats(max_health=200.0, current_health=200.0, armor=0.0)
        hit = self.sim.resolve_hit(
            "Items.Preset_Yukimura_Default",
            target,
            flags=HitFlag.Unaware,
            rng_seed=0)
        self.assertAlmostEqual(hit.stealth_bonus, 0.10)
```

### AMM-style companion mod example

```python
from engine import (GameSimulation, AIFollowerRole, AINoRole,
                    gameGodModeType, EAIAttitude)

class TestCompanionMod(unittest.TestCase):
    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_companion_follows_player(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC", "Companion"], pos=(5, 0, 0))
        self.sim.set_companion(npc)

        ctrl = npc.GetAIControllerComponent()
        self.assertTrue(ctrl.IsFollower())
        self.assertFalse(ctrl.IsHostile())

    def test_god_mode_survives_toggle(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0))
        self.sim.set_companion(npc)
        self.sim.set_god_mode(npc, immortal=True)

        # Toggle hostile and back
        self.sim.toggle_hostile(npc)
        self.sim.toggle_hostile(npc)

        # God mode persists across role changes
        eid = npc.GetEntityID()
        self.assertTrue(self.sim.god_mode.IsImmortal(eid))

    def test_appearance_change_logs_history(self):
        npc = self.sim.spawn_npc(tags=["AMM_NPC"], pos=(5, 0, 0),
                                  appearance="judy_default")
        self.sim.change_appearance(npc, "judy_summer")
        self.sim.change_appearance(npc, "judy_winter")

        history = npc.GetAppearanceHistory()
        self.assertIn("judy_summer", history)
        self.assertIn("judy_winter", history)
        self.assertEqual(npc.GetCurrentAppearanceName(), "judy_winter")
```

---

## Key Simulation API

```python
sim = GameSimulation()

# ── Session lifecycle ────────────────────────────────────────────────────────
sim.start_session(player_pos=(x, y, z), player_yaw=90)
sim.end_session()

# ── Spawn entities ────────────────────────────────────────────────────────────
npc = sim.spawn_npc(tags=["AMM", "Companion"], pos=(10, 0, 0), yaw=45)
npc = sim.spawn_npc(tags=["Enemy"], pos=(20, 0, 0), npc_stats=NPCStats(max_health=300))

# ── Time ──────────────────────────────────────────────────────────────────────
sim.tick(count=4, interval=0.25)    # 4 ticks at 0.25s
sim.advance_time(1.0)               # 1 second instant

# ── Input ─────────────────────────────────────────────────────────────────────
sim.press_key(EInputKey.IK_F6)

# ── Player movement ───────────────────────────────────────────────────────────
sim.move_player(pos=(50, 50, 0), yaw=180)

# ── TweakDB ───────────────────────────────────────────────────────────────────
weapon   = sim.tweakdb.GetRecord("Items.Preset_Yukimura_Default")
old_dmg  = sim.tweakdb.GetFlat("Items.Preset_Yukimura_Default.damagePerHit")
sim.tweakdb.SetFlat("Items.Preset_Yukimura_Default.damagePerHit", 9999.0)
sim.tweakdb.CloneRecord("AMM_Character.MyNPC", "Character.Base_NPC")

# ── Player stats ──────────────────────────────────────────────────────────────
sim.player_stats.set_attribute("Reflexes", 20)
sim.player_stats.set_skill("Handguns", 20)
sim.player_stats.add_perk("Perks.DeadlyPrecision")
snap = StatsSystem.snapshot(sim.player_stats)

# ── Inventory / economy ───────────────────────────────────────────────────────
item_id = sim.give_item("player", "Items.MaxDOC", 5)
eddies  = sim.give_money("player", 50_000)
sim.equip_item("player", "Items.Preset_Yukimura_Default", EquipmentSlot.WeaponRight)

# ── Combat ────────────────────────────────────────────────────────────────────
target = NPCStats(max_health=500.0, current_health=500.0, armor=60.0)
hit    = sim.resolve_hit("Items.Preset_Yukimura_Default", target,
                          flags=HitFlag.Headshot, rng_seed=42)
target.take_damage(hit.damage_dealt)

# ── Quests / facts ────────────────────────────────────────────────────────────
sim.set_fact("met_panam", 1)
value = sim.get_fact("met_panam")
sim.quests.AddFact("gig_count", 1)

# ── Log ───────────────────────────────────────────────────────────────────────
messages = sim.get_log()
sim.clear_log()

# ── Cleanup ───────────────────────────────────────────────────────────────────
sim.teardown()
```

---

## Accuracy Notes

All mechanics formulas match real CP2077 observed values at these checkpoints:

| Checkpoint | Expected | Simulated |
|---|---|---|
| Default V HP (Lvl 1, Body 3) | ~130 HP | 125–145 HP |
| Maxed Body build HP (Lvl 50, Body 20, Athletics 20, Invincible) | ~1100–1300 | 1100–1300 |
| Armor 60 → mitigation | 50% | 50.0% |
| Armor 240 → mitigation | ~80% | 80.0% |
| Armor 85% cap | 85% | 85.0% |
| Crit chance, Reflexes 3 (default) | ~3–8% | 6.0% |
| Burning total damage | ~120 | 120 |
| Bleeding total damage | ~30 | 30 |
| Ranged headshot multiplier | 2.0× | 2.0× |
| Street Cred level 2 XP | 500 XP | 500 XP |
| AMM follow distance (1-2 companions) | 2.0 m | 2.0 m |
| AMM follow distance (3 companions) | 3.5 m | 3.5 m |
| AMM follow distance (4+ companions) | 5.0 m | 5.0 m |
| TweakDB CloneRecord isolation | independent | independent |
| GodMode multi-reason (clear one, keep other) | stays immortal | stays immortal |

---

## Performance Benchmarks

The engine maintains these performance bounds (validated by `TestMultiCompanionStress`):

| Operation | Bound | Notes |
|---|---|---|
| Spawn 100 NPCs | < 1000 ms | DES dual-index architecture |
| Update follow distances (100 companions) | < 500 ms | AICommand queue |
| Distance check + reissue (100 companions) | < 200 ms | Vector4 distance math |
| Schedule 1000 delayed callbacks | < 500 ms | heapq O(n log n) |
| Fire 1000 callbacks via Tick | all 1000 fired | heapq Tick correctness |
| `GetTags(eid)` | O(1) | reverse index lookup |
| `DeleteEntity` | O(T) where T = tag count | no full-scan |

---

## What's NOT Simulated

- UI / ink widget system (ImGui overlay)
- AI behaviour trees / NPC navigation mesh
- Physics / raycasting / collision
- Visual rendering (SVG diagrams and glTF export provide offline verification)
- Audio / sound effects
- File I/O / save system internals
- Network / multiplayer
- Full TweakDB (only ~60 representative records seeded; extend via `CloneRecord`/`SetFlat`)
