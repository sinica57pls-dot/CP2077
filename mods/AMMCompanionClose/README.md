# AMM Companion Close-Follow

Makes AMM-spawned companions (and any dynamically spawned NPCs) actually **follow you closely** instead of standing still or slowly drifting behind.

## The Problem

When you spawn an NPC in AMM and set them as a companion, the built-in companion distance settings (`Close`, `Default`, `Distance`) still leave the NPC standing around until you move *very* far away. They don't really track you in real-time -- they feel more like statues than companions.

## The Solution

This mod adds a toggleable **close-follow mode** that:

| Situation | What happens |
|-----------|-------------|
| Companion is **> 15 m** away | **Instant teleport** right behind you |
| Companion is **3 - 15 m** away | **Smooth movement** toward you every 0.25 s |
| Companion is **< 3 m** away | **Nothing** -- they're close enough, personal space respected |

Press **F6** to toggle it on/off at any time.

## Installation

Just place the folders in the game root folder.

### Requirements
- [Cyber Engine Tweaks](https://www.nexusmods.com/cyberpunk2077/mods/107) 1.37+
- [RED4ext](https://www.nexusmods.com/cyberpunk2077/mods/2380) 1.29+
- [Redscript](https://www.nexusmods.com/cyberpunk2077/mods/1511) 0.5.31+
- [Codeware](https://www.nexusmods.com/cyberpunk2077/mods/7780) 1.19+
- [Appearance Menu Mod (AMM)](https://www.nexusmods.com/cyberpunk2077/mods/790) (to spawn companions)

### Steps

1. Copy the `r6/` folder into your Cyberpunk 2077 game directory
2. Copy the `bin/` folder into your Cyberpunk 2077 game directory
3. Launch the game

Your file structure should look like:
```
Cyberpunk 2077/
  r6/scripts/AMMCompanionClose/
    Module.reds
    Config.reds
    CompanionCloseSystem.reds
  bin/x64/plugins/cyber_engine_tweaks/mods/AMMCompanionClose/
    init.lua
```

## Usage

1. Start the game and load a save
2. Open AMM and spawn an NPC companion
3. Press **F6** to enable close-follow mode
4. Walk/run/drive around -- the companion stays right behind you
5. Press **F6** again to disable

### CET Overlay

Open the CET overlay (`~` key) and you'll see a **Companion Close-Follow** window with a toggle button and status display.

## Configuration

Edit `r6/scripts/AMMCompanionClose/Config.reds` to change:

| Setting | Default | Description |
|---------|---------|-------------|
| `TeleportDistance` | `15.0` | Beyond this, NPC is teleported instantly |
| `FollowDistance` | `3.0` | Beyond this, NPC is smoothly moved closer |
| `TargetDistance` | `1.8` | How close to V the NPC ends up |
| `TickInterval` | `0.25` | Seconds between position checks (lower = smoother) |
| `LerpFactor` | `0.45` | How fast the smooth movement is (0-1, higher = faster) |
| `ToggleKey` | `IK_F6` | Which key toggles the feature |

## For Mod Authors

Other mods can interact with this system via redscript:

```swift
// Get the system
let sys = GameInstance.GetScriptableSystemsContainer()
    .Get(n"AMMCompanionClose.CompanionCloseSystem")
    as AMMCompanionClose.CompanionCloseSystem;

// Toggle programmatically
sys.SetEnabled(true);
sys.SetEnabled(false);

// Check state
let on: Bool = sys.IsEnabled();

// Register custom entity tags (if your mod uses its own tags)
sys.RegisterTag(n"MyModCompanions");
```

## How It Works

The mod uses Codeware's `ScriptableSystem` to register:

1. **Input callback** on F6 → toggles the feature
2. **DelayCallback tick** every 0.25 s → checks every dynamic entity's distance to V
3. **SetWorldTransform** → smoothly moves or teleports NPCs that are too far

It scans for entities tagged with common AMM/Codeware tags (`AMM`, `Companion`, etc.) and repositions them. It does **not** modify any game files or override any existing AMM behavior -- it's purely additive.

## Changelog

- **v1.0.4** -- Fixed critical tag mismatch: AMM uses `AMM_NPC` and `AMM_CAR` tags (confirmed from [AMM source](https://github.com/MaximiliumM/appearancemenumod), spawn.lua lines 522/603), not generic `AMM`/`Companion`. Without this fix the mod would not detect any AMM-spawned entities. Now scans `AMM_NPC`, `AMM_CAR`, `AMM`, and `Companion`.
- **v1.0.3** -- Fixed degenerate zero-quaternion orientation in `TeleportEntity` (was `(0,0,0,0)` instead of preserving the NPC's live facing via `GetWorldOrientation()`). Fixed teleport placement using full 3D forward vector which could put NPCs underground or mid-air on slopes/anims; now flattened to XY ground plane. Fixed stale `DynamicEntitySystem` wref not being refreshed across session loads.
- **v1.0.2** -- Fixed fatal compile errors: replaced `FTLog` (doesn't exist in Codeware) with `ModLog`, replaced `EntityID.GetHash` (doesn't exist) with `EntityID.ToHash`. Added pcall crash safety to all game API calls in CET overlay. Added `InvalidateSystem()` cleanup on shutdown.
- **v1.0.1** -- Replaced brute-force teleport with natural AI movement (sprint/run/walk tiers based on distance). Cancelled follow command when NPC is close enough so they stand still instead of backing away from the player.
- **v1.0.0** -- Initial release.

## License

MIT -- do whatever you want with it.
