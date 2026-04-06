module AMMCompanionClose

// ---------------------------------------------------------------------------
//  AMM Companion Voice Line System
// ---------------------------------------------------------------------------
//
//  What it does
//  ------------
//  Adds voice lines to AMM-spawned NPCs so they actually *talk* when you
//  interact with them. Press F7 (default) to make the nearest companion:
//
//    1. Turn to look at V
//    2. Play a random voice line from the game's built-in VO pool
//    3. Show a facial expression (talking / smiling / reacting)
//    4. Reset to neutral after a few seconds
//
//  The voice lines come from the game's native audio system -- each NPC
//  archetype has its own bank of greeting/reaction lines, so the same
//  "greeting" VO event produces different dialogue depending on the NPC.
//
//  Architecture
//  ------------
//  Similar to CompanionCloseSystem, this is a ScriptableSystem with:
//    - CompanionVoiceSystem  : main system (hotkey, targeting, VO playback)
//    - VoiceResetCallback    : DelayCallback to reset facial animation
//    - CompanionVoiceCooldown: per-NPC cooldown tracking
//
// ---------------------------------------------------------------------------

// ============================
//  Per-NPC cooldown tracker
// ============================

public class CompanionVoiceCooldown extends IScriptable {
    public let entityHash: Uint64;
    public let cooldownEnd: Float;
}

// ============================
//  Facial animation reset
// ============================

public class VoiceResetCallback extends DelayCallback {
    public let npc: wref<GameObject>;

    public func Call() -> Void {
        if IsDefined(this.npc) {
            // Reset facial expression to neutral
            let animFeat = new AnimFeature_FacialReaction();
            animFeat.category = 0;
            animFeat.idle = 0;
            AnimationControllerComponent.ApplyFeatureToReplica(this.npc, n"FacialReaction", animFeat);
        }
    }
}

// ============================
//  Main voice system
// ============================

public class CompanionVoiceSystem extends ScriptableSystem {

    // Cached references
    private let m_player: wref<GameObject>;
    private let m_entitySystem: wref<DynamicEntitySystem>;

    // State
    private let m_active: Bool;

    // Cooldown tracking
    private let m_cooldowns: array<ref<CompanionVoiceCooldown>>;

    // Voice line pool -- weighted toward "greeting" for reliability
    private let m_voiceLines: array<CName>;
    private let m_nextVoiceIndex: Int32;

    // Facial animation presets for variety
    private let m_facialCategories: array<Int32>;
    private let m_facialIdles: array<Int32>;

    // ------------------------------------------------------------------
    //  Lifecycle
    // ------------------------------------------------------------------

    private func OnAttach() -> Void {
        this.m_active = false;
        this.m_nextVoiceIndex = 0;

        this.m_entitySystem = GameInstance.GetDynamicEntitySystem();

        this.InitVoiceLines();
        this.InitFacialPresets();

        // Register the talk hotkey (F7 by default)
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Input/Key", this, n"OnKeyInput")
            .AddTarget(InputTarget.Key(CompanionCloseConfig.TalkKey(), EInputAction.IACT_Press));

        // Clean up on session end
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

        // Skip main menu
        if GameInstance.GetSystemRequestsHandler().IsPreGame() { return; }

        // Refresh entity system reference (may not have been ready in OnAttach)
        if !IsDefined(this.m_entitySystem) {
            this.m_entitySystem = GameInstance.GetDynamicEntitySystem();
        }

        this.m_active = true;
        FTLog("[CompanionVoice] Voice system ready. Press F7 to talk to nearest companion.");
    }

    // ------------------------------------------------------------------
    //  Voice line pool
    // ------------------------------------------------------------------

