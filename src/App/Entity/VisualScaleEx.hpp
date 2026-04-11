#pragma once

#include "Red/Mesh.hpp"

namespace App
{
struct MeshComponentScaleEx : Red::ent::MeshComponent
{
    Red::Vector3 GetVisualScale();
    void SetVisualScale(Red::Vector3 aScale);
};

struct SkinnedMeshComponentScaleEx : Red::ent::SkinnedMeshComponent
{
    Red::Vector3 GetVisualScale();
    void SetVisualScale(Red::Vector3 aScale);
};

struct MorphTargetSkinnedMeshComponentScaleEx : Red::ent::MorphTargetSkinnedMeshComponent
{
    Red::Vector3 GetVisualScale();
    void SetVisualScale(Red::Vector3 aScale);
};
}

RTTI_EXPAND_CLASS(Red::ent::MeshComponent, App::MeshComponentScaleEx, {
    RTTI_METHOD(GetVisualScale);
    RTTI_METHOD(SetVisualScale);
});

RTTI_EXPAND_CLASS(Red::ent::SkinnedMeshComponent, App::SkinnedMeshComponentScaleEx, {
    RTTI_METHOD(GetVisualScale);
    RTTI_METHOD(SetVisualScale);
});

RTTI_EXPAND_CLASS(Red::ent::MorphTargetSkinnedMeshComponent, App::MorphTargetSkinnedMeshComponentScaleEx, {
    RTTI_METHOD(GetVisualScale);
    RTTI_METHOD(SetVisualScale);
});
