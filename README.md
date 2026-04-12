---
description: Welcome to the Cyberpunk 2077 modding wiki!
---

# Home

This is the dedicated repository for all those that want to reference the API, and learn about modifying CyberPunk 2077 to make the game yours. [Get Started](modding-guides/world-editing/native-interactions-framework/getting-started.md)!

> #### <mark style="color:blue;">Coming from github?  We're editing on</mark> [<mark style="color:blue;">Gitbook</mark>](https://wiki.redmodding.org/cyberpunk-2077-modding/) <mark style="color:blue;">these days!</mark>

<div data-full-width="true"><figure><img src=".gitbook/assets/Type=Down.png" alt=""><figcaption></figcaption></figure></div>

{% hint style="success" %}
**Make this wiki better**! \
[Become an editor](https://app.gitbook.com/invite/-MP5ijqI11FeeX7c8-N8/H70HZBOeUulIpkQnBLK7), share your knowledge so others may learn, check out our [Discord Server](https://discord.gg/redmodding).
{% endhint %}

<table data-card-size="large" data-column-title-hidden data-view="cards"><thead><tr><th></th><th data-hidden></th><th data-hidden></th><th data-hidden data-card-cover data-type="files"></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead><tbody><tr><td>Modding Troubleshooting</td><td></td><td></td><td><a href=".gitbook/assets/using_mods.png">using_mods.png</a></td><td><a href="for-mod-users/user-guide-troubleshooting/">user-guide-troubleshooting</a></td></tr><tr><td>Mod Dev - Getting Started</td><td></td><td></td><td><a href=".gitbook/assets/making_mods.png">making_mods.png</a></td><td><a href="/broken/pages/SYwU6v32aY3CipwSk8ZP">Broken link</a></td></tr></tbody></table>

<div data-full-width="true"><figure><img src=".gitbook/assets/Type=Up.png" alt=""><figcaption></figcaption></figure></div>

---

## RED4 Engine Simulator & Offline Test Framework

> **Test your mods without launching the game.**

This repository ships a complete Python-based offline simulation of Cyberpunk 2077's RED4 engine, located in [`tests/`](tests/).  
It lets you run your mod logic against an accurate engine simulation — no game install, no loading screens, no restarts.

### What's covered

| System | What's simulated |
|---|---|
| **Entity / World** | `DynamicEntitySystem`, `Entity` positions & RTTI, `WorldTransform`, `DelaySystem`, `CallbackSystem` |
| **TweakDB** | FNV-1a hashed record IDs · 50+ seeded weapon / armor / cyberware / perk records · `GetFlat` / `SetFlat` override API |
| **Stats** | All 5 attributes · 12 skills · 20+ perks · accurate HP / Stamina / RAM / Crit / Armor formulas |
| **Combat** | Full 11-step damage pipeline · status effects (Burning, Bleeding, Poison, Shock, EMP) · weapon state |
| **Inventory** | `TransactionSystem` · `EquipmentSystem` · eddies (€$) · Street Cred levels 1–50 |
| **Quests** | `FactManager` (case-insensitive fact store) · quest phase graph executor · `JournalManager` |

### Quick start

```bash
# Requires Python 3.9+, zero external dependencies
python tests/run_tests.py
```

308 tests across 5 test suites validate all mechanics against real-game observed values.

**Full documentation:** [`tests/README.md`](tests/README.md)

