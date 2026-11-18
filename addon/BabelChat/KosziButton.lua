-- KosziButton.lua — a "Köszi" button that says a random haiku in /say
--
-- An addon may call SendChatMessage for /say from a click on the 3.3.5
-- client, so the button speaks for the player directly. `/koszi` does the
-- same from the chat box; `/koszi show` and `/koszi hide` toggle the button.
--
-- The button's position lives in BabelChatDB.minimap.koszi — a nested table.
-- A new top-level key in BabelChatDB would rehash the table the companion app
-- holds a pointer into (see PreallocateCompanionKeys), so none is added here.

local ADDON_NAME, addonTable = ...
local L = addonTable.L

local function Settings()
    local minimap = BabelChatDB.minimap
    if type(minimap) ~= "table" then
        minimap = {}
        BabelChatDB.minimap = minimap
    end
    if type(minimap.koszi) ~= "table" then
        minimap.koszi = {}
    end
    return minimap.koszi
end

function addonTable.RandomHaiku()
    local haikus = addonTable.HAIKUS
    if type(haikus) ~= "table" or #haikus == 0 then return nil end
    return haikus[math.random(#haikus)]
end

function addonTable.SayHaiku()
    local haiku = addonTable.RandomHaiku()
    if haiku then
        SendChatMessage(haiku, "SAY")
    end
    return haiku
end

local function SavePosition(button)
    local point, _, relativePoint, x, y = button:GetPoint()
    local settings = Settings()
    settings.point, settings.relativePoint, settings.x, settings.y = point, relativePoint, x, y
end

local function Restore(button)
    local settings = Settings()
    button:ClearAllPoints()
    if settings.point then
        button:SetPoint(settings.point, UIParent, settings.relativePoint or settings.point, settings.x or 0, settings.y or 0)
    else
        button:SetPoint("CENTER", UIParent, "CENTER", 0, -180)
    end
end

function addonTable.CreateKosziButton()
    if addonTable.kosziButton then return addonTable.kosziButton end

    local button = CreateFrame("Button", "BabelChatKosziButton", UIParent, "UIPanelButtonTemplate")
    button:SetWidth(72)
    button:SetHeight(24)
    button:SetText(L["KOSZI_LABEL"])
    button:SetFrameStrata("MEDIUM")
    button:SetMovable(true)
    button:SetClampedToScreen(true)
    button:RegisterForDrag("LeftButton")
    button:RegisterForClicks("LeftButtonUp")

    button:SetScript("OnDragStart", function(self) self:StartMoving() end)
    button:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        SavePosition(self)
    end)
    button:SetScript("OnClick", function() addonTable.SayHaiku() end)
    button:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_TOP")
        GameTooltip:SetText(L["KOSZI_TT"])
        GameTooltip:Show()
    end)
    button:SetScript("OnLeave", function() GameTooltip:Hide() end)

    Restore(button)
    if Settings().hide then button:Hide() else button:Show() end

    addonTable.kosziButton = button
    return button
end

function addonTable.SetKosziButtonShown(shown)
    Settings().hide = not shown
    local button = addonTable.CreateKosziButton()
    if shown then button:Show() else button:Hide() end
end

SLASH_BABELCHATKOSZI1 = "/koszi"
SLASH_BABELCHATKOSZI2 = "/köszi"
SlashCmdList["BABELCHATKOSZI"] = function(msg)
    local command = strtrim(msg or ""):lower()
    if command == "show" then
        addonTable.SetKosziButtonShown(true)
    elseif command == "hide" then
        addonTable.SetKosziButtonShown(false)
        DEFAULT_CHAT_FRAME:AddMessage("|cff9482c9BabelChat|r: " .. L["KOSZI_HIDDEN"])
    else
        addonTable.SayHaiku()
    end
end