    private func InitVoiceLines() -> Void {
        ArrayClear(this.m_voiceLines);

        // "greeting" is the most reliable VO event for generic NPCs.
        // The game's Wwise audio engine randomly selects from multiple
        // audio files per NPC archetype, so repeating "greeting" still
        // produces different spoken lines each time.
        ArrayPush(this.m_voiceLines, n"greeting");
        ArrayPush(this.m_voiceLines, n"greeting");
        ArrayPush(this.m_voiceLines, n"greeting");
        ArrayPush(this.m_voiceLines, n"greeting");
        ArrayPush(this.m_voiceLines, n"greeting");

        // Additional VO events -- these work on many NPC archetypes.
        // If an NPC doesn't have a specific event, it silently no-ops.
        ArrayPush(this.m_voiceLines, n"stlh_greeting");
        ArrayPush(this.m_voiceLines, n"curious_grunt");
        ArrayPush(this.m_voiceLines, n"farewell");
    }

    // ------------------------------------------------------------------
    //  Facial animation presets
    // ------------------------------------------------------------------

    private func InitFacialPresets() -> Void {
        ArrayClear(this.m_facialCategories);
        ArrayClear(this.m_facialIdles);

        // category 1=neutral-talk, 2=happy, 3=talk-expressive, 4=concerned
        ArrayPush(this.m_facialCategories, 2);
        ArrayPush(this.m_facialCategories, 3);
        ArrayPush(this.m_facialCategories, 3);
        ArrayPush(this.m_facialCategories, 2);
        ArrayPush(this.m_facialCategories, 4);
        ArrayPush(this.m_facialCategories, 1);

        // idle variants within each category
        ArrayPush(this.m_facialIdles, 3);
        ArrayPush(this.m_facialIdles, 5);
        ArrayPush(this.m_facialIdles, 7);
        ArrayPush(this.m_facialIdles, 2);
        ArrayPush(this.m_facialIdles, 4);
        ArrayPush(this.m_facialIdles, 6);
    }

    // ------------------------------------------------------------------
    //  Pseudo-random selection using game time
    // ------------------------------------------------------------------

    private func GetCurrentTime() -> Float {
        return EngineTime.ToFloat(GameInstance.GetSimTime(this.GetGameInstance()));
    }

    private func GetRandomVoiceLine() -> CName {
        let count: Int32 = ArraySize(this.m_voiceLines);
        if count == 0 { return n"greeting"; }

        let time: Float = this.GetCurrentTime();
        let seed: Int32 = Cast<Int32>(time * 1000.0);

        this.m_nextVoiceIndex += 1;
        let index: Int32 = (seed + this.m_nextVoiceIndex * 7) % count;
        if index < 0 { index = -index; }

        return this.m_voiceLines[index];
    }

    private func GetRandomFacialCategory() -> Int32 {
        let count: Int32 = ArraySize(this.m_facialCategories);
        if count == 0 { return 3; }

        let time: Float = this.GetCurrentTime();
        let seed: Int32 = Cast<Int32>(time * 137.0);
        let index: Int32 = (seed + this.m_nextVoiceIndex * 3) % count;
        if index < 0 { index = -index; }

        return this.m_facialCategories[index];
    }

    private func GetRandomFacialIdle() -> Int32 {
        let count: Int32 = ArraySize(this.m_facialIdles);
        if count == 0 { return 5; }

        let time: Float = this.GetCurrentTime();
        let seed: Int32 = Cast<Int32>(time * 251.0);
        let index: Int32 = (seed + this.m_nextVoiceIndex * 11) % count;
        if index < 0 { index = -index; }

        return this.m_facialIdles[index];
    }

    // ------------------------------------------------------------------
    //  Hotkey handler (F7)
    // ------------------------------------------------------------------

    private cb func OnKeyInput(evt: ref<KeyInputEvent>) -> Void {
        if !this.m_active { return; }
        this.TalkToNearest();
    }

    private cb func OnSessionEnd(evt: ref<GameSessionEvent>) -> Void {
        this.m_active = false;
        ArrayClear(this.m_cooldowns);
    }

