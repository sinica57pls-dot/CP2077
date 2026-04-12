Audit the CP2077 offline engine simulator for consistency and correctness.

## What to check

1. **Import surface** — every class exported from `tests/engine/__init__.py` should
   exist in the source module it's claimed to come from. Run:
   ```
   grep "^from \." tests/engine/__init__.py
   ```
   Then verify each imported name exists in the corresponding file.

2. **GameSimulation wiring** — every system created in `GameSimulation.__init__`
   should have a corresponding `gi._current_*` assignment and should be reset
   in `gi._reset_globals()`. Cross-check `simulation.py` vs `game_instance.py`.

3. **Test method counts** — count `def test_` in each test file and verify the
   numbers match the table in `tests/README.md`:
   ```bash
   grep -c "def test_" tests/mods/test_amm_full.py
   grep -c "def test_" tests/mods/test_amm_companion_close.py
   # etc.
   ```

4. **Entity method coverage** — every method called on `NPCPuppet` or `PlayerPuppet`
   in the test files should exist in `tests/engine/entity.py`.

5. **System method coverage** — for each system, check that every method called in
   test files exists in the engine module.

## How to report

List: ✅ things that are consistent, ❌ things that are broken or missing.
For each ❌, specify exactly which file/line has the mismatch.
