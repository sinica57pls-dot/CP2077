module AMMCompanionClose

// ---------------------------------------------------------------------------
//  AMM Companion Close-Follow System
// ---------------------------------------------------------------------------
//
//  What it does
//  ------------
//  When toggled ON (press F6 by default), every spawned NPC that is registered
//  in the game's DynamicEntitySystem is checked 4 times per second:
//
//    * If they are > 15 m away  -->  instant teleport right next to V
//    * If they are > 3 m away   -->  smooth lerp toward V each tick
//    * Otherwise                 -->  leave them alone (personal space)
//
//  This makes AMM-spawned companions stick to the player like actual
//  companions instead of standing still or slowly shambling after you.
//
//  Architecture
//  ------------
//  We use a ScriptableSystem (not a ScriptableService) because it gives us
//  access to GetGameInstance(), OnAttach / OnPlayerAttach / OnRestored
//  lifecycle hooks, and the game's DelaySystem for scheduling ticks.
//
//  The system is completely self-contained:
//    - CompanionCloseSystem   : main system (lifecycle, tick scheduling)
//    - CompanionCloseTick     : DelayCallback that fires every 0.25 s
//    - Config                 : static tunables in Config.reds
//
// ---------------------------------------------------------------------------

// ============================
//  Tick callback
// ============================

public class CompanionCloseTick extends DelayCallback {
    public let system: wref<CompanionCloseSystem>;

    public func Call() -> Void {
        if IsDefined(this.system) {
            this.system.OnTick();
        }
    }
}

// ============================
//  Main system
// ============================

public class CompanionCloseSystem extends ScriptableSystem {

    // Cached references
    private let m_player: wref<GameObject>;
    private let m_entitySystem: wref<DynamicEntitySystem>;

    // State
    private let m_enabled: Bool;
    private let m_active: Bool;       // True once the session is fully ready

    // Extra tags registered by other mods at runtime
    private let m_extraTags: array<CName>;

    // Track entities we already processed this tick (avoid duplicates across tags)
    private let m_processedThisTick: array<Uint64>;

    // ------------------------------------------------------------------
    //  Lifecycle
    // ------------------------------------------------------------------

    private func OnAttach() -> Void {
        this.m_enabled = false;
        this.m_active = false;

        this.m_entitySystem = GameInstance.GetDynamicEntitySystem();

        // Register the hotkey toggle  --  fires on every press of the key
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Input/Key", this, n"OnKeyInput")
            .AddTarget(InputTarget.Key(CompanionCloseConfig.ToggleKey(), EInputAction.IACT_Press));

        // Listen for session end so we can clean up
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Session/BeforeEnd", this, n"OnSessionEnd");
    }

    /// Called when a saved game is loaded (player already exists).
    private func OnRestored(saveVersion: Int32, gameVersion: Int32) -> Void {
        this.Initialize();
    }

    /// Called on new game once the player puppet is ready.
    private func OnPlayerAttach(request: ref<PlayerAttachRequest>) -> Void {
        this.Initialize();
    }

    private func Initialize() -> Void {
        if this.m_active { return; }

        this.m_player = GetPlayer(this.GetGameInstance());

        if !IsDefined(this.m_player) { return; }

        // Skip main menu
        if GameInstance.GetSystemRequestsHandler().IsPreGame() { return; }

        this.m_active = true;

        ModLog(n"CompanionClose", "System ready. Press F6 to toggle close-follow.");
    }

    // ------------------------------------------------------------------
    //  Hotkey handler
    // ------------------------------------------------------------------

    private cb func OnKeyInput(evt: ref<KeyInputEvent>) -> Void {
        if !this.m_active { return; }

        this.m_enabled = !this.m_enabled;

        if this.m_enabled {
            ModLog(n"CompanionClose", "Close-follow ENABLED");
            this.ScheduleTick();
        } else {
            ModLog(n"CompanionClose", "Close-follow DISABLED");
        }
    }

    // ------------------------------------------------------------------
    //  Session end -- stop ticking
    // ------------------------------------------------------------------

