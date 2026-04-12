Scaffold a new mod test file for a Cyberpunk 2077 mod.

The argument ($ARGUMENTS) should be the mod name, e.g. "CyberCar" or "PhotoMode".

## Steps

1. Determine the file name: `tests/mods/test_<modname_lowercase>.py`
2. Ask the user what systems the mod uses (or infer from the mod name/description)
3. Create the file using this template, populated with relevant imports and at least
   one meaningful test per major system the mod touches:

```python
"""
<ModName> Test Suite
====================

Tests the <ModName> mod logic against the offline CP2077 engine simulator.
Source: <URL if provided>

Suites:
  1. Test<Core> — <brief>
  # add more suites as needed
"""

import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from engine import (
    GameSimulation,
    Vector4,
    # add other imports as needed
)


class Test<Core>(unittest.TestCase):

    def setUp(self):
        self.sim = GameSimulation()
        self.sim.start_session(player_pos=(0, 0, 0))

    def tearDown(self):
        self.sim.teardown()

    def test_placeholder(self):
        """Replace with real test."""
        self.assertIsNotNone(self.sim.player)


if __name__ == '__main__':
    unittest.main()
```

## Important rules

- Always call `self.sim.teardown()` in `tearDown()`
- Use `self.sim.spawn_npc(tags=[...], pos=(...))` to create NPCs
- Use `self.sim.timed(fn)` for performance-sensitive operations
- Consult `tests/AI_CONTEXT.md` for the full system API reference
- Consult `tests/README.md` for examples

After creating the file, confirm it's discoverable:
```bash
python -m unittest tests.mods.test_<modname> -v
```
