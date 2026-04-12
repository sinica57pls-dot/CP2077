Add a new system to the CP2077 offline engine simulator.

The argument ($ARGUMENTS) describes the system to add (e.g. "VehicleSystem" or "CraftingSystem").

## Steps

Read `tests/AI_CONTEXT.md` section "How to Add a New Engine System" first, then:

1. **Identify the right module** — does it belong in `world.py`, or should a new
   `tests/engine/<system>.py` be created?

2. **Implement the class** following the pattern of existing systems. Key conventions:
   - Constructor takes no arguments (or only primitives)
   - Methods mirror the real REDscript API where possible
   - Include a `Reset()` or `Clear()` method for test isolation
   - If the system has time-based state, add a `Tick(dt: float)` method

3. **Export** from `tests/engine/__init__.py` (follow the existing blocks)

4. **Wire** into `GameSimulation` in `tests/engine/simulation.py`:
   ```python
   # in __init__:
   self.<system_name> = <ClassName>()
   gi._current_<system_name> = self.<system_name>
   ```

5. **Declare globals** in `tests/engine/game_instance.py`:
   ```python
   _current_<system_name> = None
   ```
   Add accessor to `GameInstance`:
   ```python
   @staticmethod
   def Get<SystemName>():
       return _current_<system_name>
   ```
   Add reset in `_reset_globals()`:
   ```python
   _current_<system_name> = None
   ```

6. **Write tests** in `tests/mods/test_<system_name>.py` (or add a suite to an existing test file)

7. **Update documentation**:
   - Add a row to the "World Systems (AMM)" table in `tests/README.md`
   - Add a section to `tests/AI_CONTEXT.md` under "System-by-System Reference"
   - Add a bullet to `SUMMARY.md` under "For Mod Creators: Testing"

## Reference implementations

Simplest system (stateless): `WorkspotSystem` in `world.py`
Medium system (state + history): `WeatherSystem` in `world.py`
Complex system (multi-entity + reasons): `GodModeSystem` in `world.py`
Very complex (dual-index, lifecycle): `DynamicEntitySystem` in `systems.py`
