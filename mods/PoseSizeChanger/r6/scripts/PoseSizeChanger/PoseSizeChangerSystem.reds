module PoseSizeChanger

// ---------------------------------------------------------------------------
//  Pose Size Changer System  v1.0.1
// ---------------------------------------------------------------------------
//
//  AMM-style "aim and apply" entity scaler for Photo Mode and gameplay.
//
//  1. Look at a character (player V, AMM-spawned NPC, photo mode puppet)
//  2. Press F9 (or use the CET overlay) to scale them up
//  3. The scale persists through pose changes
//  4. Press F10 to reset that character back to normal
//
//  v1.0.1 fixes:
//    - Replaced FTLog with ModLog (guaranteed native)
//    - Added entMorphTargetSkinnedMeshComponent + entGarmentSkinnedMeshComponent
//    - Fixed stale entity cleanup in tick loop
//    - Fixed early-break in duplicate entity check
//    - Removed silent player fallback from crosshair targeting
//    - Added dedicated ApplyScaleToPlayer API
//    - Cached tag array (built once, not per-call)
//    - Hoisted Vector3 allocation out of tick loop
//    - Added lightweight UpdateTarget / GetLastTargetName for CET overlay
//
// ---------------------------------------------------------------------------

// ============================
//  Scaled entity tracking
// ============================

public class ScaledEntityEntry extends IScriptable {
    public let entityID: EntityID;
    public let scaleFactor: Float;
    public let displayName: String;
}

// ============================
//  Tick callback
// ============================

public class PoseSizeChangerTick extends DelayCallback {
    public let system: wref<PoseSizeChangerSystem>;

    public func Call() -> Void {
        if IsDefined(this.system) {
            this.system.OnTick();
        }
    }
}

// ============================
//  Main system
// ============================

public class PoseSizeChangerSystem extends ScriptableSystem {

    // Cached references
    private let m_player: wref<GameObject>;
    private let m_entitySystem: wref<DynamicEntitySystem>;

    // State
    private let m_active: Bool;
    private let m_ticking: Bool;

    // The list of entities we are actively scaling
    private let m_scaledEntities: array<ref<ScaledEntityEntry>>;

    // Cached tag list for entity lookups (built once in Initialize)
    private let m_lookupTags: array<CName>;

    // Last targeted entity info (lightweight cache for CET overlay)
    private let m_lastTargetName: String;

    // ------------------------------------------------------------------
    //  Lifecycle
    // ------------------------------------------------------------------

    private func OnAttach() -> Void {
        this.m_active = false;
        this.m_ticking = false;
        this.m_lastTargetName = "None";

        // Register hotkeys
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Input/Key", this, n"OnKeyInput")
            .AddTarget(InputTarget.Key(PoseSizeChangerConfig.ApplyKey(), EInputAction.IACT_Press));

        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Input/Key", this, n"OnResetKeyInput")
            .AddTarget(InputTarget.Key(PoseSizeChangerConfig.ResetKey(), EInputAction.IACT_Press));

        // Session end cleanup
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Session/BeforeEnd", this, n"OnSessionEnd");
    }

    private func OnRestored(saveVersion: Int32, gameVersion: Int32) -> Void {
        this.Initialize();
    }

    private func OnPlayerAttach(request: ref<PlayerAttachRequest>) -> Void {
        this.Initialize();
    }

    private func Initialize() -> Void {
        if this.m_active { return; }

        this.m_player = GetPlayer(this.GetGameInstance());
        if !IsDefined(this.m_player) { return; }
        if GameInstance.GetSystemRequestsHandler().IsPreGame() { return; }

        this.m_entitySystem = GameInstance.GetDynamicEntitySystem();

        // Build tag lookup array once
        ArrayClear(this.m_lookupTags);
        ArrayPush(this.m_lookupTags, n"AMM");
        ArrayPush(this.m_lookupTags, n"amm");
        ArrayPush(this.m_lookupTags, n"Companion");
        ArrayPush(this.m_lookupTags, n"companion");
        ArrayPush(this.m_lookupTags, n"PhotoMode");
        ArrayPush(this.m_lookupTags, n"photomode");

        this.m_active = true;

        ModLog(n"PoseSizeChanger", "System ready. F9 = scale target, F10 = reset target.");
    }

