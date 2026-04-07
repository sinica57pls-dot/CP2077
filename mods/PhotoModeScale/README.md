# Photo Mode Scale -- Bigger Male V in Poses

Makes Male V appear **1.2x bigger** (20% larger) in Photo Mode, giving a more imposing, broader silhouette in every pose. Works with **any pose pack** including Rev's Sharp Dressed Man and all other photomode pose mods.

## Features

- Automatically scales Male V when Photo Mode opens
- Restores original scale when Photo Mode closes (no gameplay impact)
- **F8** hotkey to toggle on/off
- CET overlay with **live scale slider** (0.8x to 2.0x)
- Quick presets: 1.0x, 1.1x, 1.2x, 1.3x, 1.5x
- Gender-aware: only scales male body type by default
- Zero impact on normal gameplay

## Installation

Extract the zip into your Cyberpunk 2077 game directory:

```
Cyberpunk 2077/
  r6/scripts/PhotoModeScale/
    Module.reds
    Config.reds
    PhotoModeScaleSystem.reds
  bin/x64/plugins/cyber_engine_tweaks/mods/PhotoModeScale/
    init.lua
```

## Requirements

- Cyberpunk 2077 v2.31+
- RED4ext 1.29+
- Redscript 0.5.31+
- Codeware 1.19+
- Cyber Engine Tweaks 1.37+ (for overlay; optional)

## Configuration

Edit `r6/scripts/PhotoModeScale/Config.reds` to change defaults:

- `ScaleFactor()` -- default 1.20 (1.2x)
- `MaleOnly()` -- default true (only scale male body type)
- `ToggleKey()` -- default F8
- `ScaleNPCs()` -- default false

Or use the CET overlay (~) to change scale live while in photo mode.

## How It Works

The mod hooks into `PhotoModePlayerEntityComponent.SetupInventory()` to detect when Photo Mode activates with a puppet. It then iterates all `MeshComponent` instances on the photo puppet and sets their `visualScale` to the configured factor. When Photo Mode closes, scale is restored to 1.0.

## Compatibility

Works alongside any pose pack (.archive/.xl/.yaml based). The scaling is applied at the mesh component level, independent of animation/pose data.

## License

MIT
