module PhotoModeScale

// ---------------------------------------------------------------------------
//  Photo Mode Scale System
// ---------------------------------------------------------------------------
//
//  What it does
//  ------------
//  When Photo Mode activates, this system scales Male V's visual mesh
//  components by a configurable factor (default 1.2x), making the male
//  model appear bigger in every pose -- shoulders wider, frame larger,
//  more imposing silhouette.
//
//  When Photo Mode exits, the original scale (1.0) is restored so
//  normal gameplay is completely unaffected.
//
//  The system can be toggled on/off with F8, and also exposes a CET
//  overlay for live scale adjustment.
//
//  Architecture
//  ------------
//  - PhotoModeScaleSystem  : ScriptableSystem managing lifecycle
//  - PhotoModeScaleTick    : DelayCallback for periodic checks while
//                            photo mode is active (catches late-spawned
//                            components, pose changes, etc.)
//  - Config                : static tunables in Config.reds
//
// ---------------------------------------------------------------------------

// ============================
//  Tick callback
// ============================

public class PhotoModeScaleTick extends DelayCallback {
    public let system: wref<PhotoModeScaleSystem>;

    public func Call() -> Void {
        if IsDefined(this.system) {
            this.system.OnTick();
        }
    }
}

// ============================
//  Main system
// ============================

public class PhotoModeScaleSystem extends ScriptableSystem {

    // Cached references
    private let m_player: wref<GameObject>;

    // State
    private let m_enabled: Bool;         // User toggle (F8)
    private let m_active: Bool;          // Session is ready
    private let m_inPhotoMode: Bool;     // Photo mode is currently open
    private let m_scaled: Bool;          // Scale is currently applied

    // Runtime scale factor (can be changed from CET overlay)
    private let m_scaleFactor: Float;

    // ------------------------------------------------------------------
    //  Lifecycle
    // ------------------------------------------------------------------

    private func OnAttach() -> Void {
        this.m_enabled = true;
        this.m_active = false;
        this.m_inPhotoMode = false;
        this.m_scaled = false;
        this.m_scaleFactor = PhotoModeScaleConfig.ScaleFactor();

        // Register hotkey toggle
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Input/Key", this, n"OnKeyInput")
            .AddTarget(InputTarget.Key(PhotoModeScaleConfig.ToggleKey(), EInputAction.IACT_Press));

        // Listen for session end
        GameInstance.GetCallbackSystem()
            .RegisterCallback(n"Session/BeforeEnd", this, n"OnSessionEnd");
    }

    /// Called when a saved game is loaded.
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

