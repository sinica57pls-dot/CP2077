"""
RED4 Engine Simulation -- Skeleton Visualization & Export
========================================================

Provides visual debugging tools for rig deformation:
  - CP2077_SKELETON: hardcoded humanoid bone hierarchy (front-view 2D positions)
  - generate_skeleton_svg(): SVG wireframe skeleton diagram
  - generate_skeleton_svg_comparison(): before/after overlay
  - export_gltf_json(): glTF 2.0 JSON export for 3D viewers

Uses an approximate CP2077 skeleton hierarchy based on the
community rig-deforming documentation:
  modding-guides/npcs/rig-deforming-for-v.md

Zero external dependencies -- uses only json, struct, base64, math, os
from the Python standard library.
"""

import json
import math
import os
import struct
import base64
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
#  CP2077 Skeleton Hierarchy
# =============================================================================

# Approximate 2D positions (x, y) for front-view rendering.
# Y-axis goes upward.  Coordinates in arbitrary SVG-friendly units (0-230).
# Based on humanoid anatomy and CP2077 bone naming from the modding docs.
#
# Format: bone_name -> (x, y, parent_name_or_None)

CP2077_SKELETON: Dict[str, Tuple[float, float, Optional[str]]] = {
    # Spine chain (midline)
    "Hips":         (0.0,  100.0, None),
    "Spine":        (0.0,  115.0, "Hips"),
    "Spine1":       (0.0,  130.0, "Spine"),
    "Spine2":       (0.0,  145.0, "Spine1"),
    "Spine3":       (0.0,  160.0, "Spine2"),
    "Chest":        (0.0,  175.0, "Spine3"),
    "Neck":         (0.0,  192.0, "Chest"),
    "Head":         (0.0,  215.0, "Neck"),
    # Left arm chain
    "Shoulder_l":   (-25.0, 182.0, "Chest"),
    "UpperArm_l":   (-45.0, 172.0, "Shoulder_l"),
    "ForeArm_l":    (-55.0, 142.0, "UpperArm_l"),
    "Hand_l":       (-60.0, 117.0, "ForeArm_l"),
    # Right arm chain
    "Shoulder_r":   (25.0,  182.0, "Chest"),
    "UpperArm_r":   (45.0,  172.0, "Shoulder_r"),
    "ForeArm_r":    (55.0,  142.0, "UpperArm_r"),
    "Hand_r":       (60.0,  117.0, "ForeArm_r"),
    # Left leg chain
    "Thigh_l":      (-15.0, 92.0,  "Hips"),
    "Calf_l":       (-17.0, 52.0,  "Thigh_l"),
    "Foot_l":       (-18.0, 10.0,  "Calf_l"),
    # Right leg chain
    "Thigh_r":      (15.0,  92.0,  "Hips"),
    "Calf_r":       (17.0,  52.0,  "Thigh_r"),
    "Foot_r":       (18.0,  10.0,  "Calf_r"),
}


# =============================================================================
#  SVG Generation  (Feature 2)
# =============================================================================

_COLOR_IDENTITY = "#4CAF50"   # green
_COLOR_MODIFIED = "#FF9800"   # orange
_COLOR_BEFORE   = "#9E9E9E"   # grey
_COLOR_CHANGED  = "#F44336"   # red
_BASE_RADIUS    = 5.0


def _get_bone_scale(rig, bone_name: str) -> Tuple[float, float, float]:
    """Retrieve (sx, sy, sz) from a rig, defaulting to identity."""
    if rig is None:
        return (1.0, 1.0, 1.0)
    bone = rig.GetBoneScale(bone_name)
    if bone is None:
        return (1.0, 1.0, 1.0)
    return (bone.scaleX, bone.scaleY, bone.scaleZ)


def _is_modified(sx, sy, sz) -> bool:
    return (abs(sx - 1.0) > 1e-6 or abs(sy - 1.0) > 1e-6
            or abs(sz - 1.0) > 1e-6)