    // ------------------------------------------------------------------
    //  Session end
    // ------------------------------------------------------------------

    private cb func OnSessionEnd(evt: ref<GameSessionEvent>) -> Void {
        this.ResetAll();
        this.m_active = false;
        this.m_ticking = false;
        this.m_lastTargetName = "None";
    }

    // ------------------------------------------------------------------
    //  Hotkey: F9 = apply scale to look-at target
    // ------------------------------------------------------------------

    private cb func OnKeyInput(evt: ref<KeyInputEvent>) -> Void {
        if !this.m_active { return; }

        let target: ref<Entity> = this.FindLookAtEntity();
        if IsDefined(target) {
            this.ApplyScaleToEntity(target, PoseSizeChangerConfig.DefaultScale());
            this.m_lastTargetName = this.GetEntityDisplayName(target);
            ModLog(n"PoseSizeChanger", "Scaled target entity.");
        } else {
            ModLog(n"PoseSizeChanger", "No valid target in crosshair.");
        }
    }

    // ------------------------------------------------------------------
    //  Hotkey: F10 = reset look-at target
    // ------------------------------------------------------------------

    private cb func OnResetKeyInput(evt: ref<KeyInputEvent>) -> Void {
        if !this.m_active { return; }

        let target: ref<Entity> = this.FindLookAtEntity();
        if IsDefined(target) {
            this.ResetEntity(target.GetEntityID());
            ModLog(n"PoseSizeChanger", "Reset entity to default scale.");
        } else {
            ModLog(n"PoseSizeChanger", "No valid target in crosshair.");
        }
    }

    // ------------------------------------------------------------------
    //  Tick: periodically reapply scales + cleanup stale entries
    // ------------------------------------------------------------------

    public func ScheduleTick() -> Void {
        if this.m_ticking { return; }
        if ArraySize(this.m_scaledEntities) == 0 { return; }

        this.m_ticking = true;

        let cb = new PoseSizeChangerTick();
        cb.system = this;
        GameInstance.GetDelaySystem(this.GetGameInstance())
            .DelayCallback(cb, PoseSizeChangerConfig.TickInterval(), false);
    }

    public func OnTick() -> Void {
        this.m_ticking = false;

        if !this.m_active { return; }
        if ArraySize(this.m_scaledEntities) == 0 { return; }

        // Reapply scales; remove stale (despawned) entries in reverse order
        let i: Int32 = ArraySize(this.m_scaledEntities) - 1;
        while i >= 0 {
            let entry: ref<ScaledEntityEntry> = this.m_scaledEntities[i];
            let entity: ref<Entity> = this.ResolveEntity(entry.entityID);
            if IsDefined(entity) {
                let scaleVec: Vector3 = new Vector3(entry.scaleFactor, entry.scaleFactor, entry.scaleFactor);
                this.ScaleMeshComponents(entity, scaleVec);
            } else {
                // Entity despawned or no longer valid -- remove stale entry
                ArrayErase(this.m_scaledEntities, i);
            }
            i -= 1;
        }

        // Keep ticking while there are scaled entities
        this.ScheduleTick();
    }

    // ------------------------------------------------------------------
    //  Entity targeting (AMM-style look-at)
    // ------------------------------------------------------------------