        FTLog("[PhotoModeScale] System ready. Press F8 to toggle. Scale factor: " + FloatToString(this.m_scaleFactor));
    }

    // ------------------------------------------------------------------
    //  Session end
    // ------------------------------------------------------------------

    private cb func OnSessionEnd(evt: ref<GameSessionEvent>) -> Void {
        // Restore scale before session dies
        if this.m_scaled {
            this.RestoreScale();
        }
        this.m_active = false;
        this.m_inPhotoMode = false;
        this.m_scaled = false;
    }

    // ------------------------------------------------------------------
    //  Hotkey handler
    // ------------------------------------------------------------------

    private cb func OnKeyInput(evt: ref<KeyInputEvent>) -> Void {
        if !this.m_active { return; }

        this.m_enabled = !this.m_enabled;

        if this.m_enabled {
            FTLog("[PhotoModeScale] ENABLED (scale: " + FloatToString(this.m_scaleFactor) + "x)");
            // If we're already in photo mode, apply immediately
            if this.m_inPhotoMode && !this.m_scaled {
                this.ApplyScale();
                this.ScheduleTick();
            }
        } else {
            FTLog("[PhotoModeScale] DISABLED");
            // If currently scaled, restore
            if this.m_scaled {
                this.RestoreScale();
            }
        }
    }

    // ------------------------------------------------------------------
    //  Photo Mode detection
    //  Called from the @wrapMethod hooks below.
    // ------------------------------------------------------------------

    public func OnPhotoModeEnter() -> Void {
        this.m_inPhotoMode = true;

        if !this.m_active || !this.m_enabled { return; }

        // Refresh player ref
        this.m_player = GetPlayer(this.GetGameInstance());

        // Small delay to let photo mode fully initialize the puppet
        let cb = new PhotoModeScaleTick();
        cb.system = this;
        GameInstance.GetDelaySystem(this.GetGameInstance())
            .DelayCallback(cb, 0.3, false);
    }

    public func OnPhotoModeExit() -> Void {
        this.m_inPhotoMode = false;

        if this.m_scaled {
            this.RestoreScale();
        }
    }

    // ------------------------------------------------------------------
    //  Tick (periodic re-application while in photo mode)
    // ------------------------------------------------------------------

    public func ScheduleTick() -> Void {
        if !this.m_enabled || !this.m_active || !this.m_inPhotoMode { return; }

        let cb = new PhotoModeScaleTick();
        cb.system = this;

        // Check every 0.5s to catch pose/puppet changes
        GameInstance.GetDelaySystem(this.GetGameInstance())
            .DelayCallback(cb, 0.5, false);
    }

    public func OnTick() -> Void {
        if !this.m_enabled || !this.m_active || !this.m_inPhotoMode { return; }

        this.ApplyScale();

        // Keep ticking while in photo mode
        this.ScheduleTick();
    }

    // ------------------------------------------------------------------
    //  Scale application
    // ------------------------------------------------------------------

    private func ApplyScale() -> Void {
        let factor: Float = this.m_scaleFactor;
        let scaleVec: Vector3 = new Vector3(factor, factor, factor);

        // --- Scale the photo puppet ---
        let playerSystem: ref<PlayerSystem> = GameInstance.GetPlayerSystem(this.GetGameInstance());
        let photoPuppet: wref<gamePuppet> = playerSystem.GetPhotoPuppet();

        if IsDefined(photoPuppet) {
            // Check gender filter
            if !PhotoModeScaleConfig.MaleOnly() || this.IsMaleBodyType(photoPuppet) {
                this.ScaleEntity(photoPuppet as Entity, scaleVec);
                this.m_scaled = true;
            }
        }

        // --- Also try the player directly (fallback) ---
        if !this.m_scaled && IsDefined(this.m_player) {
            if !PhotoModeScaleConfig.MaleOnly() || this.IsPlayerMale() {
                this.ScaleEntity(this.m_player as Entity, scaleVec);
                this.m_scaled = true;
            }
        }
    }

    private func RestoreScale() -> Void {
        let defaultScale: Vector3 = new Vector3(1.0, 1.0, 1.0);

        let playerSystem: ref<PlayerSystem> = GameInstance.GetPlayerSystem(this.GetGameInstance());
        let photoPuppet: wref<gamePuppet> = playerSystem.GetPhotoPuppet();

        if IsDefined(photoPuppet) {
            this.ScaleEntity(photoPuppet as Entity, defaultScale);
        }

        if IsDefined(this.m_player) {
            this.ScaleEntity(this.m_player as Entity, defaultScale);
        }

        this.m_scaled = false;
    }

    private func ScaleEntity(entity: ref<Entity>, scaleVec: Vector3) -> Void {
        if !IsDefined(entity) { return; }

        let components: array<ref<IComponent>> = entity.GetComponents();
        let i: Int32 = 0;

        while i < ArraySize(components) {
            let comp: ref<IComponent> = components[i];
            if IsDefined(comp) {
                // Scale all mesh-type components
                if comp.IsA(n"entSkinnedMeshComponent") {
                    let skinned: ref<MeshComponent> = comp as MeshComponent;
                    if IsDefined(skinned) {
                        skinned.visualScale = scaleVec;
                    }
                } else {
                    if comp.IsA(n"entMeshComponent") {
                        let mesh: ref<MeshComponent> = comp as MeshComponent;
                        if IsDefined(mesh) {
                            mesh.visualScale = scaleVec;
                        }
                    }
                }
            }
            i += 1;
        }
    }

    // ------------------------------------------------------------------
    //  Gender detection
    // ------------------------------------------------------------------

    private func IsMaleBodyType(puppet: wref<gamePuppet>) -> Bool {
        // Check if the puppet has a male body type
        // The game uses body gender for this, not voice
        let go: wref<GameObject> = puppet as GameObject;
        if IsDefined(go) {
            return !go.IsA(n"FemalePlayerPuppet");
        }
        return true;  // Default to male if we can't determine
    }

    private func IsPlayerMale() -> Bool {
        if IsDefined(this.m_player) {
            return !this.m_player.IsA(n"FemalePlayerPuppet");
        }
        return true;
    }

    // ------------------------------------------------------------------
    //  Public API  --  for CET overlay and other mods
    // ------------------------------------------------------------------

    public func SetEnabled(enabled: Bool) -> Void {
        let wasEnabled: Bool = this.m_enabled;
        this.m_enabled = enabled;

        if enabled && !wasEnabled {
            FTLog("[PhotoModeScale] ENABLED (via API)");
            if this.m_inPhotoMode && !this.m_scaled {
                this.ApplyScale();
                this.ScheduleTick();
            }
        } else {
            if !enabled && wasEnabled {
                FTLog("[PhotoModeScale] DISABLED (via API)");
                if this.m_scaled {
                    this.RestoreScale();
                }
            }
        }
    }

    public func IsEnabled() -> Bool {
        return this.m_enabled;
    }

    public func IsActive() -> Bool {
        return this.m_active;
    }

    public func IsInPhotoMode() -> Bool {
        return this.m_inPhotoMode;
    }

    public func IsScaled() -> Bool {
        return this.m_scaled;
    }

    public func GetScaleFactor() -> Float {
        return this.m_scaleFactor;
    }

    public func SetScaleFactor(factor: Float) -> Void {
        this.m_scaleFactor = factor;
        FTLog("[PhotoModeScale] Scale factor set to " + FloatToString(factor));

        // If currently scaled, re-apply with new factor
        if this.m_scaled && this.m_inPhotoMode {
            this.ApplyScale();
        }
    }
}

