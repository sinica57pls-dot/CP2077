# AMM Companion Close-Follow + Voice Lines

Makes AMM-spawned companions (and any dynamically spawned NPCs) actually **follow you closely** and **talk with voice lines** from the game.

## Features

### Close-Follow (F6)

When toggled ON, every AMM companion stays right next to you:

| Situation | What happens |
|-----------|-------------|
| Companion is **> 15 m** away | **Instant teleport** right behind you |
| Companion is **3 - 15 m** away | **Smooth movement** toward you every 0.25 s |
| Companion is **< 3 m** away | **Nothing** -- they're close enough, personal space respected |

### Voice Lines (F7) -- *New in v1.0.1*

Press **F7** near any AMM-spawned NPC to make them:

1. **Turn to look at you** -- the NPC turns their head/body to face V
2. **Speak a voice line** -- a random line from the game's built-in voice bank for that NPC archetype
3. **Show a facial expression** -- randomized talking/smiling/reacting animations
4. **Reset naturally** -- expression returns to neutral after a few seconds

Each NPC archetype has its own voice bank, so the same companion will say different things each time. There's an 8-second cooldown per NPC to prevent spam.

You can also trigger voice lines from the CET overlay with the **"Talk to Nearest Companion"** button.

## Installation

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
    CompanionVoiceSystem.reds        <-- NEW in v1.0.1
  bin/x64/plugins/cyber_engine_tweaks/mods/AMMCompanionClose/
    init.lua
```

## Usage

1. Start the game and load a save
2. Open AMM and spawn an NPC companion
3. Press **F6** to enable close-follow mode
4. Walk/run/drive around -- the companion stays right behind you
5. Press **F7** near a companion to make them talk to you
6. Press **F6** / **F7** again as needed

### CET Overlay

Open the CET overlay (`~` key) and you'll see a **Companion Close-Follow + Voice** window with:
- A toggle button for close-follow (ON/OFF)
- A **"Talk to Nearest Companion"** button
- Status display and hotkey reminders

## Configuration

Edit `r6/scripts/AMMCompanionClose/Config.reds` to change:

### Close-Follow Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `TeleportDistance` | `15.0` | Beyond this, NPC is teleported instantly |
| `FollowDistance` | `3.0` | Beyond this, NPC is smoothly moved closer |
| `TargetDistance` | `1.8` | How close to V the NPC ends up |
| `TickInterval` | `0.25` | Seconds between position checks (lower = smoother) |
| `LerpFactor` | `0.45` | How fast the smooth movement is (0-1, higher = faster) |
| `ToggleKey` | `IK_F6` | Which key toggles close-follow |

### Voice Line Settings (v1.0.1)

| Setting | Default | Description |
|---------|---------|-------------|
| `TalkKey` | `IK_F7` | Which key triggers "talk to nearest" |
| `VoiceCooldown` | `8.0` | Seconds between voice lines per NPC |
| `VoiceMaxDistance` | `12.0` | Max distance (m) to detect companions for talking |
| `VoiceLineDuration` | `4.0` | How long facial animation plays before reset |
| `VoiceLookAtDuration` | `5.0` | How long the NPC looks at you after talking |

## For Mod Authors

Other mods can interact with both systems via Redscript:

```swift
// Get the close-follow system
let followSys = GameInstance.GetScriptableSystemsContainer()
    .Get(n"AMMCompanionClose.CompanionCloseSystem")
    as AMMCompanionClose.CompanionCloseSystem;

// Toggle close-follow programmatically
followSys.SetEnabled(true);
followSys.SetEnabled(false);
let on: Bool = followSys.IsEnabled();

// Register custom entity tags
followSys.RegisterTag(n"MyModCompanions");

// Get the voice system
let voiceSys = GameInstance.GetScriptableSystemsContainer()
    .Get(n"AMMCompanionClose.CompanionVoiceSystem")
    as AMMCompanionClose.CompanionVoiceSystem;

// Make the nearest companion talk
voiceSys.TalkToNearest();

// Talk to a specific entity
voiceSys.TalkToEntity(someEntity);
```

## Changelog

### v1.0.1
- **NEW:** Voice line system -- press F7 to make companions talk
- **NEW:** Random voice lines from the game's native audio system
- **NEW:** Random facial animations (talking, smiling, reacting)
- **NEW:** Per-NPC cooldown system to prevent voice spam
- **NEW:** "Talk to Nearest Companion" button in CET overlay
- **NEW:** CompanionVoiceSystem Redscript API for mod integration
- **FIX:** NPCs no longer snap-rotate to face north after teleport (orientation preserved)
- **FIX:** DynamicEntitySystem reference now refreshes after session transitions
- **FIX:** Entity system stale reference check added to tick loop

### v1.0.0
- Initial release
- Close-follow system with teleport + lerp movement
- F6 hotkey toggle
- CET overlay with enable/disable button

## How It Works

### Close-Follow
Uses Codeware's `ScriptableSystem` with a `DelayCallback` tick (4 Hz). Each tick scans all entities tagged with AMM/Companion tags via `DynamicEntitySystem`, then either teleports (> 15m) or lerp-moves (3-15m) them toward V. Preserves NPC orientation during movement.

### Voice Lines
A second `ScriptableSystem` handles voice interactions. When triggered (F7 or overlay button), it:
1. Finds the nearest AMM-tagged entity within 12m
2. Activates `ReactionManagerComponent.ActivateReactionLookAt` for NPC-to-player facing
3. Calls `GameObject.PlayVoiceOver` with a randomly selected VO event
4. Applies `AnimFeature_FacialReaction` via `AnimationControllerComponent` for expressive animation
5. Schedules a `DelayCallback` to reset the facial animation after the line finishes

The voice lines come from the game's Wwise audio system -- each NPC archetype has its own bank of greeting/reaction audio, so the same VO event produces different spoken dialogue depending on the NPC.

## License

MIT -- do whatever you want with it.
