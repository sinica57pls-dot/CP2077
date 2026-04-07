module PoseSizeChanger

// ---------------------------------------------------------------------------
// Configuration -- tweak these values to your liking
// ---------------------------------------------------------------------------

public abstract class PoseSizeChangerConfig {

    // --- Default scale factor ---

    // The default multiplier applied when you press the hotkey.
    // 1.2 = 120% of original size (20% bigger).
    public static func DefaultScale() -> Float = 1.20

    // --- Targeting ---

    // Maximum distance (metres) to detect an entity in your crosshair.
    public static func MaxTargetDistance() -> Float = 25.0

    // Cone half-angle for crosshair detection.
    // 0.92 ~= cos(23 degrees) -- a generous cone so you don't
    // have to aim pixel-perfectly at the NPC.
    public static func MinDotProduct() -> Float = 0.92

    // --- Hotkeys ---

    // Apply scale to the entity you're looking at.
    public static func ApplyKey() -> EInputKey = EInputKey.IK_F9

    // Reset the entity you're looking at back to default scale.
    public static func ResetKey() -> EInputKey = EInputKey.IK_F10

    // --- Tick speed ---

    // How often (seconds) the system reapplies scales to keep them
    // sticky across pose changes, component reloads, etc.
    public static func TickInterval() -> Float = 0.5
}
