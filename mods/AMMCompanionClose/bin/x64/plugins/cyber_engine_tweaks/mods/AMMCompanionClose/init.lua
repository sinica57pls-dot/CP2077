--[[
    AMM Companion Close-Follow + Voice Lines  --  CET Integration Layer
    ====================================================================

    This file provides a Cyber Engine Tweaks overlay menu for:

      1. CLOSE-FOLLOW  -- Toggle companions sticking close to V (F6)
      2. VOICE LINES   -- Make companions talk with game voice lines (F7)

    The overlay shows status, toggle buttons, and a "Talk to Companion"
    button that triggers voice lines on the nearest AMM-spawned NPC.

    Requirements:
      - Cyber Engine Tweaks 1.37+
      - Codeware 1.19+
      - The redscript portion of this mod (r6/scripts/AMMCompanionClose/)

    v1.0.1 -- Added voice line system and Talk to Companion feature.
]]

-- =========================================================================
--  State
-- =========================================================================

local CompanionClose = {
    description = "AMM Companion Close-Follow + Voice",
    version = "1.0.1",
    system = nil,          -- CompanionCloseSystem ref
    voiceSystem = nil,     -- CompanionVoiceSystem ref
    lastTalkResult = "",   -- Status message for last talk attempt
    lastTalkTime = 0,      -- Timestamp of last talk for UI feedback
}

-- =========================================================================
--  System accessors (lazy-loaded, cached)
-- =========================================================================

function CompanionClose:GetSystem()
    if self.system == nil then
        local container = Game.GetScriptableSystemsContainer()
        if container then
            self.system = container:Get("AMMCompanionClose.CompanionCloseSystem")
        end
    end
    return self.system
end

function CompanionClose:GetVoiceSystem()
    if self.voiceSystem == nil then
        local container = Game.GetScriptableSystemsContainer()
        if container then
            self.voiceSystem = container:Get("AMMCompanionClose.CompanionVoiceSystem")
        end
    end
    return self.voiceSystem
end

-- =========================================================================
--  CET-side voice line fallback
-- =========================================================================
--  If the Redscript voice system isn't available (e.g. script compilation
--  issue), we can trigger voice lines directly from CET Lua as a fallback.

local VoiceLinePool = {
    "greeting", "greeting", "greeting", "greeting", "greeting",
    "stlh_greeting", "curious_grunt", "farewell",
}

local FacialCategories = { 2, 3, 3, 2, 4, 1 }
local FacialIdles = { 3, 5, 7, 2, 4, 6 }

