module PhotoModeScale

// ---------------------------------------------------------------------------
// Configuration -- tweak these values to your liking
// ---------------------------------------------------------------------------

public abstract class PhotoModeScaleConfig {

    // --- Scale factor ---

    // The uniform scale multiplier applied to Male V in Photo Mode.
    // 1.2 = 120% of original size (20% bigger).
    // Set to 1.0 to disable scaling without removing the mod.
    public static func ScaleFactor() -> Float = 1.20

    // --- Gender filter ---

    // Only scale male body type?  (true = only male, false = scale all)
    // When true, female V will keep her default scale.
    public static func MaleOnly() -> Bool = true

    // --- Toggle key ---

    // The key that toggles photo-mode scaling on/off.
    // Default: F8  (IK_F8).  Change to any EInputKey value you prefer.
    public static func ToggleKey() -> EInputKey = EInputKey.IK_F8

    // --- Apply to NPCs ---

    // Also scale AMM-spawned / photo mode NPCs by the same factor?
    // false = only scale the player character.
    public static func ScaleNPCs() -> Bool = false
}