    private cb func OnSessionEnd(evt: ref<GameSessionEvent>) -> Void {
        this.m_active = false;
        this.m_enabled = false;
    }

    // ------------------------------------------------------------------
    //  Tick scheduling  (self-rescheduling via DelaySystem)
    // ------------------------------------------------------------------

    public func ScheduleTick() -> Void {
        if !this.m_enabled || !this.m_active { return; }

        let cb = new CompanionCloseTick();
        cb.system = this;

        GameInstance.GetDelaySystem(this.GetGameInstance())
            .DelayCallback(cb, CompanionCloseConfig.TickInterval(), false);
    }

    /// Called by CompanionCloseTick every interval.
    public func OnTick() -> Void {
        if !this.m_enabled || !this.m_active { return; }

        // Refresh player ref (can become invalid after certain transitions)
        if !IsDefined(this.m_player) {
            this.m_player = GetPlayer(this.GetGameInstance());
        }
        if !IsDefined(this.m_player) {
            this.ScheduleTick();
            return;
        }

        let playerPos: Vector4 = this.m_player.GetWorldPosition();
        let playerFwd: Vector4 = this.m_player.GetWorldForward();

        // Clear the processed-this-tick set
        ArrayClear(this.m_processedThisTick);

        this.UpdateAllCompanions(playerPos, playerFwd);

        // Reschedule for the next tick
        this.ScheduleTick();
    }

    // ------------------------------------------------------------------
    //  Core movement logic
    // ------------------------------------------------------------------

    private func UpdateAllCompanions(playerPos: Vector4, playerFwd: Vector4) -> Void {
        if !IsDefined(this.m_entitySystem) { return; }

        // Default tags that AMM and Codeware commonly use
        this.TryUpdateTag(n"AMM", playerPos, playerFwd);
        this.TryUpdateTag(n"amm", playerPos, playerFwd);
        this.TryUpdateTag(n"Companion", playerPos, playerFwd);
        this.TryUpdateTag(n"companion", playerPos, playerFwd);

        // User-registered extra tags from other mods
        let i: Int32 = 0;
        while i < ArraySize(this.m_extraTags) {
            this.TryUpdateTag(this.m_extraTags[i], playerPos, playerFwd);
            i += 1;
        }
    }

    private func TryUpdateTag(tag: CName, playerPos: Vector4, playerFwd: Vector4) -> Void {
        if !this.m_entitySystem.IsPopulated(tag) { return; }

        let entities: array<ref<Entity>> = this.m_entitySystem.GetTagged(tag);
        let i: Int32 = 0;
        while i < ArraySize(entities) {
            let entity: ref<Entity> = entities[i];
            if IsDefined(entity) {
                let hash: Uint64 = EntityID.ToHash(entity.GetEntityID());

                // Skip if we already processed this entity under a different tag
                if !this.WasProcessed(hash) {
                    ArrayPush(this.m_processedThisTick, hash);
                    this.UpdateSingleCompanion(entity, playerPos, playerFwd);
                }
            }
            i += 1;
        }
    }

    private func WasProcessed(hash: Uint64) -> Bool {
        let i: Int32 = 0;
        while i < ArraySize(this.m_processedThisTick) {
            if Equals(this.m_processedThisTick[i], hash) {
                return true;
            }
            i += 1;
        }
        return false;
    }

