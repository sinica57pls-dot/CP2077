"""
RED4 Engine Simulation -- Visual State Snapshot
===============================================

Captures the complete visual state of an entity for comparison and
regression testing.  Answers the question "did V actually change
visually?" at the data level.

Aggregates data from:
  src/App/Entity/VisualScaleEx.cpp    -- per-component visual scale
  src/Red/MorphTarget.hpp             -- morph target blend weights
  src/App/Entity/EntityEx.cpp         -- entity component iteration
  DeformationRig (.rig files)         -- bone transform scales

Usage:
    before = VisualSnapshot.capture(sim.player)
    sim.apply_deformation_rig(rig)
    after  = VisualSnapshot.capture(sim.player)
    assert after.differs_from(before)
    print(after.diff(before))
"""

import copy
from typing import Any, Dict, List, Optional


def _serialize_rig(rig) -> Optional[Dict[str, Any]]:
    """Convert a DeformationRig to a JSON-friendly dict."""
    if rig is None:
        return None
    bones = {}
    for name, bt in rig.GetAllBones().items():
        bones[name] = {
            "scaleX": bt.scaleX,
            "scaleY": bt.scaleY,
            "scaleZ": bt.scaleZ,
        }
    return {
        "name": rig.name,
        "body_type": rig.body_type.value if hasattr(rig.body_type, 'value') else str(rig.body_type),
        "is_player_rig": rig._is_player_rig,
        "bones": bones,
    }


def _serialize_component(comp) -> Dict[str, Any]:
    """Extract visual properties from any mesh component."""
    data: Dict[str, Any] = {
        "type": type(comp).__name__,
        "mesh_path": getattr(comp, '_mesh_path', ""),
        "appearance": str(getattr(comp, 'meshAppearance', "")),
        "visible": getattr(comp, '_visible', True),
        "temp_hidden": getattr(comp, '_temp_hidden', False),
    }

    # Visual scale (use list, not tuple, for JSON roundtrip fidelity)
    if hasattr(comp, 'GetVisualScale'):
        v = comp.GetVisualScale()
        data["visual_scale"] = [v.X, v.Y, v.Z]
    else:
        data["visual_scale"] = [1.0, 1.0, 1.0]

    # Morph targets (only on entMorphTargetSkinnedMeshComponent)
    if hasattr(comp, 'GetAppliedMorphTargets'):
        morphs = {}
        for entry in comp.GetAppliedMorphTargets():
            morphs[entry.target] = {
                "target": entry.target,
                "region": entry.region,
                "value": entry.value,
            }
        data["morph_targets"] = morphs
    else:
        data["morph_targets"] = {}

    return data


def _deep_diff(a: Any, b: Any, path: str = "") -> Dict[str, Any]:
    """
    Recursively compare two values and return a dict of differences.
    Only fields that differ are included.  Empty dict = identical.
    """
    diffs: Dict[str, Any] = {}

    if type(a) != type(b):
        diffs[path or "root"] = {"before": a, "after": b}
        return diffs

    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            val_a = a.get(key)
            val_b = b.get(key)
            if val_a is None and val_b is not None:
                diffs[child_path] = {"before": None, "after": val_b}
            elif val_a is not None and val_b is None:
                diffs[child_path] = {"before": val_a, "after": None}
            elif val_a != val_b:
                sub = _deep_diff(val_a, val_b, child_path)
                diffs.update(sub)
        return diffs

    if isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            child_path = f"{path}[{i}]"
            if i >= len(a):
                diffs[child_path] = {"before": None, "after": b[i]}
            elif i >= len(b):
                diffs[child_path] = {"before": a[i], "after": None}
            elif a[i] != b[i]:
                sub = _deep_diff(a[i], b[i], child_path)
                diffs.update(sub)
        return diffs

    if isinstance(a, float) and isinstance(b, float):
        if abs(a - b) > 1e-6:
            diffs[path or "root"] = {"before": a, "after": b}
        return diffs

    if a != b:
        diffs[path or "root"] = {"before": a, "after": b}

    return diffs


class VisualSnapshot:
    """
    Immutable capture of an entity's complete visual state.

    Captures:
      - body_type (PlayerPuppet only, else None)
      - mesh_components: list of serialised component dicts
      - deformation_rig / deformation_rig_fpp (PlayerPuppet only)
    """

    __slots__ = ('_data',)

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @staticmethod
    def capture(entity) -> "VisualSnapshot":
        """
        Capture the current visual state of any Entity.

        Walks all components, extracting mesh paths, visual scales,
        visibility, morph targets, and (for PlayerPuppet) deformation
        rigs and body type.
        """
        data: Dict[str, Any] = {}

        # Body type (PlayerPuppet only)
        if hasattr(entity, '_body_type'):
            bt = entity._body_type
            data["body_type"] = bt.value if hasattr(bt, 'value') else str(bt)
        else:
            data["body_type"] = None

        # Mesh components
        components: List[Dict[str, Any]] = []
        if hasattr(entity, 'GetComponents'):
            for comp in entity.GetComponents():
                if hasattr(comp, 'IsA') and comp.IsA("MeshComponent"):
                    components.append(_serialize_component(comp))
        data["mesh_components"] = components

        # Deformation rigs (PlayerPuppet only)
        if hasattr(entity, '_deformation_rig'):
            data["deformation_rig"] = _serialize_rig(entity._deformation_rig)
        else:
            data["deformation_rig"] = None

        if hasattr(entity, '_deformation_rig_fpp'):
            data["deformation_rig_fpp"] = _serialize_rig(
                entity._deformation_rig_fpp)
        else:
            data["deformation_rig_fpp"] = None

        return VisualSnapshot(data)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable deep copy of the full visual state."""
        return copy.deepcopy(self._data)

    def differs_from(self, other: "VisualSnapshot") -> bool:
        """Return True if any visual property differs between snapshots."""
        return bool(self.diff(other))

    def diff(self, other: "VisualSnapshot") -> Dict[str, Any]:
        """
        Return a dict describing all differences between self and other.

        Only fields that differ are included.  Empty dict = identical.
        Keys use dot-notation paths (e.g. "deformation_rig.bones.Thigh_l.scaleX").
        """
        return _deep_diff(self._data, other._data)

    def __repr__(self):
        bt = self._data.get("body_type", "?")
        nc = len(self._data.get("mesh_components", []))
        has_rig = self._data.get("deformation_rig") is not None
        return f"VisualSnapshot(body={bt}, components={nc}, rig={has_rig})"
