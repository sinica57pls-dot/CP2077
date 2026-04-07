--[[
    Photo Mode Scale  --  CET Integration Layer
    =============================================

    Provides a Cyber Engine Tweaks overlay menu (default: ~) to:
      - Toggle photo mode scaling on/off
      - Adjust the scale factor with a slider (0.8x to 2.0x)
      - See current status at a glance

    Requirements:
      - Cyber Engine Tweaks 1.37+
      - Codeware 1.19+
      - The redscript portion of this mod (r6/scripts/PhotoModeScale/)
]]

local PhotoModeScale = {
    description = "Photo Mode Scale",
    system = nil,
    sliderValue = 1.20,   -- default matches Config.reds
}

function PhotoModeScale:GetSystem()
    if self.system == nil then
        local container = Game.GetScriptableSystemsContainer()
        if container then
            self.system = container:Get("PhotoModeScale.PhotoModeScaleSystem")
        end
    end
    return self.system
end

-- -----------------------------------------------------------------------
-- CET overlay draw
-- -----------------------------------------------------------------------
registerForEvent("onDraw", function()
    if not ImGui.Begin("Photo Mode Scale", ImGuiWindowFlags.AlwaysAutoResize) then
        ImGui.End()
        return
    end

    local sys = PhotoModeScale:GetSystem()
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

    -- Title
    ImGui.TextColored(0.9, 0.75, 0.3, 1.0, "Male V Photo Mode Scale")
    ImGui.Separator()

    -- Status info
    local inPhoto = sys:IsInPhotoMode()
    local isScaled = sys:IsScaled()
    local isEnabled = sys:IsEnabled()

    if inPhoto then
        ImGui.TextColored(0.3, 1.0, 0.3, 1.0, "Photo Mode: ACTIVE")
    else
        ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Photo Mode: Inactive")
    end

    if isScaled then
        ImGui.SameLine()
        ImGui.TextColored(0.3, 0.8, 1.0, 1.0, "  |  Scaled: YES")
    end

    ImGui.Separator()

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

    -- Scale slider
    ImGui.Text("Scale Factor:")
    PhotoModeScale.sliderValue, changed = ImGui.SliderFloat("##scale", PhotoModeScale.sliderValue, 0.80, 2.00, "%.2fx")
    if changed then
        sys:SetScaleFactor(PhotoModeScale.sliderValue)
    end

    -- Preset buttons
    ImGui.Text("Presets:")
    if ImGui.Button(" 1.0x ") then
        PhotoModeScale.sliderValue = 1.00
        sys:SetScaleFactor(1.00)
    end
    ImGui.SameLine()
    if ImGui.Button(" 1.1x ") then
        PhotoModeScale.sliderValue = 1.10
        sys:SetScaleFactor(1.10)
    end
    ImGui.SameLine()
    if ImGui.Button(" 1.2x ") then
        PhotoModeScale.sliderValue = 1.20
        sys:SetScaleFactor(1.20)
    end
    ImGui.SameLine()
    if ImGui.Button(" 1.3x ") then
        PhotoModeScale.sliderValue = 1.30
        sys:SetScaleFactor(1.30)
    end
    ImGui.SameLine()
    if ImGui.Button(" 1.5x ") then
        PhotoModeScale.sliderValue = 1.50
        sys:SetScaleFactor(1.50)
    end

    ImGui.Separator()
    ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkey: F8 (toggle on/off)")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Scale applies automatically when")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "entering Photo Mode with any pose pack.")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Works with: Rev's Sharp Dressed Man,")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "or any other photomode pose mod!")

    ImGui.End()
end)

-- -----------------------------------------------------------------------
-- CET lifecycle
-- -----------------------------------------------------------------------
registerForEvent("onInit", function()
    print("[PhotoModeScale] CET mod loaded.")
end)

registerForEvent("onShutdown", function()
    PhotoModeScale.system = nil
    print("[PhotoModeScale] CET mod unloaded.")
end)

return PhotoModeScale
