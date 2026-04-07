--[[
    Pose Size Changer v1.0.2  --  CET Integration Layer
    =====================================================

    AMM-style "aim and apply" entity scaler for Photo Mode and gameplay.

    v1.0.2 fixes:
      - Replaced CollapsingHeader (CET incompatible) with text section headers
      - Replaced TextWrapped (CET incompatible) with Text
      - Added full diagnostics panel (workability checker)
      - Added mod conflict detection
      - All ImGui calls verified against CET reference implementations

    Requirements:
      - Cyber Engine Tweaks 1.37+
      - Codeware 1.19+
      - Redscript 0.5.31+
      - RED4ext 1.29+
]]

local PoseSizeChanger = {
    description = "Pose Size Changer",
    system = nil,
    scaleFactor = 1.20,
    targetName = "None",
    statusMsg = "",
    statusTime = 0,
    diagResults = {},
    diagRan = false,
}

-- -----------------------------------------------------------------------
-- System access
-- -----------------------------------------------------------------------
function PoseSizeChanger:GetSystem()
    if self.system == nil then
        local ok, container = pcall(Game.GetScriptableSystemsContainer)
        if ok and container then
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

    -- ===========================
    -- STATUS MESSAGE (toast)
    -- ===========================
    local status = PoseSizeChanger:GetStatus()
    if status then
        ImGui.TextColored(0.3, 1.0, 0.6, 1.0, status)
        ImGui.Separator()
    end

    -- ===========================
    -- SYSTEM NOT LOADED
    -- ===========================
    if sys == nil then
        ImGui.TextColored(1.0, 0.4, 0.4, 1.0, "System not loaded.")
        ImGui.Text("Possible causes:")
        ImGui.Text("  - Redscript not installed or outdated")
        ImGui.Text("  - Codeware not installed or outdated")
        ImGui.Text("  - RED4ext not installed or outdated")
        ImGui.Text("  - Script compilation error (check r6/logs/)")
        ImGui.Text("  - Game save not loaded yet")
        ImGui.Separator()
        ImGui.Text("Check: r6/cache/modded/final.redscripts.log")
        ImGui.Text("for compilation errors.")
        ImGui.Separator()

        -- Still show diagnostics section even when system not loaded
        ImGui.TextColored(0.9, 0.4, 0.4, 1.0, "--- DIAGNOSTICS ---")
        ImGui.Spacing()
        ImGui.Text("Cannot run diagnostics: system not loaded.")
        ImGui.Text("")
        ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Troubleshooting checklist:")
        ImGui.Text("  1. Is RED4ext installed?")
        ImGui.Text("     Check: bin/x64/plugins/RED4ext.dll")
        ImGui.Text("  2. Is Redscript installed?")
        ImGui.Text("     Check: r6/scripts/ has .reds files")
        ImGui.Text("  3. Is Codeware installed?")
        ImGui.Text("     Check: red4ext/plugins/Codeware/")
        ImGui.Text("  4. Did scripts compile?")
        ImGui.Text("     Check: r6/cache/modded/final.redscripts.log")
        ImGui.Text("  5. Is a game save loaded?")
        ImGui.Text("     The system activates after loading a save.")

        ImGui.End()
        return
    end

    local isActive = sys:IsActive()
    if not isActive then
        ImGui.TextColored(1.0, 0.6, 0.2, 1.0, "System loaded but not active.")
        ImGui.Text("Load a game save to activate.")
        ImGui.Separator()
    end

    -- ===========================
    -- TARGETING
    -- ===========================
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- TARGETING ---")
    ImGui.Spacing()

    -- Display cached target name (lightweight, no computation)
    local ok, cachedName = pcall(function() return sys:GetLastTargetName() end)
    if ok and cachedName then
        PoseSizeChanger.targetName = cachedName
    end

    ImGui.Text("Current target:")
    ImGui.SameLine()
    if PoseSizeChanger.targetName ~= "None" and PoseSizeChanger.targetName ~= "" then
        ImGui.TextColored(0.3, 1.0, 0.3, 1.0, PoseSizeChanger.targetName)
    else
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "None")
    end

    -- Refresh button -- runs targeting ONCE on click
    if ImGui.Button("Refresh Target") then
        local ok2, name = pcall(function() return sys:UpdateTarget() end)
        if ok2 and name then
            PoseSizeChanger.targetName = name
            if name ~= "None" and name ~= "" then
                PoseSizeChanger:SetStatus("Target: " .. name)
            else
                PoseSizeChanger:SetStatus("No target in crosshair")
            end
        else
            PoseSizeChanger:SetStatus("Error refreshing target")
        end
    end
    ImGui.SameLine()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "(aim at character first)")

    ImGui.Spacing()
    ImGui.Separator()

    -- ===========================
    -- SCALE CONTROLS
    -- ===========================
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- SCALE ---")
    ImGui.Spacing()

    ImGui.PushItemWidth(200)
    PoseSizeChanger.scaleFactor, changed = ImGui.SliderFloat("##scale", PoseSizeChanger.scaleFactor, 0.50, 3.00, "%.2fx")
    ImGui.PopItemWidth()

    ImGui.Spacing()

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
    ImGui.Separator()

    -- ===========================
    -- ACTIONS
    -- ===========================
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- ACTIONS ---")
    ImGui.Spacing()

    -- Apply to crosshair target
    ImGui.PushStyleColor(ImGuiCol.Button, 0.15, 0.55, 0.25, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.2, 0.7, 0.3, 1.0)
    if ImGui.Button("Apply to Target") then
        local ok2, result = pcall(function() return sys:ApplyScaleToLookAt(PoseSizeChanger.scaleFactor) end)
        if ok2 and result then
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
        local ok2, result = pcall(function() return sys:ResetLookAt() end)
        if ok2 and result then
            PoseSizeChanger:SetStatus("Reset target to 1.0x")
        else
            PoseSizeChanger:SetStatus("No target found -- aim at a character")
        end
    end
    ImGui.PopStyleColor(2)

    ImGui.Spacing()

    -- Apply to Player V directly
    ImGui.PushStyleColor(ImGuiCol.Button, 0.15, 0.35, 0.55, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.2, 0.45, 0.7, 1.0)
    if ImGui.Button("Apply to Player V") then
        local ok2, result = pcall(function() return sys:ApplyScaleToPlayer(PoseSizeChanger.scaleFactor) end)
        if ok2 and result then
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
        pcall(function() sys:ResetPlayer() end)
        PoseSizeChanger:SetStatus("Reset Player V to 1.0x")
    end
    ImGui.PopStyleColor(2)

    ImGui.Spacing()

    -- Reset ALL
    ImGui.PushStyleColor(ImGuiCol.Button, 0.55, 0.35, 0.0, 1.0)
    ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.7, 0.45, 0.0, 1.0)
    if ImGui.Button("Reset ALL Entities") then
        pcall(function() sys:ResetAll() end)
        PoseSizeChanger:SetStatus("Reset ALL entities to 1.0x")
    end
    ImGui.PopStyleColor(2)

    ImGui.Spacing()
    ImGui.Separator()

    -- ===========================
    -- ACTIVE SCALES LIST
    -- ===========================
    local ok3, count = pcall(function() return sys:GetScaledCount() end)
    count = (ok3 and count) or 0

    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "--- ACTIVE SCALES (" .. tostring(count) .. ") ---")
    ImGui.Spacing()

    if count > 0 then
        local i = 0
        while i < count do
            local okN, name = pcall(function() return sys:GetScaledEntityName(i) end)
            local okF, factor = pcall(function() return sys:GetScaledEntityFactor(i) end)
            name = (okN and name and name ~= "") and name or ("Entity #" .. tostring(i + 1))
            factor = (okF and factor) or 1.0
            ImGui.Text("  * " .. string.format("%s: %.2fx", name, factor))
            i = i + 1
        end
    else
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "No entities scaled yet.")
    end

    ImGui.Spacing()
    ImGui.Separator()

    -- ===========================
    -- DIAGNOSTICS
    -- ===========================
    ImGui.TextColored(0.9, 0.4, 0.4, 1.0, "--- DIAGNOSTICS ---")
    ImGui.Spacing()

    if ImGui.Button("Run Diagnostics") then
        local okD, results = pcall(function() return sys:RunDiagnostics() end)
        if okD and results then
            PoseSizeChanger.diagResults = {}
            -- Results come back as a Redscript array; iterate
            local len = #results
            if len == 0 then
                -- Try accessing as table/userdata
                local idx = 0
                while true do
                    local okR, line = pcall(function() return results[idx] end)
                    if not okR or line == nil or line == "" then break end
                    table.insert(PoseSizeChanger.diagResults, line)
                    idx = idx + 1
                    if idx > 20 then break end -- safety limit
                end
            else
                for idx = 1, len do
                    table.insert(PoseSizeChanger.diagResults, results[idx])
                end
            end
            PoseSizeChanger.diagRan = true
            PoseSizeChanger:SetStatus("Diagnostics complete -- " .. tostring(#PoseSizeChanger.diagResults) .. " checks")
        else
            PoseSizeChanger.diagResults = {"ERROR: Failed to run diagnostics. System may not be fully loaded."}
            PoseSizeChanger.diagRan = true
            PoseSizeChanger:SetStatus("Diagnostics failed")
        end
    end

    ImGui.SameLine()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "(checks all dependencies)")

    ImGui.Spacing()

    if PoseSizeChanger.diagRan and #PoseSizeChanger.diagResults > 0 then
        for _, line in ipairs(PoseSizeChanger.diagResults) do
            if line then
                local text = tostring(line)
                if string.find(text, "^PASS") then
                    ImGui.TextColored(0.3, 1.0, 0.3, 1.0, text)
                elseif string.find(text, "^FAIL") then
                    ImGui.TextColored(1.0, 0.3, 0.3, 1.0, text)
                elseif string.find(text, "^WARN") then
                    ImGui.TextColored(1.0, 0.8, 0.2, 1.0, text)
                elseif string.find(text, "^INFO") then
                    ImGui.TextColored(0.5, 0.7, 1.0, 1.0, text)
                else
                    ImGui.Text(text)
                end
            end
        end
    elseif PoseSizeChanger.diagRan then
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "No results. System may not support diagnostics.")
    else
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Click 'Run Diagnostics' to check all dependencies.")
    end

    ImGui.Spacing()
    ImGui.Separator()

    -- ===========================
    -- HELP
    -- ===========================
    ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "--- HELP ---")
    ImGui.Spacing()
    ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkeys:")
    ImGui.Text("  F9  -- Apply scale to aimed character")
    ImGui.Text("  F10 -- Reset aimed character")
    ImGui.Spacing()
    ImGui.Text("Look at any character (Player V, AMM NPCs,")
    ImGui.Text("Photo Mode puppets), then click 'Refresh Target'.")
    ImGui.Text("Use 'Apply to Target' or F9 to scale them.")
    ImGui.Text("Scale persists through pose changes!")
    ImGui.Spacing()
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Pose Size Changer v1.0.2")

    ImGui.End()
end)

-- -----------------------------------------------------------------------
-- CET lifecycle
-- -----------------------------------------------------------------------
registerForEvent("onInit", function()
    print("[PoseSizeChanger] CET mod loaded. v1.0.2")
end)

registerForEvent("onShutdown", function()
    PoseSizeChanger.system = nil
    PoseSizeChanger.diagResults = {}
    print("[PoseSizeChanger] CET mod unloaded.")
end)

return PoseSizeChanger
