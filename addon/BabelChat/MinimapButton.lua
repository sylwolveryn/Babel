-- MinimapButton.lua — the minimap icon, without LibDBIcon
--
-- The embedded LibDBIcon-1.0 (minor 56), CallbackHandler-1.0 (minor 8) and
-- LibDataBroker were retail builds. They call APIs the 3.3.5 client does not
-- have (SetFixedFrameStrata, numeric texture file IDs, Alpha:SetFromAlpha,
-- securecallfunction) — and worse, LibStub would have let those newer minors
-- REPLACE the 3.3.5 copies other addons load, breaking their minimap buttons
-- and callbacks too. A minimap button is forty lines; this is that.
--
-- The angle is saved as BabelChatDB.minimap.minimapPos, the same field
-- LibDBIcon used, so an existing position carries over. `hide = true` in the
-- same table removes the button.

local ADDON_NAME, addonTable = ...
local L = addonTable.L

local ICON = "Interface\\AddOns\\BabelChat\\img\\icon"
local DEFAULT_ANGLE = 225
local RADIUS = 80

local function PlaceAt(button, angle)
    local radians = math.rad(angle)
    button:ClearAllPoints()
    button:SetPoint("CENTER", Minimap, "CENTER", math.cos(radians) * RADIUS, math.sin(radians) * RADIUS)
end

local function OnDragUpdate(self)
    local mx, my = Minimap:GetCenter()
    local px, py = GetCursorPosition()
    local scale = Minimap:GetEffectiveScale()
    px, py = px / scale, py / scale
    local angle = math.deg(math.atan2(py - my, px - mx)) % 360
    BabelChatDB.minimap.minimapPos = angle
    PlaceAt(self, angle)
end

local function ShowTooltip(owner, tooltip)
    tooltip:SetOwner(owner, "ANCHOR_LEFT")
    tooltip:SetText(L["QT_MINIMAP_TT"])
    tooltip:Show()
end

-- Some 3.3.5 players run Titan Panel, ChocolateBar or another LDB display.
-- Their addons bring LibDataBroker with them; if it is there, offer a launcher
-- too. Nothing is shipped for it, so there is nothing to collide with.
local function RegisterLauncher()
    if not LibStub then return end
    local ldb = LibStub("LibDataBroker-1.1", true)
    if not ldb or ldb:GetDataObjectByName("BabelChat") then return end
    ldb:NewDataObject("BabelChat", {
        type = "launcher",
        icon = ICON,
        OnClick = function() addonTable.OpenConfig() end,
        OnTooltipShow = function(tooltip) tooltip:AddLine(L["QT_MINIMAP_TT"]) end,
    })
end

function addonTable.CreateMinimapButton()
    pcall(RegisterLauncher)

    local settings = BabelChatDB.minimap
    if type(settings) ~= "table" or settings.hide or not Minimap then return end
    if addonTable.minimapButton then return end

    local button = CreateFrame("Button", "BabelChatMinimapButton", Minimap)
    button:SetFrameStrata("MEDIUM")
    button:SetFrameLevel(8)
    button:SetWidth(31)
    button:SetHeight(31)
    button:RegisterForClicks("AnyUp")
    button:RegisterForDrag("LeftButton")
    button:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")

    local background = button:CreateTexture(nil, "BACKGROUND")
    background:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
    background:SetWidth(20)
    background:SetHeight(20)
    background:SetPoint("TOPLEFT", 7, -5)

    local icon = button:CreateTexture(nil, "ARTWORK")
    icon:SetTexture(ICON)
    icon:SetWidth(17)
    icon:SetHeight(17)
    icon:SetPoint("TOPLEFT", 7, -6)

    local border = button:CreateTexture(nil, "OVERLAY")
    border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
    border:SetWidth(53)
    border:SetHeight(53)
    border:SetPoint("TOPLEFT")

    button:SetScript("OnClick", function() addonTable.OpenConfig() end)
    button:SetScript("OnEnter", function(self) ShowTooltip(self, GameTooltip) end)
    button:SetScript("OnLeave", function() GameTooltip:Hide() end)
    button:SetScript("OnDragStart", function(self)
        GameTooltip:Hide()
        self:SetScript("OnUpdate", OnDragUpdate)
    end)
    button:SetScript("OnDragStop", function(self)
        self:SetScript("OnUpdate", nil)
    end)

    PlaceAt(button, tonumber(settings.minimapPos) or DEFAULT_ANGLE)
    button:Show()
    addonTable.minimapButton = button
end
