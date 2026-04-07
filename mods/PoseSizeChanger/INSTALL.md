# Pose Size Changer -- Full Installation Guide

This guide walks you through installing **Pose Size Changer v1.0.2** and all of its dependencies from scratch.

---

## Prerequisites

You need **four** framework mods installed before Pose Size Changer will work. Install them in this order:

### 1. RED4ext (v1.29+)

RED4ext is the native plugin loader that makes Redscript and Codeware possible.

- **Download:** https://www.nexusmods.com/cyberpunk2077/mods/2380
- **Install:** Extract into your game directory. You should have:
  ```
  Cyberpunk 2077/bin/x64/plugins/RED4ext.dll
  ```
- **Verify:** Launch the game. If RED4ext is working, you'll see a `red4ext/logs/red4ext.log` file after launch.

### 2. Redscript (v0.5.31+)

Redscript is the scripting compiler that processes `.reds` script files.

- **Download:** https://www.nexusmods.com/cyberpunk2077/mods/1511
- **Install:** Extract into your game directory. You should have:
  ```
  Cyberpunk 2077/r6/scripts/                (script folder)
  Cyberpunk 2077/engine/tools/scc.exe       (compiler)
  ```
- **Verify:** After launching the game with Redscript installed, check:
  ```
  Cyberpunk 2077/r6/cache/modded/final.redscripts.log
  ```
  It should say "Compilation complete" with no errors.

### 3. Codeware (v1.19+)

Codeware provides the ScriptableSystem framework, entity APIs, and callback system that Pose Size Changer depends on.

- **Download:** https://www.nexusmods.com/cyberpunk2077/mods/7780
- **Install:** Extract into your game directory. You should have:
  ```
  Cyberpunk 2077/red4ext/plugins/Codeware/Codeware.dll
  Cyberpunk 2077/r6/scripts/Codeware/       (many .reds files)
  ```
- **Verify:** Launch the game. Codeware logs to its own log file in `red4ext/plugins/Codeware/`.

### 4. Cyber Engine Tweaks (v1.37+)

CET provides the in-game overlay UI (the ~ menu) and Lua scripting for the control panel.

- **Download:** https://www.nexusmods.com/cyberpunk2077/mods/107
- **Install:** Extract into your game directory. You should have:
  ```
  Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks.asi
  Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/
  ```
- **Verify:** Launch the game and press `~` (tilde). The CET console should open.

---

## Installing Pose Size Changer

### Step 1: Download

Download `PoseSizeChanger-v1.0.2.zip` from the GitHub releases page:
https://github.com/sinica57pls-dot/CP2077/releases

### Step 2: Extract

Extract the ZIP directly into your **Cyberpunk 2077 game directory**. The ZIP is structured so that files land in the correct locations automatically.

After extraction you should have these files:

```
Cyberpunk 2077/
  r6/
    scripts/
      PoseSizeChanger/
        Module.reds                    <-- Module declaration
        Config.reds                    <-- Configuration (hotkeys, defaults)
        PoseSizeChangerSystem.reds     <-- Core system logic
  bin/
    x64/
      plugins/
        cyber_engine_tweaks/
          mods/
            PoseSizeChanger/
              init.lua                 <-- CET overlay UI
```

### Step 3: Verify File Placement

Double-check these paths exist (relative to your game directory):

| File | Purpose |
|------|---------|
| `r6/scripts/PoseSizeChanger/Module.reds` | Module declaration |
| `r6/scripts/PoseSizeChanger/Config.reds` | Configurable settings |
| `r6/scripts/PoseSizeChanger/PoseSizeChangerSystem.reds` | Core scaling system |
| `bin/x64/plugins/cyber_engine_tweaks/mods/PoseSizeChanger/init.lua` | CET overlay |

### Step 4: Launch the Game

1. Start Cyberpunk 2077
2. **Load a save game** (the system activates after a save is loaded, not on the main menu)
3. Press `~` to open the CET overlay
4. Find the **"Pose Size Changer"** window

### Step 5: Test It Works

1. In the CET overlay, click **"Run Diagnostics"**
2. All checks should show **PASS** (green) or **INFO** (blue)
3. Any **FAIL** (red) items tell you what's missing
4. Try clicking **"Apply to Player V"** -- your character should grow to 1.2x size
5. Click **"Reset Player V"** to return to normal

---

## How to Use

### Quick Start (Hotkeys)

1. Look at any character (NPC, AMM-spawned entity, Photo Mode puppet, or Player V)
2. Press **F9** to scale them up (default 1.2x)
3. Press **F10** to reset them back to normal size

### Full Control Panel (CET Overlay)

1. Press `~` to open CET
2. In the Pose Size Changer window:
   - **Refresh Target** -- aim at a character, then click to select them
   - **Scale slider** -- drag to set scale (0.5x to 3.0x)
   - **Presets** -- quick buttons for common scales
   - **Apply to Target** -- scale the aimed character
   - **Reset Target** -- reset the aimed character to 1.0x
   - **Apply to Player V** -- scale yourself directly
   - **Reset Player V** -- reset yourself to 1.0x
   - **Reset ALL Entities** -- reset every scaled entity at once
   - **Active Scales** -- see all currently scaled entities and their factors
   - **Diagnostics** -- check if all dependencies are working