    private func UpdateSingleCompanion(entity: ref<Entity>, playerPos: Vector4, playerFwd: Vector4) -> Void {
        // Don't try to move the player themselves
        if entity.IsA(n"PlayerPuppet") { return; }
        if entity.IsA(n"gamePlayerPuppet") { return; }

        let npcPos: Vector4 = entity.GetWorldPosition();

        // Full 3D distance
        let diff: Vector4;
        diff.X = playerPos.X - npcPos.X;
        diff.Y = playerPos.Y - npcPos.Y;
        diff.Z = playerPos.Z - npcPos.Z;
        diff.W = 0.0;

        let dist: Float = SqrtF(diff.X * diff.X + diff.Y * diff.Y + diff.Z * diff.Z);

        let teleportDist: Float = CompanionCloseConfig.TeleportDistance();
        let followDist: Float = CompanionCloseConfig.FollowDistance();
        let targetDist: Float = CompanionCloseConfig.TargetDistance();

        if dist <= followDist {
            // Already close enough -- do nothing
            return;
        }

        let targetPos: Vector4;

        if dist > teleportDist {
            // --- TELEPORT --- too far, snap them right behind the player
            targetPos.X = playerPos.X - playerFwd.X * targetDist;
            targetPos.Y = playerPos.Y - playerFwd.Y * targetDist;
            targetPos.Z = playerPos.Z - playerFwd.Z * targetDist;
            targetPos.W = 0.0;
        } else {
            // --- LERP --- smoothly pull them toward the player
            let lerpFactor: Float = CompanionCloseConfig.LerpFactor();

            // Normalise direction (NPC -> player)
            let len: Float = dist;
            if len < 0.01 { return; }

            let dirX: Float = diff.X / len;
            let dirY: Float = diff.Y / len;
            let dirZ: Float = diff.Z / len;

            // How far to move this tick
            let moveAmount: Float = (dist - targetDist) * lerpFactor;
            if moveAmount < 0.05 { return; }  // negligible

            targetPos.X = npcPos.X + dirX * moveAmount;
            targetPos.Y = npcPos.Y + dirY * moveAmount;
            targetPos.Z = npcPos.Z + dirZ * moveAmount;
            targetPos.W = 0.0;
        }

        this.TeleportEntity(entity, targetPos);
    }

    // ------------------------------------------------------------------
    //  Teleport helper
    // ------------------------------------------------------------------

    private func TeleportEntity(entity: ref<Entity>, pos: Vector4) -> Void {
        let transform: WorldTransform;

        // WorldPosition uses FixedPoint fields; cast from Float
        transform.Position.x = Cast(pos.X);
        transform.Position.y = Cast(pos.Y);
        transform.Position.z = Cast(pos.Z);

        // Keep the NPC's current orientation so they don't snap-rotate
        // (WorldTransform default Orientation is identity quaternion which is fine)

        entity.SetWorldTransform(transform);
    }

    // ------------------------------------------------------------------
    //  Public API  --  for other mods and CET
    // ------------------------------------------------------------------

    public func SetEnabled(enabled: Bool) -> Void {
        if !this.m_active {
            ModLog(n"CompanionClose", "System not yet active. Wait until in-game.");
            return;
        }

        let wasEnabled: Bool = this.m_enabled;
        this.m_enabled = enabled;

        if enabled {
            ModLog(n"CompanionClose", "Close-follow ENABLED (via API)");
            if !wasEnabled {
                this.ScheduleTick();
            }
        } else {
            ModLog(n"CompanionClose", "Close-follow DISABLED (via API)");
        }
    }

    public func IsEnabled() -> Bool {
        return this.m_enabled;
    }

    public func IsActive() -> Bool {
        return this.m_active;
    }

    // ------------------------------------------------------------------
    //  Custom tag registration (for other mods)
    // ------------------------------------------------------------------

    public func RegisterTag(tag: CName) -> Void {
        let i: Int32 = 0;
        while i < ArraySize(this.m_extraTags) {
            if Equals(this.m_extraTags[i], tag) {
                return;  // already registered
            }
            i += 1;
        }
        ArrayPush(this.m_extraTags, tag);
        ModLog(n"CompanionClose", "Registered extra tag: " + NameToString(tag));
    }

    public func UnregisterTag(tag: CName) -> Void {
        let i: Int32 = 0;
        while i < ArraySize(this.m_extraTags) {
            if Equals(this.m_extraTags[i], tag) {
                ArrayErase(this.m_extraTags, i);
                ModLog(n"CompanionClose", "Unregistered extra tag: " + NameToString(tag));
                return;
            }
            i += 1;
        }
    }
}
