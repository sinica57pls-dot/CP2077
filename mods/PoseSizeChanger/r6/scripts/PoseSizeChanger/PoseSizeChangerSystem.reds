module PoseSizeChanger

// ---------------------------------------------------------------------------
//  Pose Size Changer System
// ---------------------------------------------------------------------------
//
//  What it does
//  ------------
//  AMM-style "aim and apply" entity scaler for Photo Mode.
//
//  1. Look at a character (player V, AMM-spawned NPC, photo mode puppet)
//  2. Press F9 (or use the CET overlay) to scale them up
//  3. The scale persists through pose changes
//  4. Press F10 to reset that character back to normal
//
//  The system keeps a list of scaled entities and periodically reapplies
//  the scale so it survives pose switches, component reloads, etc.
//
//  Architecture
//  ------------
//  - PoseSizeChangerSystem : ScriptableSystem managing everything
//  - PoseSizeChangerTick   : DelayCallback for periodic scale maintenance
//  - ScaledEntityEntry     : lightweight struct tracking entityID + factor
//  - Config                : static tunables in Config.reds
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

    // The list of entities we are actively scaling
    private let m_scaledEntities: array<ref<ScaledEntityEntry>>;

    // Last entity the player aimed at (for CET overlay display)
    private let m_lastTargetID: EntityID;
    private let m_lastTargetName: String;
    private let m_ticking: Bool;

    // ------------------------------------------------------------------
    //  Lifecycle
    // ------------------------------------------------------------------

    private func OnAttach() -> Void {
        this.m_active = false;
        this.m_ticking = false;

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
        this.m_active = true;

        FTLog("[PoseSizeChanger] System ready. F9 = scale target, F10 = reset target.");
    }

    // ------------------------------------------------------------------
    //  Session end
    // ------------------------------------------------------------------

    private cb func OnSessionEnd(evt: ref<GameSessionEvent>) -> Void {
        this.ResetAll();
        this.m_active = false;
        this.m_ticking = false;
    }

    // ------------------------------------------------------------------
    //  Hotkey: F9 = apply scale to look-at target
    // ------------------------------------------------------------------

    private cb func OnKeyInput(evt: ref<KeyInputEvent>) -> Void {
        if !this.m_active { return; }

        let target: ref<Entity> = this.FindLookAtEntity();
        if IsDefined(target) {
            this.ApplyScaleToEntity(target, PoseSizeChangerConfig.DefaultScale());
            FTLog("[PoseSizeChanger] Scaled entity to " + FloatToString(PoseSizeChangerConfig.DefaultScale()) + "x");
        } else {
            FTLog("[PoseSizeChanger] No valid target in crosshair.");
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
            FTLog("[PoseSizeChanger] Reset entity to default scale.");
        } else {
            FTLog("[PoseSizeChanger] No valid target in crosshair.");
        }
    }

    // ------------------------------------------------------------------
    //  Tick: periodically reapply scales
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

        // Reapply all active scales
        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            let entry: ref<ScaledEntityEntry> = this.m_scaledEntities[i];
            let entity: ref<Entity> = this.ResolveEntity(entry.entityID);
            if IsDefined(entity) {
                let scaleVec: Vector3 = new Vector3(entry.scaleFactor, entry.scaleFactor, entry.scaleFactor);
                this.ScaleMeshComponents(entity, scaleVec);
            }
            i += 1;
        }

        // Keep ticking while there are scaled entities
        this.ScheduleTick();
    }

    // ------------------------------------------------------------------
    //  Entity targeting (AMM-style look-at)
    // ------------------------------------------------------------------
    //
    //  Scans nearby entities and returns the one closest to the
    //  player's crosshair (forward direction) within a cone.
    //
    //  Checks:  1) Photo Mode puppet
    //           2) The player entity itself
    //           3) All DynamicEntitySystem-tagged entities (AMM, etc.)
    //
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

        // --- 2) Check DynamicEntitySystem tags ---
        if IsDefined(this.m_entitySystem) {
            let tagIndex: Int32 = 0;
            let tags: array<CName>;
            ArrayPush(tags, n"AMM");
            ArrayPush(tags, n"amm");
            ArrayPush(tags, n"Companion");
            ArrayPush(tags, n"companion");
            ArrayPush(tags, n"PhotoMode");
            ArrayPush(tags, n"photomode");

            while tagIndex < ArraySize(tags) {
                let tag: CName = tags[tagIndex];
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

        // --- 3) If nothing found, allow targeting self (player puppet) ---
        if !IsDefined(bestEntity) {
            // Let the player target themselves by looking down or when no NPC is near
            bestEntity = this.m_player as Entity;
        }

        // Store for CET overlay
        if IsDefined(bestEntity) {
            this.m_lastTargetID = bestEntity.GetEntityID();
            this.m_lastTargetName = this.GetEntityDisplayName(bestEntity);
        }

        return bestEntity;
    }

    // Evaluate how well an entity matches the crosshair.
    // Returns dot product (higher = more aligned) or -1.0 if out of range.
    private func EvaluateTarget(entity: ref<Entity>, playerPos: Vector4, playerFwd: Vector4, maxDist: Float, minDot: Float) -> Float {
        let entityPos: Vector4 = entity.GetWorldPosition();

        let dx: Float = entityPos.X - playerPos.X;
        let dy: Float = entityPos.Y - playerPos.Y;
        let dz: Float = entityPos.Z - playerPos.Z;

        let dist: Float = SqrtF(dx * dx + dy * dy + dz * dz);

        // Too close (self) or too far
        if dist < 0.3 || dist > maxDist {
            return -1.0;
        }

        // Normalize direction to entity
        let invDist: Float = 1.0 / dist;
        dx *= invDist;
        dy *= invDist;
        dz *= invDist;

        // Dot product: 1.0 = perfectly aligned, 0.0 = perpendicular
        let dot: Float = dx * playerFwd.X + dy * playerFwd.Y + dz * playerFwd.Z;

        if dot < minDot {
            return -1.0;
        }

        return dot;
    }

    private func IsPlayer(entity: ref<Entity>) -> Bool {
        if entity.IsA(n"PlayerPuppet") || entity.IsA(n"gamePlayerPuppet") {
            return true;
        }
        return false;
    }

    // ------------------------------------------------------------------
    //  Scale management
    // ------------------------------------------------------------------

    public func ApplyScaleToEntity(entity: ref<Entity>, factor: Float) -> Void {
        if !IsDefined(entity) { return; }

        let entityID: EntityID = entity.GetEntityID();

        // Update existing entry or create new one
        let found: Bool = false;
        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            if Equals(EntityID.GetHash(this.m_scaledEntities[i].entityID), EntityID.GetHash(entityID)) {
                this.m_scaledEntities[i].scaleFactor = factor;
                found = true;
            }
            i += 1;
        }

        if !found {
            let entry: ref<ScaledEntityEntry> = new ScaledEntityEntry();
            entry.entityID = entityID;
            entry.scaleFactor = factor;
            entry.displayName = this.GetEntityDisplayName(entity);
            ArrayPush(this.m_scaledEntities, entry);
        }

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

    public func ResetEntity(entityID: EntityID) -> Void {
        let defaultScale: Vector3 = new Vector3(1.0, 1.0, 1.0);

        // Find and remove the entry
        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            if Equals(EntityID.GetHash(this.m_scaledEntities[i].entityID), EntityID.GetHash(entityID)) {
                // Restore default scale
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

    private func ScaleMeshComponents(entity: ref<Entity>, scaleVec: Vector3) -> Void {
        if !IsDefined(entity) { return; }

        let components: array<ref<IComponent>> = entity.GetComponents();
        let i: Int32 = 0;

        while i < ArraySize(components) {
            let comp: ref<IComponent> = components[i];
            if IsDefined(comp) {
                if comp.IsA(n"entSkinnedMeshComponent") || comp.IsA(n"entMeshComponent") {
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
        // Try DynamicEntitySystem first
        if IsDefined(this.m_entitySystem) && this.m_entitySystem.IsManaged(entityID) {
            return this.m_entitySystem.GetEntity(entityID);
        }

        // Try photo puppet
        let playerSystem: ref<PlayerSystem> = GameInstance.GetPlayerSystem(this.GetGameInstance());
        let photoPuppet: wref<gamePuppet> = playerSystem.GetPhotoPuppet();
        if IsDefined(photoPuppet) {
            let puppetEntity: ref<Entity> = photoPuppet as Entity;
            if IsDefined(puppetEntity) && Equals(EntityID.GetHash(puppetEntity.GetEntityID()), EntityID.GetHash(entityID)) {
                return puppetEntity;
            }
        }

        // Try game entity registry (fallback -- the player or world entities)
        if IsDefined(this.m_player) && Equals(EntityID.GetHash(this.m_player.GetEntityID()), EntityID.GetHash(entityID)) {
            return this.m_player as Entity;
        }

        return null;
    }

    private func GetEntityDisplayName(entity: ref<Entity>) -> String {
        // Try to get a meaningful name
        if entity.IsA(n"PlayerPuppet") || entity.IsA(n"gamePlayerPuppet") {
            return "Player V";
        }

        if entity.IsA(n"gamePuppet") || entity.IsA(n"NPCPuppet") {
            return "NPC";
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

    public func GetLastTargetName() -> String {
        return this.m_lastTargetName;
    }

    public func RefreshTarget() -> String {
        let target: ref<Entity> = this.FindLookAtEntity();
        if IsDefined(target) {
            return this.m_lastTargetName;
        }
        return "None";
    }

    public func GetScaleForEntity(entityID: EntityID) -> Float {
        let i: Int32 = 0;
        while i < ArraySize(this.m_scaledEntities) {
            if Equals(EntityID.GetHash(this.m_scaledEntities[i].entityID), EntityID.GetHash(entityID)) {
                return this.m_scaledEntities[i].scaleFactor;
            }
            i += 1;
        }
        return 1.0;
    }
}