def _svg_coord(x: float, y: float, width: int, height: int,
               margin: float = 30.0) -> Tuple[float, float]:
    """Convert skeleton coords (Y-up) to SVG coords (Y-down)."""
    svg_x = x + width / 2.0
    svg_y = height - y - margin
    return (svg_x, svg_y)


def _resolve_rig(rig, entity):
    """Extract a rig from either the rig arg or the entity."""
    if rig is not None:
        return rig
    if entity is not None:
        if hasattr(entity, 'GetDeformationRig'):
            return entity.GetDeformationRig()
        if hasattr(entity, '_deformation_rig'):
            return entity._deformation_rig
    return None


def generate_skeleton_svg(
    rig=None,
    entity=None,
    title: str = "CP2077 Skeleton",
    width: int = 400,
    height: int = 500,
) -> str:
    """
    Generate an SVG string showing a 2D wireframe skeleton.

    Args:
        rig: A DeformationRig to visualize.  If None, uses entity's rig.
        entity: A PlayerPuppet or entity.  Ignored if rig is provided.
        title: Title text rendered at the top of the SVG.
        width: SVG viewport width in pixels.
        height: SVG viewport height in pixels.

    Returns:
        A complete SVG document as a string.

    Bone visualization:
        - Circle per bone; radius = BASE_RADIUS * avg(scaleX, scaleY, scaleZ)
        - Lines connecting parent -> child
        - Green (#4CAF50) for identity bones, orange (#FF9800) for modified
        - Scale labels shown next to modified bones
    """
    rig = _resolve_rig(rig, entity)
    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{width}" height="{height}" '
                 f'viewBox="0 0 {width} {height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')

    # Title
    if title:
        lines.append(f'<text x="{width / 2}" y="20" '
                     f'text-anchor="middle" fill="white" '
                     f'font-family="monospace" font-size="14">{title}</text>')

    # Draw connecting lines first (behind circles)
    for bone_name, (bx, by, parent) in CP2077_SKELETON.items():
        if parent and parent in CP2077_SKELETON:
            px, py, _ = CP2077_SKELETON[parent]
            x1, y1 = _svg_coord(px, py, width, height)
            x2, y2 = _svg_coord(bx, by, width, height)
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
                         f'x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="#555555" stroke-width="2"/>')

    # Draw bone circles and labels
    for bone_name, (bx, by, parent) in CP2077_SKELETON.items():
        sx, sy, sz = _get_bone_scale(rig, bone_name)
        modified = _is_modified(sx, sy, sz)
        avg_scale = (sx + sy + sz) / 3.0
        radius = _BASE_RADIUS * avg_scale
        color = _COLOR_MODIFIED if modified else _COLOR_IDENTITY
        cx, cy = _svg_coord(bx, by, width, height)

        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
                     f'fill="{color}" stroke="white" stroke-width="1" '
                     f'opacity="0.9"/>')

        # Label for modified bones -- place _l labels left, _r labels right
        if modified:
            label = f"{sx:.2f}, {sy:.2f}, {sz:.2f}"
            if bone_name.endswith("_l"):
                # Left-side bone: label to the left, right-aligned
                lx = cx - radius - 4
                anchor = "end"
            else:
                # Right-side or midline bone: label to the right
                lx = cx + radius + 4
                anchor = "start"
            lines.append(f'<text x="{lx:.1f}" y="{cy + 3:.1f}" '
                         f'text-anchor="{anchor}" '
                         f'fill="{_COLOR_MODIFIED}" '
                         f'font-family="monospace" font-size="9">'
                         f'{bone_name}: {label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def generate_skeleton_svg_comparison(
    rig_before=None,
    rig_after=None,
    title: str = "Before / After",
    width: int = 400,
    height: int = 500,
) -> str:
    """
    Generate an SVG overlay comparing two rig states.

    The 'before' state is drawn in grey with dashed lines.
    The 'after' state is drawn in green/orange (identity/modified).
    Bones that changed between states get a red highlight ring.

    Args:
        rig_before: The baseline rig (None = all identity).
        rig_after: The modified rig (None = all identity).
        title: Title text.

    Returns:
        A complete SVG document string.
    """
    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{width}" height="{height}" '
                 f'viewBox="0 0 {width} {height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')

    if title:
        lines.append(f'<text x="{width / 2}" y="20" '
                     f'text-anchor="middle" fill="white" '
                     f'font-family="monospace" font-size="14">{title}</text>')

    # --- Pass 1: "before" skeleton (grey, dashed) ---
    for bone_name, (bx, by, parent) in CP2077_SKELETON.items():
        if parent and parent in CP2077_SKELETON:
            px, py, _ = CP2077_SKELETON[parent]
            x1, y1 = _svg_coord(px, py, width, height)
            x2, y2 = _svg_coord(bx, by, width, height)
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
                         f'x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="{_COLOR_BEFORE}" stroke-width="1" '
                         f'stroke-dasharray="4,3"/>')

    for bone_name, (bx, by, parent) in CP2077_SKELETON.items():
        sx, sy, sz = _get_bone_scale(rig_before, bone_name)
        avg_scale = (sx + sy + sz) / 3.0
        radius = _BASE_RADIUS * avg_scale
        cx, cy = _svg_coord(bx, by, width, height)
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
                     f'fill="none" stroke="{_COLOR_BEFORE}" '
                     f'stroke-width="1" stroke-dasharray="3,2"/>')

    # --- Pass 2: "after" skeleton (colored, solid) ---
    for bone_name, (bx, by, parent) in CP2077_SKELETON.items():
        if parent and parent in CP2077_SKELETON:
            px, py, _ = CP2077_SKELETON[parent]
            x1, y1 = _svg_coord(px, py, width, height)
            x2, y2 = _svg_coord(bx, by, width, height)
            lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
                         f'x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="#555555" stroke-width="2"/>')

    for bone_name, (bx, by, parent) in CP2077_SKELETON.items():
        sx_a, sy_a, sz_a = _get_bone_scale(rig_after, bone_name)
        sx_b, sy_b, sz_b = _get_bone_scale(rig_before, bone_name)
        modified = _is_modified(sx_a, sy_a, sz_a)
        changed = (abs(sx_a - sx_b) > 1e-6 or abs(sy_a - sy_b) > 1e-6
                   or abs(sz_a - sz_b) > 1e-6)

        avg_scale = (sx_a + sy_a + sz_a) / 3.0
        radius = _BASE_RADIUS * avg_scale
        color = _COLOR_MODIFIED if modified else _COLOR_IDENTITY
        cx, cy = _svg_coord(bx, by, width, height)

        # Red highlight ring for changed bones
        if changed:
            lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" '
                         f'r="{radius + 3:.1f}" '
                         f'fill="none" stroke="{_COLOR_CHANGED}" '
                         f'stroke-width="2" opacity="0.8"/>')

        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
                     f'fill="{color}" stroke="white" stroke-width="1" '
                     f'opacity="0.9"/>')

        if modified:
            label = f"{sx_a:.2f}, {sy_a:.2f}, {sz_a:.2f}"
            if bone_name.endswith("_l"):
                lx = cx - radius - 4
                anchor = "end"
            else:
                lx = cx + radius + 4
                anchor = "start"
            lines.append(f'<text x="{lx:.1f}" y="{cy + 3:.1f}" '
                         f'text-anchor="{anchor}" '
                         f'fill="{_COLOR_MODIFIED}" '
                         f'font-family="monospace" font-size="9">'
                         f'{bone_name}: {label}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def render_skeleton_png(
    rig=None,
    entity=None,
    title: str = "CP2077 Skeleton",
    output_path: str = "/tmp/skeleton.png",
    width: int = 400,
    height: int = 500,
) -> str:
    """
    Generate a skeleton SVG, render it to PNG via rsvg-convert, and
    return the PNG path.  Requires librsvg2-bin (apt install librsvg2-bin).

    The returned path can be passed directly to the Read tool for viewing.
    """
    import subprocess
    import tempfile

    svg = generate_skeleton_svg(rig=rig, entity=entity, title=title,
                                width=width, height=height)
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w') as f:
        f.write(svg)
        svg_path = f.name
    try:
        subprocess.run(['rsvg-convert', svg_path, '-o', output_path],
                       check=True, capture_output=True)
    finally:
        os.unlink(svg_path)
    return os.path.abspath(output_path)