// ---------------------------------------------------------------------------
//  Photo Mode hooks -- detect when photo mode opens/closes
// ---------------------------------------------------------------------------

// Hook into the PhotoModePlayerEntityComponent setup to know when
// photo mode activates with a puppet ready for scaling.
@wrapMethod(PhotoModePlayerEntityComponent)
private final func SetupInventory(isCurrentPlayerObjectCustomizable: Bool) {
    wrappedMethod(isCurrentPlayerObjectCustomizable);

    // Notify our system that photo mode puppet is ready
    let system: ref<PhotoModeScaleSystem>;
    let container = GameInstance.GetScriptableSystemsContainer(this.GetOwner().GetGame());
    if IsDefined(container) {
        system = container.Get(n"PhotoModeScale.PhotoModeScaleSystem") as PhotoModeScaleSystem;
        if IsDefined(system) {
            system.OnPhotoModeEnter();
        }
    }
}

// Hook the PhotoMode menu controller to detect exit
@wrapMethod(gameuiPhotoModeMenuController)
protected cb func OnHide() -> Bool {
    // Notify our system photo mode is closing
    let game: GameInstance = GetGameInstance();
    let container = GameInstance.GetScriptableSystemsContainer(game);
    if IsDefined(container) {
        let system: ref<PhotoModeScaleSystem> = container.Get(n"PhotoModeScale.PhotoModeScaleSystem") as PhotoModeScaleSystem;
        if IsDefined(system) {
            system.OnPhotoModeExit();
        }
    }

    return wrappedMethod();
}
