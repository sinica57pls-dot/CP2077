#include "VisualScaleEx.hpp"
#include "Red/Mesh.hpp"

// ---------------------------------------------------------------------------
//  VisualScale native methods for mesh components
// ---------------------------------------------------------------------------
//
//  The CP2077 engine has a native `visualScale` (Vector3) field on all mesh
//  component types.  Codeware already exposes it on MeshComponent via
//  @addField, but NOT on the skinned mesh types (entSkinnedMeshComponent,
//  entMorphTargetSkinnedMeshComponent).
//
//  This file adds native Get/SetVisualScale methods to all three families.
//  SetVisualScale calls RefreshAppearance() after writing, which forces the
//  renderer to re-read the visual properties — guaranteeing the scale change
//  is visible in-game.
//
//  The field is resolved at runtime via RTTI property lookup
//  (Red::GetPropertyPtr), which safely handles both the case where the field
//  exists natively at the C++ level AND the case where it was injected by
//  @addField in Redscript.
// ---------------------------------------------------------------------------

// === MeshComponent ===

Red::Vector3 App::MeshComponentScaleEx::GetVisualScale()
{
    auto* ptr = Red::GetPropertyPtr<Red::Vector3>(this, "visualScale");
    if (ptr)
        return *ptr;

    return {1.0f, 1.0f, 1.0f};
}

void App::MeshComponentScaleEx::SetVisualScale(Red::Vector3 aScale)
{
    auto* ptr = Red::GetPropertyPtr<Red::Vector3>(this, "visualScale");
    if (ptr)
    {
        *ptr = aScale;
        Raw::MeshComponent::RefreshAppearance(this);
    }
}

// === SkinnedMeshComponent ===

Red::Vector3 App::SkinnedMeshComponentScaleEx::GetVisualScale()
{
    auto* ptr = Red::GetPropertyPtr<Red::Vector3>(this, "visualScale");
    if (ptr)
        return *ptr;

    return {1.0f, 1.0f, 1.0f};
}

void App::SkinnedMeshComponentScaleEx::SetVisualScale(Red::Vector3 aScale)
{
    auto* ptr = Red::GetPropertyPtr<Red::Vector3>(this, "visualScale");
    if (ptr)
    {
        *ptr = aScale;
        Raw::MeshComponent::RefreshAppearance(this);
    }
}

// === MorphTargetSkinnedMeshComponent ===

Red::Vector3 App::MorphTargetSkinnedMeshComponentScaleEx::GetVisualScale()
{
    auto* ptr = Red::GetPropertyPtr<Red::Vector3>(this, "visualScale");
    if (ptr)
        return *ptr;

    return {1.0f, 1.0f, 1.0f};
}

void App::MorphTargetSkinnedMeshComponentScaleEx::SetVisualScale(Red::Vector3 aScale)
{
    auto* ptr = Red::GetPropertyPtr<Red::Vector3>(this, "visualScale");
    if (ptr)
    {
        *ptr = aScale;
        Raw::MeshComponent::RefreshAppearance(this);
    }
}
