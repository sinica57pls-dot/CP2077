--[[
    Pose Size Changer  --  CET Integration Layer
    ==============================================

    AMM-style "aim and apply" entity scaler for Photo Mode and gameplay.

    Usage:
      1. Open CET overlay (~)
      2. Look at a character (NPC, V, photo puppet)
      3. Adjust the scale slider
      4. Click "Apply to Target"

    Or just use hotkeys:
      F9  = Apply default scale (1.2x) to aimed character
      F10 = Reset aimed character to normal

    Requirements:
      - Cyber Engine Tweaks 1.37+
      - Codeware 1.19+
      - The redscript portion of this mod (r6/scripts/PoseSizeChanger/)
]]

local PoseSizeChanger = {
    description = "Pose Size Changer",
    system = nil,
    scaleFactor = 1.20,
    targetName = "None",
    showWindow = true,
}

-- -----------------------------------------------------------------------
-- System access
-- -----------------------------------------------------------------------
function PoseSizeChanger:GetSystem()
    if self.system == nil then
        local container = Game.GetScriptableSystemsContainer()
        if container then
            self.system = container:Get("PoseSizeChanger.PoseSizeChangerSystem")
        end
    end
    return self.system
end

-- -----------------------------------------------------------------------
-- CET overlay draw
-- -----------------------------------------------------------------------
registerForEvent("onDraw", function()
    if not PoseSizeChanger.showWindow then return end

    if not ImGui.Begin("Pose Size Changer", ImGuiWindowFlags.AlwaysAutoResize) then
        ImGui.End()
        return
    end

    local sys = PoseSizeChanger:GetSystem()
    if sys == nil then
        ImGui.TextColored(1.0, 0.4, 0.4, 1.0, "System not loaded. Load a save first.")
        ImGui.End()
        return
    end

    local isActive = sys:IsActive()
    if not isActive then
        ImGui.TextColored(1.0, 0.6, 0.2, 1.0, "Waiting for game session...")
        ImGui.End()
        return
    end

    -- ===========================
    -- TARGETING SECTION
    -- ===========================
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- TARGETING ---")
    ImGui.Spacing()

    -- Refresh target every frame
    local targetName = sys:RefreshTarget()
    PoseSizeChanger.targetName = targetName or "None"

    ImGui.Text("Looking at:")
    ImGui.SameLine()
    if PoseSizeChanger.targetName ~= "None" then
        ImGui.TextColored(0.3, 1.0, 0.3, 1.0, PoseSizeChanger.targetName)
    else
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "No target (aim at a character)")
    end

    ImGui.Spacing()

    -- ===========================
    -- SCALE CONTROLS
    -- ===========================
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- SCALE ---")
    ImGui.Spacing()

    -- Scale slider
    ImGui.Text("Scale Factor:")
    PoseSizeChanger.scaleFactor, changed = ImGui.SliderFloat("##scale", PoseSizeChanger.scaleFactor, 0.50, 3.00, "%.2fx")
    ImGui.Spacing()

    -- Preset row
    ImGui.Text("Presets:")
    if ImGui.Button(" 0.8x ") then PoseSizeChanger.scaleFactor = 0.80 end
    ImGui.SameLine()
    if ImGui.Button(" 1.0x ") then PoseSizeChanger.scaleFactor = 1.00 end
    ImGui.SameLine()
    if ImGui.Button(" 1.1x ") then PoseSizeChanger.scaleFactor = 1.10 end
    ImGui.SameLine()
    if ImGui.Button(" 1.2x ") then PoseSizeChanger.scaleFactor = 1.20 end
    ImGui.SameLine()
    if ImGui.Button(" 1.5x ") then PoseSizeChanger.scaleFactor = 1.50 end
    ImGui.SameLine()
    if ImGui.Button(" 2.0x ") then PoseSizeChanger.scaleFactor = 2.00 end

    ImGui.Spacing()
    ImGui.Separator()
    ImGui.Spacing()

    -- ===========================
    -- ACTION BUTTONS
    -- ===========================
    -- Apply to target
    ImGui.PushStyleColor(ImGuiCol.Button, 0.15, 0.55, 0.25, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.2, 0.7, 0.3, 1.0)
    if ImGui.Button("  Apply to Target  ", 200, 30) then
        local ok = sys:ApplyScaleToLookAt(PoseSizeChanger.scaleFactor)
        if ok then
            print("[PoseSizeChanger] Applied " .. string.format("%.2f", PoseSizeChanger.scaleFactor) .. "x to target")
        else
            print("[PoseSizeChanger] No target found")
        end
    end
    ImGui.PopStyleColor(2)

    ImGui.SameLine()

    -- Reset target
    ImGui.PushStyleColor(ImGuiCol.Button, 0.55, 0.15, 0.15, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.7, 0.2, 0.2, 1.0)
    if ImGui.Button("  Reset Target  ", 200, 30) then
        local ok = sys:ResetLookAt()
        if ok then
            print("[PoseSizeChanger] Reset target to 1.0x")
        else
            print("[PoseSizeChanger] No target found")
        end
    end
    ImGui.PopStyleColor(2)

    ImGui.Spacing()

    -- Apply to self (Player V)
    ImGui.PushStyleColor(ImGuiCol.Button, 0.15, 0.35, 0.55, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.2, 0.45, 0.7, 1.0)
    if ImGui.Button("  Apply to Player V  ", 200, 25) then
        -- Use ApplyScaleToLookAt which falls back to player
        sys:ApplyScaleToLookAt(PoseSizeChanger.scaleFactor)
        print("[PoseSizeChanger] Applied " .. string.format("%.2f", PoseSizeChanger.scaleFactor) .. "x to Player V")
    end
    ImGui.PopStyleColor(2)

    ImGui.SameLine()

    -- Reset ALL
    ImGui.PushStyleColor(ImGuiCol.Button, 0.55, 0.35, 0.0, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.7, 0.45, 0.0, 1.0)
    if ImGui.Button("  Reset ALL  ", 200, 25) then
        sys:ResetAll()
        print("[PoseSizeChanger] Reset all entities to 1.0x")
    end
    ImGui.PopStyleColor(2)

    ImGui.Spacing()
    ImGui.Separator()
    ImGui.Spacing()

    -- ===========================
    -- SCALED ENTITIES LIST
    -- ===========================
    local count = sys:GetScaledCount()
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- ACTIVE SCALES (" .. tostring(count) .. ") ---")
    ImGui.Spacing()

    if count > 0 then
        local i = 0
        while i < count do
            local name = sys:GetScaledEntityName(i)
            local factor = sys:GetScaledEntityFactor(i)
            ImGui.BulletText(string.format("%s: %.2fx", name, factor))
            i = i + 1
        end
    else
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "No entities scaled yet.")
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Aim at a character and click Apply!")
    end

    ImGui.Spacing()
    ImGui.Separator()
    ImGui.Spacing()

    -- ===========================
    -- HELP
    -- ===========================
    ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkeys:")
    ImGui.BulletText("F9  -- Apply scale to aimed character")
    ImGui.BulletText("F10 -- Reset aimed character")
    ImGui.Spacing()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Aim at any character: Player V, AMM NPCs,")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Photo Mode puppets, spawned companions.")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Scale persists through pose changes!")

    ImGui.End()
end)

-- -----------------------------------------------------------------------
-- CET lifecycle
-- -----------------------------------------------------------------------
registerForEvent("onInit", function()
    print("[PoseSizeChanger] CET mod loaded.")
end)

registerForEvent("onShutdown", function()
    PoseSizeChanger.system = nil
    print("[PoseSizeChanger] CET mod unloaded.")
end)

return PoseSizeChanger