    public func FindLookAtEntity() -> ref<Entity> {
        if !IsDefined(this.m_player) {
            this.m_player = GetPlayer(this.GetGameInstance());
        }
        if !IsDefined(this.m_player) { return null; }

        let playerPos: Vector4 = this.m_player.GetWorldPosition();
        let playerFwd: Vector4 = this.m_player.GetWorldForward();

        let maxDist: Float = PoseSizeChangerConfig.MaxTargetDistance();
        let minDot: Float = PoseSizeChangerConfig.MinDotProduct();

        let bestEntity: ref<Entity>;
        let bestDot: Float = -1.0;

        // --- 1) Check photo mode puppet ---
        let playerSystem: ref<PlayerSystem> = GameInstance.GetPlayerSystem(this.GetGameInstance());
        let photoPuppet: wref<gamePuppet> = playerSystem.GetPhotoPuppet();
        if IsDefined(photoPuppet) {
            let puppetEntity: ref<Entity> = photoPuppet as Entity;
            if IsDefined(puppetEntity) {
                let dot: Float = this.EvaluateTarget(puppetEntity, playerPos, playerFwd, maxDist, minDot);
                if dot > bestDot {
                    bestDot = dot;
                    bestEntity = puppetEntity;
                }
            }
        }

        // --- 2) Check DynamicEntitySystem tags (cached array) ---
        if IsDefined(this.m_entitySystem) {
            let tagIndex: Int32 = 0;
            while tagIndex < ArraySize(this.m_lookupTags) {
                let tag: CName = this.m_lookupTags[tagIndex];
                if this.m_entitySystem.IsPopulated(tag) {
                    let entities: array<ref<Entity>> = this.m_entitySystem.GetTagged(tag);
                    let entI: Int32 = 0;
                    while entI < ArraySize(entities) {
                        let entity: ref<Entity> = entities[entI];
                        if IsDefined(entity) && !this.IsPlayer(entity) {
                            let dot: Float = this.EvaluateTarget(entity, playerPos, playerFwd, maxDist, minDot);
                            if dot > bestDot {
                                bestDot = dot;
                                bestEntity = entity;
                            }
                        }
                        entI += 1;
                    }
                }
                tagIndex += 1;
            }
        }

        // Update cached target name for CET overlay (lightweight)
        if IsDefined(bestEntity) {
            this.m_lastTargetName = this.GetEntityDisplayName(bestEntity);
        } else {
            this.m_lastTargetName = "None";
        }

        // NO silent fallback to player -- return null if nothing in crosshair
        return bestEntity;
    }

    private func EvaluateTarget(entity: ref<Entity>, playerPos: Vector4, playerFwd: Vector4, maxDist: Float, minDot: Float) -> Float {
        let entityPos: Vector4 = entity.GetWorldPosition();

        let dx: Float = entityPos.X - playerPos.X;
        let dy: Float = entityPos.Y - playerPos.Y;
        let dz: Float = entityPos.Z - playerPos.Z;

        let dist: Float = SqrtF(dx * dx + dy * dy + dz * dz);

        if dist < 0.3 || dist > maxDist {
            return -1.0;
        }

        let invDist: Float = 1.0 / dist;
        dx *= invDist;
        dy *= invDist;
        dz *= invDist;

        let dot: Float = dx * playerFwd.X + dy * playerFwd.Y + dz * playerFwd.Z;

        if dot < minDot {
            return -1.0;
        }

        return dot;
    }

    private func IsPlayer(entity: ref<Entity>) -> Bool {
        return entity.IsA(n"PlayerPuppet") || entity.IsA(n"gamePlayerPuppet");
    }

    // ------------------------------------------------------------------
    //  Scale management
    // ------------------------------------------------------------------

    public func ApplyScaleToEntity(entity: ref<Entity>, factor: Float) -> Void {
        if !IsDefined(entity) { return; }

        let entityID: EntityID = entity.GetEntityID();
        let targetHash: Uint64 = EntityID.ToHash(entityID);

        // Update existing entry or create new one
        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            if Equals(EntityID.ToHash(this.m_scaledEntities[i].entityID), targetHash) {
                this.m_scaledEntities[i].scaleFactor = factor;
                // Apply immediately and return (early break)
                let scaleVec: Vector3 = new Vector3(factor, factor, factor);
                this.ScaleMeshComponents(entity, scaleVec);
                this.ScheduleTick();
                return;
            }
            i += 1;
        }

        // New entry
        let entry: ref<ScaledEntityEntry> = new ScaledEntityEntry();
        entry.entityID = entityID;
        entry.scaleFactor = factor;
        entry.displayName = this.GetEntityDisplayName(entity);
        ArrayPush(this.m_scaledEntities, entry);

        // Apply immediately
        let scaleVec: Vector3 = new Vector3(factor, factor, factor);
        this.ScaleMeshComponents(entity, scaleVec);

