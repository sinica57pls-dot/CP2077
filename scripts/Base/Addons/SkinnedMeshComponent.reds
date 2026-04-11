// ---------------------------------------------------------------------------
//  Expose visualScale and native scale methods on skinned mesh components
// ---------------------------------------------------------------------------
//
//  The CP2077 engine has visualScale (Vector3) at the C++ level on skinned
//  mesh components, but Codeware only exposes it on MeshComponent.
//  These declarations expose it on the skinned mesh component families, and
//  add SetVisualScale() methods that trigger RefreshAppearance() -- forcing
//  the renderer to pick up the new scale immediately.
//
//  Companion C++ implementation: src/App/Entity/VisualScaleEx.hpp/cpp
// ---------------------------------------------------------------------------

// === entSkinnedMeshComponent (body, head, limbs, clothing) ===

@addField(entSkinnedMeshComponent)
public native let visualScale: Vector3;

@addMethod(entSkinnedMeshComponent)
public native func GetVisualScale() -> Vector3

@addMethod(entSkinnedMeshComponent)
public native func SetVisualScale(scale: Vector3) -> Void

// === entMorphTargetSkinnedMeshComponent (body morphs) ===

@addField(entMorphTargetSkinnedMeshComponent)
public native let visualScale: Vector3;

@addMethod(entMorphTargetSkinnedMeshComponent)
public native func GetVisualScale() -> Vector3

@addMethod(entMorphTargetSkinnedMeshComponent)
public native func SetVisualScale(scale: Vector3) -> Void

// === MeshComponent (static/prop meshes -- methods only, field already in MeshComponent.reds) ===

@addMethod(MeshComponent)
public native func GetVisualScale() -> Vector3

@addMethod(MeshComponent)
public native func SetVisualScale(scale: Vector3) -> Void
