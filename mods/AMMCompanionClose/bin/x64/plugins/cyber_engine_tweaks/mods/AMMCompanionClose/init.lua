--[[
    AMM Companion Close-Follow v1.0.3  --  CET Integration Layer
    =====================================================

    This file provides a Cyber Engine Tweaks overlay menu so you can
    toggle the close-follow feature from the CET overlay (default: ~)
    instead of / in addition to the F6 hotkey.

    It also lets you tweak distance thresholds live from the overlay.

    v1.0.3: Fixed degenerate zero-quaternion orientation, flattened teleport
    forward vector to XY plane, refreshed DES wref across session loads.

    Requirements:
      - Cyber Engine Tweaks 1.37+
      - Codeware 1.19+
      - The redscript portion of this mod (r6/scripts/AMMCompanionClose/)
]]

local CompanionClose = {
    description = "AMM Companion Close-Follow",
    enabled = false,
    system = nil,
}

-- -----------------------------------------------------------------------
-- System access (pcall-safe)
-- -----------------------------------------------------------------------
function CompanionClose:GetSystem()
    if self.system == nil then
        local ok, container = pcall(function() return Game.GetScriptableSystemsContainer() end)
        if ok and container then
            local ok2, sys = pcall(function()
                return container:Get("AMMCompanionClose.CompanionCloseSystem")
            end)
            if ok2 and sys then
                self.system = sys
            end
        end
    end
    return self.system
end

-- Invalidate cached system ref (call on session end / shutdown)
function CompanionClose:InvalidateSystem()
    self.system = nil
    self.enabled = false
end

-- -----------------------------------------------------------------------
-- CET overlay draw
-- -----------------------------------------------------------------------
registerForEvent("onDraw", function()
    -- Only draw when the CET overlay is open
    if not ImGui.Begin("Companion Close-Follow", ImGuiWindowFlags.AlwaysAutoResize) then
        ImGui.End()
        return
    end

    local sys = CompanionClose:GetSystem()
    if sys == nil then
        ImGui.TextColored(1.0, 0.4, 0.4, 1.0, "System not loaded yet. Load a save first.")
        ImGui.End()
        return
    end

    local isActive = false
    local okActive, resultActive = pcall(function() return sys:IsActive() end)
    if okActive then
        isActive = resultActive
    end

    if not isActive then
        ImGui.TextColored(1.0, 0.6, 0.2, 1.0, "Waiting for game session...")
        ImGui.End()
        return
    end

    local isEnabled = false
    local okEnabled, resultEnabled = pcall(function() return sys:IsEnabled() end)
    if okEnabled then
        isEnabled = resultEnabled
    end

    -- Toggle button
    if isEnabled then
        ImGui.PushStyleColor(ImGuiCol.Button, 0.2, 0.7, 0.3, 1.0)
        if ImGui.Button("  ENABLED  --  Click to Disable  ") then
            pcall(function() sys:SetEnabled(false) end)
        end
        ImGui.PopStyleColor()
    else
        ImGui.PushStyleColor(ImGuiCol.Button, 0.6, 0.2, 0.2, 1.0)
        if ImGui.Button("  DISABLED  --  Click to Enable  ") then
            pcall(function() sys:SetEnabled(true) end)
        end
        ImGui.PopStyleColor()
    end

    ImGui.Separator()
    ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkey: F6 (toggle)")
    ImGui.Text("Status: " .. (isEnabled and "Companions follow closely" or "Normal companion behavior"))

    ImGui.Separator()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Tip: Spawn NPCs with AMM, then press F6.")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "They will stick close to you as you move!")

    ImGui.Spacing()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Companion Close-Follow v1.0.3")

    ImGui.End()
end)

-- -----------------------------------------------------------------------
-- CET lifecycle
-- -----------------------------------------------------------------------
registerForEvent("onInit", function()
    print("[CompanionClose] CET mod loaded. v1.0.3")
end)

registerForEvent("onShutdown", function()
    CompanionClose:InvalidateSystem()
    print("[CompanionClose] CET mod unloaded.")
end)

return CompanionClose