def render_comparison_png(
    rig_before=None,
    rig_after=None,
    title: str = "Before / After",
    output_path: str = "/tmp/skeleton_compare.png",
    width: int = 400,
    height: int = 500,
) -> str:
    """
    Generate a before/after comparison SVG, render to PNG, return path.
    Requires librsvg2-bin.
    """
    import subprocess
    import tempfile

    svg = generate_skeleton_svg_comparison(rig_before=rig_before,
                                           rig_after=rig_after, title=title,
                                           width=width, height=height)
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w') as f:
        f.write(svg)
        svg_path = f.name
    try:
        subprocess.run(['rsvg-convert', svg_path, '-o', output_path],
                       check=True, capture_output=True)
    finally:
        os.unlink(svg_path)
    return os.path.abspath(output_path)


def write_svg(svg_string: str, filepath: str) -> str:
    """Write an SVG string to a file.  Returns the absolute filepath."""
    with open(filepath, 'w') as f:
        f.write(svg_string)
    return os.path.abspath(filepath)


# =============================================================================
#  glTF 2.0 Export  (Feature 3)
# =============================================================================

def _build_cube_buffer() -> Tuple[bytes, Dict[str, Any]]:
    """
    Build a minimal unit cube as glTF binary buffer data.

    Returns:
        (buffer_bytes, info_dict) where info_dict contains byte offsets,
        lengths, and counts for indices and vertices.
    """
    # 8 vertices of a 0.5-unit cube centred at origin
    vertices = [
        (-0.5, -0.5, -0.5), ( 0.5, -0.5, -0.5),
        ( 0.5,  0.5, -0.5), (-0.5,  0.5, -0.5),
        (-0.5, -0.5,  0.5), ( 0.5, -0.5,  0.5),
        ( 0.5,  0.5,  0.5), (-0.5,  0.5,  0.5),
    ]
    # 12 triangles (36 indices)
    indices = [
        0, 1, 2,  0, 2, 3,   # front
        4, 6, 5,  4, 7, 6,   # back
        0, 4, 5,  0, 5, 1,   # bottom
        2, 6, 7,  2, 7, 3,   # top
        0, 3, 7,  0, 7, 4,   # left
        1, 5, 6,  1, 6, 2,   # right
    ]

    idx_data = b''.join(struct.pack('<H', i) for i in indices)
    # Pad to 4-byte alignment (glTF requirement)
    while len(idx_data) % 4 != 0:
        idx_data += b'\x00'

    vert_data = b''.join(struct.pack('<fff', *v) for v in vertices)
    buffer_bytes = idx_data + vert_data

    return buffer_bytes, {
        "idx_offset": 0,
        "idx_length": len(indices) * 2,
        "idx_count": len(indices),
        "vert_offset": len(idx_data),
        "vert_length": len(vert_data),
        "vert_count": len(vertices),
    }


