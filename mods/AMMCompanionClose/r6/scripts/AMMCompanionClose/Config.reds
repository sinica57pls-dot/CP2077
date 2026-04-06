module AMMCompanionClose

// ---------------------------------------------------------------------------
// Configuration -- tweak these values to your liking
// ---------------------------------------------------------------------------

public abstract class CompanionCloseConfig {

    // =====================================================================
    //  Close-Follow Settings
    // =====================================================================

    // --- Distance thresholds (metres) ---

    // When the companion is further than this, they are teleported next to you.
    // This prevents the "NPC stuck on geometry 50 m behind you" situation.
    public static func TeleportDistance() -> Float = 15.0

    // When the companion is further than this (but closer than TeleportDistance),
    // they are smoothly nudged toward you each tick.
    public static func FollowDistance() -> Float = 3.0

    // How close the companion should end up after a nudge / teleport.
    // This is the "personal space" radius so they don't stand on top of V.
    public static func TargetDistance() -> Float = 1.8

    // --- Tick speed ---

    // How often (seconds) the system checks distances and repositions.
    // Lower = smoother but more CPU. 0.25 is 4 checks/second -- very responsive.
    public static func TickInterval() -> Float = 0.25

    // --- Movement interpolation ---

    // Each nudge moves the companion this fraction of the remaining gap.
    // 0.45 means they close 45 % of the gap per tick -- fast but not instant.
    public static func LerpFactor() -> Float = 0.45

    // --- Toggle key ---

    // The key that toggles "close follow" on/off.
    // Default: F6  (IK_F6).  Change to any EInputKey value you prefer.
    //   IK_F5, IK_F6, IK_F7, IK_F8, IK_Numpad0 ... IK_Numpad9, etc.
    public static func ToggleKey() -> EInputKey = EInputKey.IK_F6

    // =====================================================================
    //  Voice Line Settings  (new in v1.0.1)
    // =====================================================================

    // --- Talk hotkey ---

    // The key that triggers "talk to nearest companion".
    // Default: F7  (IK_F7).  Press while near an AMM-spawned NPC.
    public static func TalkKey() -> EInputKey = EInputKey.IK_F7

    // --- Cooldown ---

    // Minimum seconds between voice lines for the same NPC.
    // Prevents spamming the same NPC with greetings.
    public static func VoiceCooldown() -> Float = 8.0

    // --- Max interaction distance ---

    // How close you need to be (metres) to talk to a companion.
    // NPCs further than this are ignored by "talk to nearest".
    public static func VoiceMaxDistance() -> Float = 12.0

    // --- Voice line duration ---

    // How long (seconds) the facial animation stays active after triggering.
    // After this, the NPC's expression resets to neutral.
    public static func VoiceLineDuration() -> Float = 4.0

    // --- Look-at duration ---

    // How long (seconds) the NPC looks at the player after being talked to.
    public static func VoiceLookAtDuration() -> Float = 5.0
}