    // ------------------------------------------------------------------
    //  Public API
    // ------------------------------------------------------------------

    /// Talk to the nearest AMM-spawned companion within range.
    /// Returns true if a voice line was successfully triggered.
    public func TalkToNearest() -> Bool {
        if !this.m_active { return false; }

        // Refresh player reference if stale
        if !IsDefined(this.m_player) {
            this.m_player = GetPlayer(this.GetGameInstance());
        }
        if !IsDefined(this.m_player) { return false; }

        let nearest: ref<Entity> = this.FindNearestCompanion();
        if !IsDefined(nearest) {
            FTLog("[CompanionVoice] No companion found nearby.");
            return false;
        }

        return this.TalkToEntity(nearest);
    }

    /// Talk to a specific entity by reference.
    /// Returns true if a voice line was triggered (false if on cooldown or invalid).
    public func TalkToEntity(entity: ref<Entity>) -> Bool {
        if !this.m_active || !IsDefined(entity) { return false; }

        let hash: Uint64 = EntityID.GetHash(entity.GetEntityID());

        // Respect cooldown -- don't spam NPCs
        if this.IsOnCooldown(hash) {
            FTLog("[CompanionVoice] NPC is on cooldown, try again in a few seconds.");
            return false;
        }

        let npc: ref<GameObject> = entity as GameObject;
        if !IsDefined(npc) { return false; }

        // Refresh player reference
        if !IsDefined(this.m_player) {
            this.m_player = GetPlayer(this.GetGameInstance());
        }
        if !IsDefined(this.m_player) { return false; }

        // === 1. Make the NPC look at the player ===
        this.TriggerLookAt(npc);

        // === 2. Apply talking facial animation ===
        this.TriggerFacialAnimation(npc);

        // === 3. Play a voice line (slight delay for natural feel) ===
        let voiceLine: CName = this.GetRandomVoiceLine();
        npc.PlayVoiceOver(voiceLine, n"", 0.30, this.m_player.GetEntityID(), true);

        // === 4. Set cooldown for this NPC ===
        this.SetCooldown(hash);

        // === 5. Schedule facial reset after the voice line finishes ===
        let resetCb = new VoiceResetCallback();
        resetCb.npc = npc;
        GameInstance.GetDelaySystem(this.GetGameInstance())
            .DelayCallback(resetCb, CompanionCloseConfig.VoiceLineDuration(), false);

        FTLog("[CompanionVoice] Talking to NPC -- VO: " + NameToString(voiceLine));
        return true;
    }

    /// Check if the voice system is ready to use.
    public func IsActive() -> Bool {
        return this.m_active;
    }

    /// Check if a specific NPC (by entity hash) is currently on cooldown.
    public func IsEntityOnCooldown(entity: ref<Entity>) -> Bool {
        if !IsDefined(entity) { return false; }
        let hash: Uint64 = EntityID.GetHash(entity.GetEntityID());
        return this.IsOnCooldown(hash);
    }

    // ------------------------------------------------------------------
    //  Look-at and facial animation
    // ------------------------------------------------------------------

    private func TriggerLookAt(npc: ref<GameObject>) -> Void {
        let puppet: ref<ScriptedPuppet> = npc as ScriptedPuppet;
        if !IsDefined(puppet) { return; }

        let stimComp: ref<ReactionManagerComponent> = puppet.GetStimReactionComponent();
        if IsDefined(stimComp) {
            // Parameters: target, isPlayer, duration, headOnly, alertedState
            // duration is set from config (default 5s), head+upperBody look-at
            stimComp.ActivateReactionLookAt(this.m_player, false, CompanionCloseConfig.VoiceLookAtDuration(), true, true);
        }
    }

    private func TriggerFacialAnimation(npc: ref<GameObject>) -> Void {
        let animFeat = new AnimFeature_FacialReaction();
        animFeat.category = this.GetRandomFacialCategory();
        animFeat.idle = this.GetRandomFacialIdle();

        // Apply to the NPC's animation controller via the static helper
        AnimationControllerComponent.ApplyFeatureToReplica(npc, n"FacialReaction", animFeat);
    }

