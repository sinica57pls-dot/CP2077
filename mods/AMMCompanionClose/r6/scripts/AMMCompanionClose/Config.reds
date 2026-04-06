module AMMCompanionClose

// ---------------------------------------------------------------------------
// Configuration -- tweak these values to your liking
// ---------------------------------------------------------------------------

public abstract class CompanionCloseConfig {

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
}