        // Start ticking to maintain scale
        this.ScheduleTick();
    }

    public func ApplyScaleToLookAt(factor: Float) -> Bool {
        let target: ref<Entity> = this.FindLookAtEntity();
        if IsDefined(target) {
            this.ApplyScaleToEntity(target, factor);
            return true;
        }
        return false;
    }

    public func ApplyScaleToPlayer(factor: Float) -> Bool {
        if !IsDefined(this.m_player) {
            this.m_player = GetPlayer(this.GetGameInstance());
        }
        if !IsDefined(this.m_player) { return false; }

        this.ApplyScaleToEntity(this.m_player as Entity, factor);
        return true;
    }

    public func ResetEntity(entityID: EntityID) -> Void {
        let defaultScale: Vector3 = new Vector3(1.0, 1.0, 1.0);
        let targetHash: Uint64 = EntityID.ToHash(entityID);

        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            if Equals(EntityID.ToHash(this.m_scaledEntities[i].entityID), targetHash) {
                let entity: ref<Entity> = this.ResolveEntity(entityID);
                if IsDefined(entity) {
                    this.ScaleMeshComponents(entity, defaultScale);
                }
                ArrayErase(this.m_scaledEntities, i);
                return;
            }
            i += 1;
        }
    }

    public func ResetLookAt() -> Bool {
        let target: ref<Entity> = this.FindLookAtEntity();
        if IsDefined(target) {
            this.ResetEntity(target.GetEntityID());
            return true;
        }
        return false;
    }

    public func ResetPlayer() -> Void {
        if !IsDefined(this.m_player) { return; }
        this.ResetEntity(this.m_player.GetEntityID());
    }

    public func ResetAll() -> Void {
        let defaultScale: Vector3 = new Vector3(1.0, 1.0, 1.0);

        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            let entity: ref<Entity> = this.ResolveEntity(this.m_scaledEntities[i].entityID);
            if IsDefined(entity) {
                this.ScaleMeshComponents(entity, defaultScale);
            }
            i += 1;
        }

        ArrayClear(this.m_scaledEntities);
    }

    // ------------------------------------------------------------------
    //  Mesh component scaling
    // ------------------------------------------------------------------
    //  Scales ALL mesh-type components on the entity:
    //    - entMeshComponent           (static meshes)
    //    - entSkinnedMeshComponent    (skinned body/head)
    //    - entGarmentSkinnedMeshComponent  (clothing)
    //    - entMorphTargetSkinnedMeshComponent (body morph meshes)
    //  All inherit from MeshComponent, so the cast and visualScale access work.
    // ------------------------------------------------------------------

    private func ScaleMeshComponents(entity: ref<Entity>, scaleVec: Vector3) -> Void {
        if !IsDefined(entity) { return; }

        let components: array<ref<IComponent>> = entity.GetComponents();
        let i: Int32 = 0;

        while i < ArraySize(components) {
            let comp: ref<IComponent> = components[i];
            if IsDefined(comp) {
                if comp.IsA(n"entSkinnedMeshComponent")
                    || comp.IsA(n"entMeshComponent")
                    || comp.IsA(n"entMorphTargetSkinnedMeshComponent")
                    || comp.IsA(n"entGarmentSkinnedMeshComponent") {
                    let mesh: ref<MeshComponent> = comp as MeshComponent;
                    if IsDefined(mesh) {
                        mesh.visualScale = scaleVec;
                    }
                }
            }
            i += 1;
        }
    }

    // ------------------------------------------------------------------
    //  Entity resolution helpers
    // ------------------------------------------------------------------

    private func ResolveEntity(entityID: EntityID) -> ref<Entity> {
        let targetHash: Uint64 = EntityID.ToHash(entityID);

        // Try DynamicEntitySystem first
        if IsDefined(this.m_entitySystem) && this.m_entitySystem.IsManaged(entityID) {
            return this.m_entitySystem.GetEntity(entityID);
        }

        // Try photo puppet
        let playerSystem: ref<PlayerSystem> = GameInstance.GetPlayerSystem(this.GetGameInstance());
        let photoPuppet: wref<gamePuppet> = playerSystem.GetPhotoPuppet();
        if IsDefined(photoPuppet) {
            let puppetEntity: ref<Entity> = photoPuppet as Entity;
            if IsDefined(puppetEntity) && Equals(EntityID.ToHash(puppetEntity.GetEntityID()), targetHash) {
                return puppetEntity;
            }
        }

        // Fallback: player entity
        if IsDefined(this.m_player) && Equals(EntityID.ToHash(this.m_player.GetEntityID()), targetHash) {
            return this.m_player as Entity;
        }

        return null;
    }

    private func GetEntityDisplayName(entity: ref<Entity>) -> String {
        if entity.IsA(n"PlayerPuppet") || entity.IsA(n"gamePlayerPuppet") {
            return "Player V";
        }
        if entity.IsA(n"NPCPuppet") {
            return "NPC";
        }
        if entity.IsA(n"gamePuppet") {
            return "Puppet";
        }
        return "Entity";
    }

    // ------------------------------------------------------------------
    //  Public API  --  for CET overlay and other mods
    // ------------------------------------------------------------------

    public func IsActive() -> Bool {
        return this.m_active;
    }

    public func GetScaledCount() -> Int32 {
        return ArraySize(this.m_scaledEntities);
    }

    public func GetScaledEntityName(index: Int32) -> String {
        if index >= 0 && index < ArraySize(this.m_scaledEntities) {
            return this.m_scaledEntities[index].displayName;
        }
        return "";
    }

    public func GetScaledEntityFactor(index: Int32) -> Float {
        if index >= 0 && index < ArraySize(this.m_scaledEntities) {
            return this.m_scaledEntities[index].scaleFactor;
        }
        return 1.0;
    }

    // Lightweight getter -- returns cached name, NO computation
    public func GetLastTargetName() -> String {
        return this.m_lastTargetName;
    }

    // Explicit target refresh -- call this from a button press, NOT per-frame
    public func UpdateTarget() -> String {
        let target: ref<Entity> = this.FindLookAtEntity();
        // m_lastTargetName is updated inside FindLookAtEntity
        return this.m_lastTargetName;
    }

    public func GetScaleForEntity(entityID: EntityID) -> Float {
        let targetHash: Uint64 = EntityID.ToHash(entityID);
        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            if Equals(EntityID.ToHash(this.m_scaledEntities[i].entityID), targetHash) {
                return this.m_scaledEntities[i].scaleFactor;
            }
            i += 1;
        }
        return 1.0;
    }

    // ------------------------------------------------------------------
    //  Diagnostics  --  workability checker
    // ------------------------------------------------------------------
    //
    //  RunDiagnostics() checks every dependency and feature the mod
    //  needs to function, returning a human-readable results array.
    //  Call from CET overlay "Run Diagnostics" button.
    //
    // ------------------------------------------------------------------

    public func RunDiagnostics() -> array<String> {
        let results: array<String>;

        // --- 1. System status ---
        if this.m_active {
            ArrayPush(results, "PASS: System is active and attached");
        } else {
            ArrayPush(results, "FAIL: System is NOT active -- session may not be loaded");
        }

        // --- 2. Player reference ---
        let player: wref<GameObject> = GetPlayer(this.GetGameInstance());
        if IsDefined(player) {
            ArrayPush(results, "PASS: Player reference acquired");
        } else {
            ArrayPush(results, "FAIL: Cannot get player reference -- are you in a loaded game?");
        }

        // --- 3. PlayerSystem + PhotoPuppet ---
        let playerSystem: ref<PlayerSystem> = GameInstance.GetPlayerSystem(this.GetGameInstance());
        if IsDefined(playerSystem) {
            ArrayPush(results, "PASS: PlayerSystem available");

            let photoPuppet: wref<gamePuppet> = playerSystem.GetPhotoPuppet();
            if IsDefined(photoPuppet) {
                ArrayPush(results, "PASS: Photo Mode puppet present (photo mode active or was used)");
            } else {
                ArrayPush(results, "INFO: Photo Mode puppet is NULL (normal if photo mode was not opened yet)");
            }
        } else {
            ArrayPush(results, "FAIL: PlayerSystem unavailable -- Codeware may not be loaded");
        }

        // --- 4. DynamicEntitySystem ---
        let dynSys: ref<DynamicEntitySystem> = GameInstance.GetDynamicEntitySystem();
        if IsDefined(dynSys) {
            ArrayPush(results, "PASS: DynamicEntitySystem available");

            // Check common tags
            if dynSys.IsPopulated(n"AMM") || dynSys.IsPopulated(n"amm") {
                ArrayPush(results, "INFO: AMM entities detected -- AMM is installed");
            } else {
                ArrayPush(results, "INFO: No AMM entities found (normal if AMM NPCs not spawned)");
            }
        } else {
            ArrayPush(results, "FAIL: DynamicEntitySystem unavailable -- Codeware may not be loaded");
        }

        // --- 5. CallbackSystem ---
        let cbSys: ref<CallbackSystem> = GameInstance.GetCallbackSystem();
        if IsDefined(cbSys) {
            ArrayPush(results, "PASS: CallbackSystem available (Codeware working)");
        } else {
            ArrayPush(results, "FAIL: CallbackSystem unavailable -- Codeware is NOT loaded");
        }

        // --- 6. DelaySystem ---
        let delaySys: ref<DelaySystem> = GameInstance.GetDelaySystem(this.GetGameInstance());
        if IsDefined(delaySys) {
            ArrayPush(results, "PASS: DelaySystem available (tick scheduling works)");
        } else {
            ArrayPush(results, "FAIL: DelaySystem unavailable -- scale persistence will not work");
        }

        // --- 7. Mesh component access on player ---
        if IsDefined(player) {
            let entity: ref<Entity> = player as Entity;
            if IsDefined(entity) {
                let components: array<ref<IComponent>> = entity.GetComponents();
                let meshCount: Int32 = 0;
                let i: Int32 = 0;
                while i < ArraySize(components) {
                    let comp: ref<IComponent> = components[i];
                    if IsDefined(comp) {
                        if comp.IsA(n"entSkinnedMeshComponent")
                            || comp.IsA(n"entMeshComponent")
                            || comp.IsA(n"entMorphTargetSkinnedMeshComponent")
                            || comp.IsA(n"entGarmentSkinnedMeshComponent") {
                            meshCount += 1;
                        }
                    }
                    i += 1;
                }

                if meshCount > 0 {
                    ArrayPush(results, "PASS: Found mesh components on player (" + IntToString(meshCount) + " mesh components)");
                } else {
                    ArrayPush(results, "WARN: No mesh components found on player -- scaling may not work");
                }

                // Test visualScale access
                let testComp: ref<IComponent> = entity.FindComponentByType(n"entSkinnedMeshComponent");
                if IsDefined(testComp) {
                    let mesh: ref<MeshComponent> = testComp as MeshComponent;
                    if IsDefined(mesh) {
                        ArrayPush(results, "PASS: visualScale property accessible on MeshComponent");
                    } else {
                        ArrayPush(results, "FAIL: Cannot cast to MeshComponent -- Codeware addon may be missing");
                    }
                } else {
                    ArrayPush(results, "WARN: No entSkinnedMeshComponent found via FindComponentByType");
                }
            }
        }

        // --- 8. PreGame check ---
        if GameInstance.GetSystemRequestsHandler().IsPreGame() {
            ArrayPush(results, "FAIL: Currently in PreGame (main menu) -- load a save first");
        } else {
            ArrayPush(results, "PASS: In-game session active");
        }

        // --- 9. Scaled entities status ---
        let scaledCount: Int32 = ArraySize(this.m_scaledEntities);
        if scaledCount > 0 {
            ArrayPush(results, "INFO: Currently tracking " + IntToString(scaledCount) + " scaled entities");
        } else {
            ArrayPush(results, "INFO: No entities currently scaled");
        }

        // --- 10. Tick status ---
        if this.m_ticking {
            ArrayPush(results, "PASS: Tick loop is running (scale persistence active)");
        } else {
            if scaledCount > 0 {
                ArrayPush(results, "WARN: Tick loop is NOT running but entities are scaled -- reapply to restart");
            } else {
                ArrayPush(results, "INFO: Tick loop idle (normal when nothing is scaled)");
            }
        }

        // Log all results
        let r: Int32 = 0;
        while r < ArraySize(results) {
            ModLog(n"PoseSizeChanger", "[Diagnostics] " + results[r]);
            r += 1;
        }

        return results;
    }

    public func GetDiagnosticCount() -> Int32 {
        // Returns the number of checks (for pre-allocation in CET)
        return 12;
    }
}