    // ------------------------------------------------------------------
    //  Find nearest AMM companion
    // ------------------------------------------------------------------

    private func FindNearestCompanion() -> ref<Entity> {
        // Refresh entity system if needed
        if !IsDefined(this.m_entitySystem) {
            this.m_entitySystem = GameInstance.GetDynamicEntitySystem();
        }
        if !IsDefined(this.m_entitySystem) { return null; }

        let playerPos: Vector4 = this.m_player.GetWorldPosition();
        let bestEntity: ref<Entity>;
        let bestDist: Float = 99999.0;

        // Scan all common AMM / companion tags
        this.SearchTag(n"AMM", playerPos, bestEntity, bestDist);
        this.SearchTag(n"amm", playerPos, bestEntity, bestDist);
        this.SearchTag(n"Companion", playerPos, bestEntity, bestDist);
        this.SearchTag(n"companion", playerPos, bestEntity, bestDist);

        return bestEntity;
    }

    private func SearchTag(tag: CName, playerPos: Vector4, out bestEntity: ref<Entity>, out bestDist: Float) -> Void {
        if !this.m_entitySystem.IsPopulated(tag) { return; }

        let entities: array<ref<Entity>> = this.m_entitySystem.GetTagged(tag);
        let i: Int32 = 0;
        while i < ArraySize(entities) {
            let entity: ref<Entity> = entities[i];
            if IsDefined(entity) && !entity.IsA(n"PlayerPuppet") && !entity.IsA(n"gamePlayerPuppet") {
                let npcPos: Vector4 = entity.GetWorldPosition();
                let dx: Float = playerPos.X - npcPos.X;
                let dy: Float = playerPos.Y - npcPos.Y;
                let dz: Float = playerPos.Z - npcPos.Z;
                let dist: Float = SqrtF(dx * dx + dy * dy + dz * dz);

                if dist < bestDist && dist < CompanionCloseConfig.VoiceMaxDistance() {
                    bestDist = dist;
                    bestEntity = entity;
                }
            }
            i += 1;
        }
    }

    // ------------------------------------------------------------------
    //  Cooldown management
    // ------------------------------------------------------------------

    private func IsOnCooldown(hash: Uint64) -> Bool {
        let currentTime: Float = this.GetCurrentTime();
        let i: Int32 = 0;
        while i < ArraySize(this.m_cooldowns) {
            if Equals(this.m_cooldowns[i].entityHash, hash) {
                return currentTime < this.m_cooldowns[i].cooldownEnd;
            }
            i += 1;
        }
        return false;
    }

    private func SetCooldown(hash: Uint64) -> Void {
        let currentTime: Float = this.GetCurrentTime();
        let endTime: Float = currentTime + CompanionCloseConfig.VoiceCooldown();

        // Update existing entry or create new one
        let i: Int32 = 0;
        while i < ArraySize(this.m_cooldowns) {
            if Equals(this.m_cooldowns[i].entityHash, hash) {
                this.m_cooldowns[i].cooldownEnd = endTime;
                return;
            }
            i += 1;
        }

        let entry = new CompanionVoiceCooldown();
        entry.entityHash = hash;
        entry.cooldownEnd = endTime;
        ArrayPush(this.m_cooldowns, entry);

        // Prune expired cooldown entries to prevent list from growing forever
        this.PruneCooldowns(currentTime);
    }

    private func PruneCooldowns(currentTime: Float) -> Void {
        let i: Int32 = ArraySize(this.m_cooldowns) - 1;
        while i >= 0 {
            if currentTime >= this.m_cooldowns[i].cooldownEnd {
                ArrayErase(this.m_cooldowns, i);
            }
            i -= 1;
        }
    }
}