def _build_node_hierarchy(
    rig, include_mesh: bool, mesh_index: int = 0
) -> Tuple[List[Dict], List[int]]:
    """
    Build glTF nodes from CP2077_SKELETON + rig bone scales.

    Returns:
        (nodes_list, root_node_indices)
    """
    bone_names = list(CP2077_SKELETON.keys())
    name_to_idx = {name: i for i, name in enumerate(bone_names)}

    nodes: List[Dict[str, Any]] = []
    root_indices: List[int] = []

    for name in bone_names:
        bx, by, parent = CP2077_SKELETON[name]
        node: Dict[str, Any] = {"name": name}

        # Translation relative to parent (convert to ~metres: /100)
        if parent and parent in CP2077_SKELETON:
            px, py, _ = CP2077_SKELETON[parent]
            node["translation"] = [
                (bx - px) / 100.0,
                (by - py) / 100.0,
                0.0,
            ]
        else:
            node["translation"] = [bx / 100.0, by / 100.0, 0.0]
            root_indices.append(name_to_idx[name])

        # Scale from rig
        if rig is not None:
            bone = rig.GetBoneScale(name)
            if bone is not None and not bone.is_identity():
                node["scale"] = [bone.scaleX, bone.scaleY, bone.scaleZ]

        # Children
        children = [name_to_idx[n] for n in bone_names
                    if CP2077_SKELETON[n][2] == name]
        if children:
            node["children"] = children

        # Mesh reference
        if include_mesh:
            node["mesh"] = mesh_index

        nodes.append(node)

    return nodes, root_indices


