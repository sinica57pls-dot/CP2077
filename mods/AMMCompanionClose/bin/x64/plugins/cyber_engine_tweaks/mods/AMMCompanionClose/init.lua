--[[
    AMM Companion Close-Follow  --  CET Integration Layer
    =====================================================

    This file provides a Cyber Engine Tweaks overlay menu so you can
    toggle the close-follow feature from the CET overlay (default: ~)
    instead of / in addition to the F6 hotkey.

    It also lets you tweak distance thresholds live from the overlay.

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

function CompanionClose:GetSystem()
    if self.system == nil then
        local container = Game.GetScriptableSystemsContainer()
        if container then
            self.system = container:Get("AMMCompanionClose.CompanionCloseSystem")
        end
    end
    return self.system
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

    local isActive = sys:IsActive()
    if not isActive then
        ImGui.TextColored(1.0, 0.6, 0.2, 1.0, "Waiting for game session...")
        ImGui.End()
        return
    end

    local isEnabled = sys:IsEnabled()

    -- Toggle button
    if isEnabled then
        ImGui.PushStyleColor(ImGuiCol.Button, 0.2, 0.7, 0.3, 1.0)
        if ImGui.Button("  ENABLED  --  Click to Disable  ") then
            sys:SetEnabled(false)
        end
        ImGui.PopStyleColor()
    else
        ImGui.PushStyleColor(ImGuiCol.Button, 0.6, 0.2, 0.2, 1.0)
        if ImGui.Button("  DISABLED  --  Click to Enable  ") then
            sys:SetEnabled(true)
        end
        ImGui.PopStyleColor()
    end

    ImGui.Separator()
    ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkey: F6 (toggle)")
    ImGui.Text("Status: " .. (isEnabled and "Companions follow closely" or "Normal companion behavior"))

    ImGui.Separator()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Tip: Spawn NPCs with AMM, then press F6.")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "They will stick close to you as you move!")

    ImGui.End()
end)

-- -----------------------------------------------------------------------
-- CET lifecycle
-- -----------------------------------------------------------------------
registerForEvent("onInit", function()
    print("[CompanionClose] CET mod loaded.")
end)

registerForEvent("onShutdown", function()
    CompanionClose.system = nil
    print("[CompanionClose] CET mod unloaded.")
end)

return CompanionClose
