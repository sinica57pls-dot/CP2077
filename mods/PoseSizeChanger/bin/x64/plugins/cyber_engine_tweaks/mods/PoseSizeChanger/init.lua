--[[
    Pose Size Changer v1.0.1  --  CET Integration Layer
    =====================================================

    AMM-style "aim and apply" entity scaler for Photo Mode and gameplay.

    Usage:
      1. Open CET overlay (~)
      2. Click "Refresh Target" while looking at a character
      3. Adjust the scale slider
      4. Click "Apply to Target"

    Or just use hotkeys:
      F9  = Apply default scale (1.2x) to aimed character
      F10 = Reset aimed character to normal

    Requirements:
      - Cyber Engine Tweaks 1.37+
      - Codeware 1.19+
      - The redscript portion of this mod (r6/scripts/PoseSizeChanger/)

    v1.0.1 fixes:
      - Removed per-frame RefreshTarget (critical perf bug)
      - Fixed ImGui.Button invalid size parameters
      - Added nil guards for entity list rendering
      - Added visual status feedback in overlay
      - Cleaned up UI layout
      - Separated "Apply to Player V" from crosshair targeting
]]

local PoseSizeChanger = {
    description = "Pose Size Changer",
    system = nil,
    scaleFactor = 1.20,
    targetName = "None",
    statusMsg = "",
    statusTime = 0,
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

-- Status message helper (shows for 3 seconds)
function PoseSizeChanger:SetStatus(msg)
    self.statusMsg = msg
    self.statusTime = os.clock()
end

function PoseSizeChanger:GetStatus()
    if self.statusMsg ~= "" and (os.clock() - self.statusTime) < 3.0 then
        return self.statusMsg
    end
    self.statusMsg = ""
    return nil
end

-- -----------------------------------------------------------------------
-- CET overlay draw
-- -----------------------------------------------------------------------
registerForEvent("onDraw", function()
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
    -- STATUS MESSAGE (if any)
    -- ===========================
    local status = PoseSizeChanger:GetStatus()
    if status then
        ImGui.TextColored(0.3, 1.0, 0.6, 1.0, status)
        ImGui.Separator()
    end

    -- ===========================
    -- TARGETING
    -- ===========================
    if ImGui.CollapsingHeader("Targeting", ImGuiTreeNodeFlags.DefaultOpen) then
        ImGui.Spacing()

        -- Display cached target name (lightweight, no computation)
        local cachedName = sys:GetLastTargetName()
        PoseSizeChanger.targetName = cachedName or "None"

        ImGui.Text("Current target:")
        ImGui.SameLine()
        if PoseSizeChanger.targetName ~= "None" and PoseSizeChanger.targetName ~= "" then
            ImGui.TextColored(0.3, 1.0, 0.3, 1.0, PoseSizeChanger.targetName)
        else
            ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "None")
        end

        -- Refresh button -- runs targeting ONCE on click, not every frame
        if ImGui.Button("Refresh Target") then
            local name = sys:UpdateTarget()
            PoseSizeChanger.targetName = name or "None"
            if PoseSizeChanger.targetName ~= "None" and PoseSizeChanger.targetName ~= "" then
                PoseSizeChanger:SetStatus("Target: " .. PoseSizeChanger.targetName)
            else
                PoseSizeChanger:SetStatus("No target in crosshair")
            end
        end
        ImGui.SameLine()
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "(aim at character first)")

        ImGui.Spacing()
    end

    -- ===========================
    -- SCALE CONTROLS
    -- ===========================
    if ImGui.CollapsingHeader("Scale", ImGuiTreeNodeFlags.DefaultOpen) then
        ImGui.Spacing()

        -- Scale slider
        ImGui.PushItemWidth(200)
        PoseSizeChanger.scaleFactor, changed = ImGui.SliderFloat("##scale", PoseSizeChanger.scaleFactor, 0.50, 3.00, "%.2fx")
        ImGui.PopItemWidth()

        ImGui.Spacing()

        -- Presets
        ImGui.Text("Presets:")
        ImGui.SameLine()
        if ImGui.Button("0.8x") then PoseSizeChanger.scaleFactor = 0.80 end
        ImGui.SameLine()
        if ImGui.Button("1.0x") then PoseSizeChanger.scaleFactor = 1.00 end
        ImGui.SameLine()
        if ImGui.Button("1.1x") then PoseSizeChanger.scaleFactor = 1.10 end
        ImGui.SameLine()
        if ImGui.Button("1.2x") then PoseSizeChanger.scaleFactor = 1.20 end
        ImGui.SameLine()
        if ImGui.Button("1.5x") then PoseSizeChanger.scaleFactor = 1.50 end
        ImGui.SameLine()
        if ImGui.Button("2.0x") then PoseSizeChanger.scaleFactor = 2.00 end

        ImGui.Spacing()
    end

    -- ===========================
    -- ACTIONS
    -- ===========================
    if ImGui.CollapsingHeader("Actions", ImGuiTreeNodeFlags.DefaultOpen) then
        ImGui.Spacing()

        -- Apply to crosshair target
        ImGui.PushStyleColor(ImGuiCol.Button, 0.15, 0.55, 0.25, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.2, 0.7, 0.3, 1.0)
        if ImGui.Button("Apply to Target") then
            local ok = sys:ApplyScaleToLookAt(PoseSizeChanger.scaleFactor)
            if ok then
                PoseSizeChanger:SetStatus("Applied " .. string.format("%.2fx", PoseSizeChanger.scaleFactor) .. " to target")
            else
                PoseSizeChanger:SetStatus("No target found -- aim at a character")
            end
        end
        ImGui.PopStyleColor(2)

        ImGui.SameLine()

        -- Reset crosshair target
        ImGui.PushStyleColor(ImGuiCol.Button, 0.55, 0.15, 0.15, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.7, 0.2, 0.2, 1.0)
        if ImGui.Button("Reset Target") then
            local ok = sys:ResetLookAt()
            if ok then
                PoseSizeChanger:SetStatus("Reset target to 1.0x")
            else
                PoseSizeChanger:SetStatus("No target found -- aim at a character")
            end
        end
        ImGui.PopStyleColor(2)

        ImGui.Spacing()

        -- Apply to Player V directly (no crosshair needed)
        ImGui.PushStyleColor(ImGuiCol.Button, 0.15, 0.35, 0.55, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.2, 0.45, 0.7, 1.0)
        if ImGui.Button("Apply to Player V") then
            local ok = sys:ApplyScaleToPlayer(PoseSizeChanger.scaleFactor)
            if ok then
                PoseSizeChanger:SetStatus("Applied " .. string.format("%.2fx", PoseSizeChanger.scaleFactor) .. " to Player V")
            else
                PoseSizeChanger:SetStatus("Player not available")
            end
        end
        ImGui.PopStyleColor(2)

        ImGui.SameLine()

        -- Reset Player V
        ImGui.PushStyleColor(ImGuiCol.Button, 0.45, 0.25, 0.15, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.6, 0.35, 0.2, 1.0)
        if ImGui.Button("Reset Player V") then
            sys:ResetPlayer()
            PoseSizeChanger:SetStatus("Reset Player V to 1.0x")
        end
        ImGui.PopStyleColor(2)

        ImGui.Spacing()

        -- Reset ALL
        ImGui.PushStyleColor(ImGuiCol.Button, 0.55, 0.35, 0.0, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.7, 0.45, 0.0, 1.0)
        if ImGui.Button("Reset ALL Entities") then
            sys:ResetAll()
            PoseSizeChanger:SetStatus("Reset ALL entities to 1.0x")
        end
        ImGui.PopStyleColor(2)

        ImGui.Spacing()
    end

    -- ===========================
    -- ACTIVE SCALES LIST
    -- ===========================
    local count = sys:GetScaledCount()
    if ImGui.CollapsingHeader("Active Scales (" .. tostring(count) .. ")", ImGuiTreeNodeFlags.DefaultOpen) then
        ImGui.Spacing()

        if count > 0 then
            local i = 0
            while i < count do
                local name = sys:GetScaledEntityName(i)
                local factor = sys:GetScaledEntityFactor(i)
                if name and name ~= "" and factor then
                    ImGui.BulletText(string.format("%s: %.2fx", name, factor))
                else
                    ImGui.BulletText(string.format("Entity #%d: %.2fx", i + 1, factor or 1.0))
                end
                i = i + 1
            end
        else
            ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "No entities scaled yet.")
        end

        ImGui.Spacing()
    end

    -- ===========================
    -- HELP
    -- ===========================
    if ImGui.CollapsingHeader("Help") then
        ImGui.Spacing()
        ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkeys:")
        ImGui.BulletText("F9  -- Apply scale to aimed character")
        ImGui.BulletText("F10 -- Reset aimed character")
        ImGui.Spacing()
        ImGui.TextWrapped("Look at any character (Player V, AMM NPCs, Photo Mode puppets), then click 'Refresh Target' to see who you're targeting. Use 'Apply to Target' or F9 to scale them. Scale persists through pose changes!")
        ImGui.Spacing()
    end

    ImGui.End()
end)

-- -----------------------------------------------------------------------
-- CET lifecycle
-- -----------------------------------------------------------------------
registerForEvent("onInit", function()
    print("[PoseSizeChanger] CET mod loaded. v1.0.1")
end)

registerForEvent("onShutdown", function()
    PoseSizeChanger.system = nil
    print("[PoseSizeChanger] CET mod unloaded.")
end)

return PoseSizeChanger