### Photo Mode

1. Enter Photo Mode
2. Spawn or pose a character
3. Exit Photo Mode briefly (press Escape)
4. Aim at the character and press F9 (or use CET overlay)
5. Re-enter Photo Mode -- the scale persists through pose changes!

---

## Configuration

Edit `r6/scripts/PoseSizeChanger/Config.reds` with any text editor:

```swift
// Default scale when pressing F9 (1.2 = 120% size)
public static func DefaultScale() -> Float = 1.20

// How far away (metres) you can target an entity
public static func MaxTargetDistance() -> Float = 25.0

// Aiming cone size (0.92 = ~23 degree cone)
public static func MinDotProduct() -> Float = 0.92

// Hotkey to apply scale
public static func ApplyKey() -> EInputKey = EInputKey.IK_F9

// Hotkey to reset scale
public static func ResetKey() -> EInputKey = EInputKey.IK_F10

// How often scale is reapplied to survive pose changes (seconds)
public static func TickInterval() -> Float = 0.5
```

After editing, restart the game for changes to take effect (Redscript compiles on launch).

---

## Troubleshooting

### "System not loaded" in CET overlay

This means the Redscript system didn't compile or initialize. Check:

1. **Is RED4ext installed?**
   - Look for: `bin/x64/plugins/RED4ext.dll`
   - Check: `red4ext/logs/red4ext.log` for errors

2. **Is Redscript installed?**
   - Look for: `engine/tools/scc.exe`
   - Check: `r6/cache/modded/final.redscripts.log` for compilation errors

3. **Is Codeware installed?**
   - Look for: `red4ext/plugins/Codeware/Codeware.dll`
   - Look for: `r6/scripts/Codeware/` folder with `.reds` files

4. **Did scripts compile successfully?**
   - Open: `r6/cache/modded/final.redscripts.log`
   - Search for "error" or "PoseSizeChanger"
   - If there are errors, another mod may be conflicting

5. **Did you load a save?**
   - The system only activates after loading a game save
   - It will NOT work on the main menu

### "System loaded but not active"

- You're on the main menu or between saves
- Load a game save to activate the system

### Scale doesn't stick / resets immediately

- This usually means another mod is also modifying `visualScale` on mesh components
- Run Diagnostics to check for conflicts
- Try increasing the tick interval in Config.reds (e.g., 0.3 instead of 0.5)

### CET overlay doesn't show Pose Size Changer window

- Check that `init.lua` is in the correct path:
  `bin/x64/plugins/cyber_engine_tweaks/mods/PoseSizeChanger/init.lua`
- Check CET's log for Lua errors:
  `bin/x64/plugins/cyber_engine_tweaks/scripting.log`

### F9/F10 hotkeys don't work

- Make sure CET hotkey bindings aren't conflicting
- The hotkeys require the **CallbackSystem** from Codeware
- Run Diagnostics -- check that "CallbackSystem" shows PASS

### Nothing happens when I click "Apply to Target"

- You need to aim at a character first
- Click "Refresh Target" to verify the targeting works
- Move closer -- default max distance is 25 metres
- The target must be an NPC, puppet, or player character (not vehicles/objects)

---

## Compatibility

### Works with:
- **Any pose pack** (Sharp Dressed Man, Nibbles Replacer poses, etc.)
- **AMM** (Appearance Menu Mod) -- detects AMM-spawned entities automatically
- **PhotoModeScale** -- compatible but redundant (you don't need both)
- **Appearance Change Unlocker**
- **All vanilla game content**

### Potential conflicts:
- Other mods that modify `MeshComponent.visualScale` at runtime
- Mods that override the same Redscript classes (very rare)
- Use the built-in **Diagnostics** panel to detect conflicts

---

## Uninstalling

Delete these files/folders from your game directory:

```
r6/scripts/PoseSizeChanger/           (entire folder)
bin/x64/plugins/cyber_engine_tweaks/mods/PoseSizeChanger/   (entire folder)
```

The framework mods (RED4ext, Redscript, Codeware, CET) can stay -- other mods likely depend on them.

---

## Version History

- **v1.0.2** -- Critical bug fixes (EntityID.ToHash, CET ImGui compatibility), added diagnostics panel, mod conflict detection, full installation guide
- **v1.0.1** -- Optimization pass, FTLog fix, per-frame targeting fix, mesh component coverage, stale entity cleanup
- **v1.0.0** -- Initial release

---

## Support

If the built-in diagnostics can't identify the issue:

1. Open `r6/cache/modded/final.redscripts.log` and search for errors
2. Open `red4ext/logs/red4ext.log` and check for plugin failures
3. Open `bin/x64/plugins/cyber_engine_tweaks/scripting.log` for CET errors
4. Report the issue on GitHub: https://github.com/sinica57pls-dot/CP2077/issues
