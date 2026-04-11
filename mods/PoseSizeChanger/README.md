# Pose Size Changer -- AMM-Style Entity Scaler

Aim at any character and scale them bigger or smaller. Works in Photo Mode, gameplay, and with any pose pack.

## How It Works

Just like AMM -- **aim at a character, then apply settings:**

1. Look at a character (Player V, AMM NPC, Photo Mode puppet)
2. Press **F9** to scale them up (default 1.2x)
3. Or open the CET overlay (~) for a full control panel with slider
4. Press **F10** to reset a character back to normal

The scale **persists through pose changes** -- switch poses all you want, the character stays big.

## Features

- **AMM-style targeting** -- look at a character to select them
- **Per-entity scaling** -- scale different characters by different amounts
- **Live scale slider** (0.5x to 3.0x) in CET overlay
- **Quick presets**: 0.8x, 1.0x, 1.1x, 1.2x, 1.5x, 2.0x
- **Apply to Player V** button for quick self-scaling
- **Reset individual** or **Reset ALL** buttons
- **Active scales list** showing all currently scaled entities
- **Persistent through pose changes** -- auto-reapplies every 0.5s
- **F9** hotkey to apply, **F10** to reset
- Works with **any pose pack** (Sharp Dressed Man, etc.)

## Installation

Extract the zip into your Cyberpunk 2077 game directory:

```
Cyberpunk 2077/
  r6/scripts/PoseSizeChanger/
    Module.reds
    Config.reds
    PoseSizeChangerSystem.reds
  bin/x64/plugins/cyber_engine_tweaks/mods/PoseSizeChanger/
    init.lua
```

## Requirements

- Cyberpunk 2077 v2.31+
- RED4ext 1.29+
- Redscript 0.5.31+
- Codeware 1.19+
- Cyber Engine Tweaks 1.37+ (for CET overlay; hotkeys work without it)

## Configuration

Edit `r6/scripts/PoseSizeChanger/Config.reds`:

- `DefaultScale()` -- default 1.20 (used by F9 hotkey)
- `MaxTargetDistance()` -- default 25.0 metres
- `MinDotProduct()` -- default 0.92 (~23 degree cone)
- `ApplyKey()` -- default F9
- `ResetKey()` -- default F10
- `TickInterval()` -- default 0.5s (scale reapplication frequency)

## Diagnostics

The mod includes a built-in workability checker. Open the CET overlay (~) and click **Run Diagnostics** to verify:

- System status and session state
- All framework dependencies (RED4ext, Redscript, Codeware, CET)
- Mesh component detection per type (skinned, morph, static)
- Cast path verification for each component type
- Tick loop status and scale persistence

## Compatibility

- Works alongside any pose pack (ArchiveXL .archive/.xl/.yaml based)
- Works alongside AMM (detects AMM-spawned entities)
- Compatible with the separate PhotoModeScale mod (but you don't need both)
- No conflicts with vanilla game systems

## Changelog

- **v2.0.0-alpha** -- NATIVE C++ BACKEND: Scale transforms now use Codeware's native SetVisualScale() method implemented as a RED4ext C++ RTTI expansion. SetVisualScale() resolves the visualScale field via RTTI property lookup at the C++ level and calls RefreshAppearance() after writing, forcing the renderer to pick up changes. This replaces the prior @addField-only approach which had no rendering guarantee. All prior fixes preserved.
- **v1.0.4** -- Audit cleanup: full static analysis verified 812 lines Redscript + 418 lines Lua + 18 framework files + 6 C++ sources. Removed phantom comment, fixed INSTALL.md version refs, deprecated dead code. No functional changes; core logic confirmed correct.
- **v1.0.3** -- CRITICAL FIX: Character scaling now actually works. Previous versions cast skinned mesh components to MeshComponent (always returned null because they are sibling classes, not parent-child). Fixed by exposing visualScale on entSkinnedMeshComponent and entMorphTargetSkinnedMeshComponent via @addField. Enhanced diagnostics with per-component-type breakdown and cast verification.
- **v1.0.2** -- Diagnostics panel, mod conflict detection, pcall crash safety
- **v1.0.1** -- Replaced FTLog with ModLog, added mesh component types, stale entity cleanup
- **v1.0.0** -- Initial release

## License

MIT