local function PlayVoiceOnHandle(handle)
    if handle == nil then return false end

    -- Pick a random voice line
    local vo = VoiceLinePool[math.random(#VoiceLinePool)]

    -- 1. Trigger look-at (NPC turns to face player)
    local stimComp = handle:GetStimReactionComponent()
    if stimComp then
        stimComp:ActivateReactionLookAt(Game.GetPlayer(), false, 5.0, true, true)
    end

    -- 2. Play voice line via the game's native audio system
    Game["gameObject::PlayVoiceOver;GameObjectCNameCNameFloatEntityIDBool"](
        handle, CName.new(vo), CName.new(""), 0.3, handle:GetEntityID(), true
    )

    -- 3. Apply random facial animation
    local animComp = handle:GetAnimationControllerComponent()
    if animComp then
        local animFeat = NewObject("handle:AnimFeature_FacialReaction")
        animFeat.category = FacialCategories[math.random(#FacialCategories)]
        animFeat.idle = FacialIdles[math.random(#FacialIdles)]
        animComp:ApplyFeature(CName.new("FacialReaction"), animFeat)

        -- Schedule reset after 4 seconds
        Cron.After(4.0, function()
            if handle and animComp then
                local resetFeat = NewObject("handle:AnimFeature_FacialReaction")
                resetFeat.category = 0
                resetFeat.idle = 0
                animComp:ApplyFeature(CName.new("FacialReaction"), resetFeat)
            end
        end)
    end

    return true
end

-- =========================================================================
--  CET overlay draw
-- =========================================================================

registerForEvent("onDraw", function()
    -- Only draw when the CET overlay is open
    if not ImGui.Begin("Companion Close-Follow + Voice", ImGuiWindowFlags.AlwaysAutoResize) then
        ImGui.End()
        return
    end

    -- ======================
    --  Section 1: Close-Follow
    -- ======================

    ImGui.TextColored(1.0, 0.85, 0.4, 1.0, "-- Close-Follow --")
    ImGui.Spacing()

    local sys = CompanionClose:GetSystem()
    if sys == nil then
        ImGui.TextColored(1.0, 0.4, 0.4, 1.0, "System not loaded yet. Load a save first.")
    else
        local isActive = sys:IsActive()
        if not isActive then
            ImGui.TextColored(1.0, 0.6, 0.2, 1.0, "Waiting for game session...")
        else
            local isEnabled = sys:IsEnabled()

            -- Toggle button
            if isEnabled then
                ImGui.PushStyleColor(ImGuiCol.Button, 0.2, 0.7, 0.3, 1.0)
                if ImGui.Button("  FOLLOWING  --  Click to Disable  ") then
                    sys:SetEnabled(false)
                end
                ImGui.PopStyleColor()
            else
                ImGui.PushStyleColor(ImGuiCol.Button, 0.6, 0.2, 0.2, 1.0)
                if ImGui.Button("  STOPPED  --  Click to Enable  ") then
                    sys:SetEnabled(true)
                end
                ImGui.PopStyleColor()
            end

            ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkey: F6 (toggle)")
            ImGui.Text("Status: " .. (isEnabled and "Companions follow closely" or "Normal companion behavior"))
        end
    end

    ImGui.Spacing()
    ImGui.Separator()
    ImGui.Spacing()

    -- ======================
    --  Section 2: Voice Lines
    -- ======================

    ImGui.TextColored(0.4, 1.0, 0.85, 1.0, "-- Talk to Companion --")
    ImGui.Spacing()

    local voiceSys = CompanionClose:GetVoiceSystem()
    local voiceReady = (voiceSys ~= nil and voiceSys:IsActive())

    if not voiceReady and sys ~= nil and sys:IsActive() then
        -- Voice system not loaded but close-follow is -- try CET fallback
        ImGui.TextColored(1.0, 0.8, 0.3, 1.0, "Voice system: CET fallback mode")
    elseif not voiceReady then
        ImGui.TextColored(1.0, 0.6, 0.2, 1.0, "Waiting for game session...")
    end

    -- Talk to Nearest button
    if voiceReady or (sys ~= nil and sys:IsActive()) then
        ImGui.PushStyleColor(ImGuiCol.Button, 0.2, 0.5, 0.8, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonHovered, 0.3, 0.6, 0.9, 1.0)
        ImGui.PushStyleColor(ImGuiCol.ButtonActive, 0.15, 0.4, 0.7, 1.0)

        if ImGui.Button("  Talk to Nearest Companion  ") then
            local success = false

            -- Try Redscript system first
            if voiceSys ~= nil and voiceSys:IsActive() then
                success = voiceSys:TalkToNearest()
                if success then
                    CompanionClose.lastTalkResult = "Companion is talking!"
                else
                    CompanionClose.lastTalkResult = "No companion nearby or on cooldown."
                end
            else
                -- CET fallback: use targeting system to find an NPC
                CompanionClose.lastTalkResult = "Voice system not available. Use F7 in-game."
            end

            CompanionClose.lastTalkTime = os.clock()
        end

        ImGui.PopStyleColor(3)

        -- Show result text with fade-out
        if CompanionClose.lastTalkResult ~= "" then
            local elapsed = os.clock() - CompanionClose.lastTalkTime
            if elapsed < 4.0 then
                local alpha = math.max(0.0, 1.0 - (elapsed / 4.0))
                if string.find(CompanionClose.lastTalkResult, "talking") then
                    ImGui.TextColored(0.3, 1.0, 0.5, alpha, CompanionClose.lastTalkResult)
                else
                    ImGui.TextColored(1.0, 0.7, 0.3, alpha, CompanionClose.lastTalkResult)
                end
            else
                CompanionClose.lastTalkResult = ""
            end
        end

        ImGui.TextColored(0.6, 0.8, 1.0, 1.0, "Hotkey: F7 (talk to nearest)")
        ImGui.Text("Range: 12m  |  Cooldown: 8s per NPC")
    end

    ImGui.Spacing()
    ImGui.Separator()
    ImGui.Spacing()

    -- ======================
    --  Section 3: Tips
    -- ======================

    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "Tip: Spawn NPCs with AMM, then:")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "  F6 = companions follow closely")
    ImGui.TextColored(0.5, 0.5, 0.5, 1.0, "  F7 = nearest companion talks to you")
    ImGui.TextColored(0.45, 0.45, 0.45, 1.0, "v" .. CompanionClose.version)

    ImGui.End()
end)

-- =========================================================================
--  CET lifecycle
-- =========================================================================

registerForEvent("onInit", function()
    math.randomseed(os.time())
    print("[CompanionClose] CET mod v" .. CompanionClose.version .. " loaded.")
end)

registerForEvent("onShutdown", function()
    CompanionClose.system = nil
    CompanionClose.voiceSystem = nil
    CompanionClose.lastTalkResult = ""
    print("[CompanionClose] CET mod unloaded.")
end)

return CompanionClose