def export_gltf_json(
    rig=None,
    entity=None,
    output_path: Optional[str] = None,
    include_mesh: bool = True,
) -> str:
    """
    Export the skeleton + bone scales as a glTF 2.0 JSON file.

    Args:
        rig: A DeformationRig to export.  If None, uses entity's rig.
        entity: Entity to extract rig from (used if rig is None).
        output_path: If provided, write JSON to this file path.
        include_mesh: If True, include a cube mesh primitive per bone.

    Returns:
        The glTF JSON string.

    The output conforms to glTF 2.0 and can be loaded in:
      - https://gltf-viewer.donmccurdy.com
      - three.js editor
      - Blender (File > Import > glTF)
    """
    rig = _resolve_rig(rig, entity)
    nodes, root_indices = _build_node_hierarchy(
        rig, include_mesh=include_mesh, mesh_index=0)

    gltf: Dict[str, Any] = {
        "asset": {
            "version": "2.0",
            "generator": "CP2077-Engine-Sim",
        },
        "scene": 0,
        "scenes": [{"name": "Skeleton", "nodes": root_indices}],
        "nodes": nodes,
    }

    if include_mesh:
        buf_bytes, info = _build_cube_buffer()
        data_uri = ("data:application/octet-stream;base64,"
                    + base64.b64encode(buf_bytes).decode('ascii'))

        gltf["buffers"] = [{
            "uri": data_uri,
            "byteLength": len(buf_bytes),
        }]

        gltf["bufferViews"] = [
            {   # indices
                "buffer": 0,
                "byteOffset": info["idx_offset"],
                "byteLength": info["idx_length"],
                "target": 34963,  # ELEMENT_ARRAY_BUFFER
            },
            {   # vertices
                "buffer": 0,
                "byteOffset": info["vert_offset"],
                "byteLength": info["vert_length"],
                "target": 34962,  # ARRAY_BUFFER
            },
        ]

        gltf["accessors"] = [
            {   # indices
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": info["idx_count"],
                "type": "SCALAR",
                "max": [7],
                "min": [0],
            },
            {   # positions
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": info["vert_count"],
                "type": "VEC3",
                "max": [0.5, 0.5, 0.5],
                "min": [-0.5, -0.5, -0.5],
            },
        ]

        gltf["meshes"] = [{
            "name": "BoneCube",
            "primitives": [{
                "attributes": {"POSITION": 1},
                "indices": 0,
            }],
        }]

    result = json.dumps(gltf, indent=2)

    if output_path is not None:
        with open(output_path, 'w') as f:
            f.write(result)

    return result
