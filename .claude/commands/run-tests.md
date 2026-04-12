Run the CP2077 offline engine test suite.

```bash
python tests/run_tests.py
```

If a specific suite is requested, run:
```bash
python -m unittest tests.mods.$ARGUMENTS -v
```

Available suites:
- `test_amm_full` — 155 tests, full AMM mod (15 suites)
- `test_amm_companion_close` — 84 tests, companion system
- `test_combat_system` — 53 tests
- `test_inventory_system` — 71 tests
- `test_stats_system` — 58 tests
- `test_tweakdb` — 42 tests

After running, report: total tests, failures, errors, and elapsed time.
If there are failures, read the failing test and the relevant engine module to diagnose.
