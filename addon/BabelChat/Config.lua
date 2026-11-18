-- Config.lua — Settings UI for BabelChat
-- Based on Pirson's WoWTranslator Config, extended with companion settings.

local ADDON_NAME, addonTable = ...
local L = addonTable.L

-- Vertical gap between a section heading and the first control under it.
-- GameFontNormal draws 14px down from its anchor and a checkbox 26px, both
-- anchored TOPLEFT at x=16, so anything under about 20 makes them overlap.
-- The General and Companion sections already used 25; the Categories and
-- Channels sections used 5, and looked like it.
local SECTION_GAP = 25

-- Height of the scrolling content. Generous on purpose: too tall only means
-- a little empty space at the bottom, too short silently clips a section.
local CONTENT_HEIGHT = 930

local function CountEntries(dict)
    if type(dict) ~= "table" then return 0 end
    local n = 0
    for _ in pairs(dict) do n = n + 1 end
    return n
end

local function AddTooltip(frame, text)
    if not text then return end
    frame:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:SetText(text, nil, nil, nil, nil, true)
        GameTooltip:Show()
    end)
    frame:SetScript("OnLeave", function()
        GameTooltip:Hide()
    end)
end

-- Solid colour fill. Texture:SetColorTexture arrived in 7.0; on 3.3.5
-- SetTexture(r, g, b, a) does the same job.
local function Fill(texture, r, g, b, a)
    texture:SetTexture(r, g, b, a or 1)
end

local function SetFrameSize(frame, width, height)
    frame:SetWidth(width)
    frame:SetHeight(height)
end

-- Open the options window on our panel. Exported: the slash command, the
-- welcome frame and the minimap button all land here. Returns false when the
-- panel does not exist yet, so the caller can say so.
--
-- Called twice on purpose. On 3.3.5 the first call only opens the Interface
-- Options window — on the Game tab when it was closed — and the second is
-- what selects the AddOn panel. A well-known client bug of that patch.
function addonTable.OpenConfig()
    local panel = addonTable.configPanel
    if not panel or not InterfaceOptionsFrame_OpenToCategory then return false end
    InterfaceOptionsFrame_OpenToCategory(panel)
    InterfaceOptionsFrame_OpenToCategory(panel)
    return true
end

function addonTable.CreateConfigUI()
    local db = BabelChatDB
    -- Parented to the options container the way Blizzard's own panels are,
    -- and hidden: InterfaceOptionsFrame shows it, sizes it and anchors it.
    local canvas = CreateFrame("Frame", "BabelChatPanel", InterfaceOptionsFramePanelContainer or UIParent)
    canvas.name = "BabelChat"
    canvas:Hide()

    -- The options window gives a panel no scrolling of its own. The content
    -- runs well past the 3.3.5 panel height, so everything is built inside a
    -- scroll frame; `panel` below is the scrolling content.
    local scroll = CreateFrame("ScrollFrame", "BabelChatPanelScroll", canvas, "UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT", 0, -4)
    scroll:SetPoint("BOTTOMRIGHT", -28, 4)

    local panel = CreateFrame("Frame", "BabelChatPanelContent", scroll)
    SetFrameSize(panel, 600, CONTENT_HEIGHT)
    scroll:SetScrollChild(panel)

    local yOffset = -16

    -- Title
    local title = panel:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
    title:SetPoint("TOPLEFT", 16, yOffset)
    title:SetText(L["UI_TITLE"])

    -- Logo
    local logo = panel:CreateTexture(nil, "ARTWORK")
    SetFrameSize(logo, 64, 64)
    logo:SetPoint("TOPRIGHT", -20, -10)
    logo:SetTexture("Interface\\AddOns\\BabelChat\\img\\icon")

    local version = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
    version:SetPoint("TOP", logo, "BOTTOM", 0, -2)
    version:SetText("v" .. (GetAddOnMetadata(ADDON_NAME, "Version") or "3.3.5a"))

    -- ════════════════════════════════════
    -- SECTION 1: GENERAL
    -- ════════════════════════════════════
    yOffset = yOffset - 40
    local genHeader = panel:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    genHeader:SetPoint("TOPLEFT", 16, yOffset)
    genHeader:SetText("|cffd597ff" .. L["GEN_HEADER"] .. "|r")

    yOffset = yOffset - 25
    local mainCB = CreateFrame("CheckButton", "WCT_MainEnableCB", panel, "InterfaceOptionsCheckButtonTemplate")
    mainCB:SetPoint("TOPLEFT", 16, yOffset)
    _G[mainCB:GetName() .. "Text"]:SetText(L["UI_ENABLE_TEXT"])
    mainCB:SetChecked(db.dict.enabled)
    mainCB:SetScript("OnClick", function(self) db.dict.enabled = self:GetChecked() end)
    AddTooltip(mainCB, L["TT_ENABLE"])

    -- The gloss and the overlay answer the same question, so by default only
    -- one of them speaks. This is the escape hatch for players who want both.
    yOffset = yOffset - 24
    local alwaysCB = CreateFrame("CheckButton", "WCT_AlwaysGlossCB", panel, "InterfaceOptionsCheckButtonTemplate")
    alwaysCB:SetPoint("TOPLEFT", 16, yOffset)
    _G[alwaysCB:GetName() .. "Text"]:SetText(L["UI_ALWAYS_GLOSS"])
    _G[alwaysCB:GetName() .. "Text"]:SetFontObject("GameFontHighlightSmall")
    alwaysCB:SetChecked(db.dict.mode == "always")
    alwaysCB:SetScript("OnClick", function(self)
        db.dict.mode = self:GetChecked() and "always" or "auto"
    end)
    AddTooltip(alwaysCB, L["TT_ALWAYS_GLOSS"])

    -- Color button
    local colorBtn = CreateFrame("Button", "WCT_ColorBtn", panel, "UIPanelButtonTemplate")
    colorBtn:SetPoint("LEFT", mainCB, "RIGHT", 220, 0)
    SetFrameSize(colorBtn, 120, 22)
    colorBtn:SetText(L["UI_COLOR_BTN"])
    AddTooltip(colorBtn, L["TT_COLOR"])

    local colorPreview = colorBtn:CreateTexture(nil, "OVERLAY")
    colorPreview:SetPoint("LEFT", colorBtn, "RIGHT", 10, 0)
    SetFrameSize(colorPreview, 18, 18)

    local function UpdateColorPreview()
        local hex = db.dict.chatColor or "00ff00"
        local r = tonumber(hex:sub(1, 2), 16) / 255
        local g = tonumber(hex:sub(3, 4), 16) / 255
        local b = tonumber(hex:sub(5, 6), 16) / 255
        Fill(colorPreview, r, g, b)
    end

    -- The 3.3.5 colour picker is driven through fields on the frame, not the
    -- SetupColorPickerAndShow call retail has. `func` runs on every change,
    -- `cancelFunc` gets back `previousValues` when the player presses Cancel.
    local function SaveColor(r, g, b)
        db.dict.chatColor = string.format("%02x%02x%02x", r * 255, g * 255, b * 255)
        UpdateColorPreview()
    end

    colorBtn:SetScript("OnClick", function()
        local hex = db.dict.chatColor or "00ff00"
        local r = tonumber(hex:sub(1, 2), 16) / 255
        local g = tonumber(hex:sub(3, 4), 16) / 255
        local b = tonumber(hex:sub(5, 6), 16) / 255
        -- Cleared first: SetColorRGB fires the current `func`, which may still
        -- belong to some other addon's swatch.
        ColorPickerFrame.func = nil
        ColorPickerFrame.opacityFunc = nil
        ColorPickerFrame.cancelFunc = nil
        ColorPickerFrame.hasOpacity = false
        ColorPickerFrame.previousValues = { r, g, b }
        ColorPickerFrame:SetColorRGB(r, g, b)
        ColorPickerFrame.func = function()
            SaveColor(ColorPickerFrame:GetColorRGB())
        end
        ColorPickerFrame.cancelFunc = function(previous)
            if type(previous) == "table" then
                SaveColor(previous[1], previous[2], previous[3])
            end
        end
        -- Hidden first so its OnShow runs again and reads the fields above.
        ColorPickerFrame:Hide()
        ShowUIPanel(ColorPickerFrame)
    end)
    UpdateColorPreview()

    -- Separator
    yOffset = yOffset - 30
    local line1 = panel:CreateTexture(nil, "ARTWORK")
    SetFrameSize(line1, 580, 1)
    line1:SetPoint("TOPLEFT", 16, yOffset)
    Fill(line1, 1, 1, 1, 0.1)

    -- ════════════════════════════════════
    -- SECTION 2: CATEGORIES
    -- ════════════════════════════════════
    yOffset = yOffset - 15
    local filterHeader = panel:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    filterHeader:SetPoint("TOPLEFT", 16, yOffset)
    filterHeader:SetText("|cffd597ff" .. L["CAT_HEADER"] .. "|r")

    local categories = {
        { text = L["CAT_MAZZ"],    key = "showDungeons",    tt = L["TT_CAT_MAZZ"],    dict = addonTable.MazzRaidDict },
        { text = L["CAT_SOCIAL"],  key = "showSocial",      tt = L["TT_CAT_SOCIAL"],  dict = addonTable.SocialDict },
        { text = L["CAT_CLASSES"], key = "showClasses",     tt = L["TT_CAT_CLASSES"], dict = addonTable.ClasesDict },
        { text = L["CAT_ROLES"],   key = "showRoles",       tt = L["TT_CAT_ROLES"],   dict = addonTable.RolesDict },
        { text = L["CAT_STATS"],   key = "showStats",       tt = L["TT_CAT_STATS"],   dict = addonTable.EstadisticasDict },
        { text = L["CAT_PROF"],    key = "showProfessions", tt = L["TT_CAT_PROF"],    dict = addonTable.ProfesionesDict },
        { text = L["CAT_COMBAT"],  key = "showCombat",      tt = L["TT_CAT_COMBAT"],  dict = addonTable.CombateDict },
        { text = L["CAT_TRADE"],   key = "showTrade",       tt = L["TT_CAT_TRADE"],   dict = addonTable.ComercioDict },
        { text = L["CAT_GROUPS"],  key = "showGroups",      tt = L["TT_CAT_GROUPS"],  dict = addonTable.GruposDict },
        { text = L["CAT_GUILD"],   key = "showGuild",       tt = L["TT_CAT_GUILD"],   dict = addonTable.HermandadDict },
        { text = L["CAT_STATUS"],  key = "showStatus",      tt = L["TT_CAT_STATUS"],  dict = addonTable.EstadoDict },
        { text = L["CAT_SLANG"],   key = "showSlang",       tt = L["TT_CAT_SLANG"],   dict = addonTable.SlangDict },
        { text = L["CAT_ENDGAME"], key = "showEndgame",     tt = L["TT_CAT_ENDGAME"], dict = addonTable.EndgameDict },
    }

    -- A header anchored TOPLEFT occupies 14px downward; a checkbox from
    -- InterfaceOptionsCheckButtonTemplate occupies 26. Five pixels of gap put
    -- the first row of checkboxes 9px INSIDE the heading above it.
    yOffset = yOffset - SECTION_GAP
    for i, info in ipairs(categories) do
        local cb = CreateFrame("CheckButton", "WCT_CB_" .. info.key, panel, "InterfaceOptionsCheckButtonTemplate")
        local col = ((i - 1) % 3)
        local row = math.floor((i - 1) / 3)
        cb:SetPoint("TOPLEFT", 16 + col * 190, yOffset - row * 25)
        -- The count tells the player what the category is for without making
        -- them hover for a tooltip: "Slang (48)" is self-explaining.
        local label = info.text
        local count = CountEntries(info.dict)
        if count > 0 then label = label .. " (" .. count .. ")" end
        _G[cb:GetName() .. "Text"]:SetText(label)
        _G[cb:GetName() .. "Text"]:SetFontObject("GameFontHighlightSmall")
        cb:SetChecked(db.dict.settings[info.key])
        cb:SetScript("OnClick", function(self)
            db.dict.settings[info.key] = self:GetChecked()
            addonTable.RebuildMasterDict()
        end)
        AddTooltip(cb, info.tt)
    end

    local catRows = math.ceil(#categories / 3)
    yOffset = yOffset - catRows * 25 - 10

    -- Separator
    local line2 = panel:CreateTexture(nil, "ARTWORK")
    SetFrameSize(line2, 580, 1)
    line2:SetPoint("TOPLEFT", 16, yOffset)
    Fill(line2, 1, 1, 1, 0.1)

    -- ════════════════════════════════════
    -- SECTION 3: CHANNELS
    -- ════════════════════════════════════
    yOffset = yOffset - 15
    local channelHeader = panel:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    channelHeader:SetPoint("TOPLEFT", 16, yOffset)
    channelHeader:SetText("|cffd597ff" .. L["CH_HEADER"] .. "|r")

    local channelSettings = {
        { text = L["CH_SAY"],          events = { "CHAT_MSG_SAY", "CHAT_MSG_YELL" },                                      tt = L["TT_CH_SAY"] },
        { text = L["CH_PARTY"],        events = { "CHAT_MSG_PARTY", "CHAT_MSG_PARTY_LEADER" },                            tt = L["TT_CH_PARTY"] },
        { text = L["CH_RAID"],         events = { "CHAT_MSG_RAID", "CHAT_MSG_RAID_LEADER", "CHAT_MSG_RAID_WARNING" },     tt = L["TT_CH_RAID"] },
        { text = L["CH_BATTLEGROUND"], events = { "CHAT_MSG_BATTLEGROUND", "CHAT_MSG_BATTLEGROUND_LEADER" },              tt = L["TT_CH_BATTLEGROUND"] },
        { text = L["CH_GUILD"],        events = { "CHAT_MSG_GUILD", "CHAT_MSG_OFFICER" },                                 tt = L["TT_CH_GUILD"] },
        { text = L["CH_WHISPER"],      events = { "CHAT_MSG_WHISPER", "CHAT_MSG_WHISPER_INFORM", "CHAT_MSG_BN_WHISPER" }, tt = L["TT_CH_WHISPER"] },
        { text = L["CH_CHANNEL"],      events = { "CHAT_MSG_CHANNEL" },                                                   tt = L["TT_CH_CHANNEL"] },
        { text = L["CH_EMOTE"],        events = { "CHAT_MSG_EMOTE" },                                                     tt = L["TT_CH_EMOTE"] },
    }

    yOffset = yOffset - SECTION_GAP
    for i, info in ipairs(channelSettings) do
        local cb = CreateFrame("CheckButton", "WCT_CH_CB_" .. i, panel, "InterfaceOptionsCheckButtonTemplate")
        local col = ((i - 1) % 3)
        local row = math.floor((i - 1) / 3)
        cb:SetPoint("TOPLEFT", 16 + col * 190, yOffset - row * 25)
        _G[cb:GetName() .. "Text"]:SetText(info.text)
        _G[cb:GetName() .. "Text"]:SetFontObject("GameFontHighlightSmall")

        local isEnabled = true
        for _, ev in ipairs(info.events) do
            if db.dict.settings.channels[ev] == false then
                isEnabled = false
                break
            end
        end
        cb:SetChecked(isEnabled)

        cb:SetScript("OnClick", function(self)
            local val = self:GetChecked()
            for _, ev in ipairs(info.events) do
                db.dict.settings.channels[ev] = val
            end
        end)
        AddTooltip(cb, info.tt)
    end

    local chRows = math.ceil(#channelSettings / 3)
    yOffset = yOffset - chRows * 25 - 10

    -- Separator
    local line3 = panel:CreateTexture(nil, "ARTWORK")
    SetFrameSize(line3, 580, 1)
    line3:SetPoint("TOPLEFT", 16, yOffset)
    Fill(line3, 1, 1, 1, 0.1)

    -- ════════════════════════════════════
    -- SECTION 4: LANGUAGE SELECTOR
    -- ════════════════════════════════════
    yOffset = yOffset - 15
    local langLabel = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    langLabel:SetPoint("TOPLEFT", 16, yOffset)
    langLabel:SetText("|cffd597ff" .. L["UI_LANG_LABEL"] .. "|r")

    -- The dictionary carries English and Hungarian, so those are the only
    -- targets. A list, not a map: pairs() would put them in a random order.
    local languages = {
        { value = "huHU", name = "Magyar" },
        { value = "enUS", name = "English" },
    }
    local function LanguageName(value)
        for _, language in ipairs(languages) do
            if language.value == value then return language.name end
        end
        return languages[1].name
    end

    local dropdown = CreateFrame("Frame", "WCT_LangDrop", panel, "UIDropDownMenuTemplate")
    dropdown:SetPoint("TOPLEFT", langLabel, "BOTTOMLEFT", -15, -5)
    AddTooltip(dropdown, L["TT_LANG"])

    UIDropDownMenu_Initialize(dropdown, function()
        for _, language in ipairs(languages) do
            local info = UIDropDownMenu_CreateInfo()
            info.text = language.name
            info.value = language.value
            info.func = function(button)
                -- Also the language of this panel and of the slash commands,
                -- which pick it up on the next /reload.
                db.dict.targetLocale = button.value
                UIDropDownMenu_SetSelectedValue(dropdown, button.value)
                UIDropDownMenu_SetText(dropdown, LanguageName(button.value))
                addonTable.RebuildMasterDict()
            end
            info.checked = (db.dict.targetLocale == language.value)
            UIDropDownMenu_AddButton(info)
        end
    end)

    UIDropDownMenu_SetSelectedValue(dropdown, db.dict.targetLocale)
    UIDropDownMenu_SetText(dropdown, LanguageName(db.dict.targetLocale))

    -- Test button
    local testBtn = CreateFrame("Button", "WCT_TestBtn", panel, "UIPanelButtonTemplate")
    testBtn:SetPoint("LEFT", dropdown, "RIGHT", 140, 2)
    SetFrameSize(testBtn, 150, 22)
    testBtn:SetText(L["UI_TEST_BTN"])
    testBtn:SetScript("OnClick", function() addonTable.RunTest() end)
    AddTooltip(testBtn, L["TT_TEST_BTN"])

    yOffset = yOffset - 60

    -- Separator
    local line4 = panel:CreateTexture(nil, "ARTWORK")
    SetFrameSize(line4, 580, 1)
    line4:SetPoint("TOPLEFT", 16, yOffset)
    Fill(line4, 1, 1, 1, 0.1)

    -- ════════════════════════════════════
    -- SECTION 5: COMPANION APP
    -- ════════════════════════════════════
    yOffset = yOffset - 15
    local compHeader = panel:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    compHeader:SetPoint("TOPLEFT", 16, yOffset)
    compHeader:SetText("|cffd597ff" .. L["COMP_HEADER"] .. "|r")

    yOffset = yOffset - 25
    local compCB = CreateFrame("CheckButton", "WCT_CompEnableCB", panel, "InterfaceOptionsCheckButtonTemplate")
    compCB:SetPoint("TOPLEFT", 16, yOffset)
    _G[compCB:GetName() .. "Text"]:SetText(L["COMP_ENABLE"])
    compCB:SetChecked(db.companion.enabled)
    compCB:SetScript("OnClick", function(self)
        db.companion.enabled = self:GetChecked()
        if db.companion.enabled then
            addonTable.StartBufferFlush()
        else
            addonTable.StopBufferFlush()
        end
    end)
    AddTooltip(compCB, L["TT_COMP_ENABLE"])

    -- ════════════════════════════════════
    -- SECTION 6: ABOUT
    -- ════════════════════════════════════
    yOffset = yOffset - 30

    -- Separator
    local line5 = panel:CreateTexture(nil, "ARTWORK")
    SetFrameSize(line5, 580, 1)
    line5:SetPoint("TOPLEFT", 16, yOffset)
    Fill(line5, 1, 1, 1, 0.1)

    yOffset = yOffset - SECTION_GAP
    local aboutHeader = panel:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    aboutHeader:SetPoint("TOPLEFT", 16, yOffset)
    aboutHeader:SetText("|cffd597ff" .. L["ABOUT_HEADER"] .. "|r")

    yOffset = yOffset - 22
    local authors = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
    authors:SetPoint("TOPLEFT", 16, yOffset)
    authors:SetText(L["ABOUT_AUTHORS"])

    yOffset = yOffset - 18
    local dictCredit = panel:CreateFontString(nil, "ARTWORK", "GameFontDisableSmall")
    dictCredit:SetPoint("TOPLEFT", 16, yOffset)
    dictCredit:SetText(L["ABOUT_DICT_CREDIT"])

    yOffset = yOffset - 18
    local license = panel:CreateFontString(nil, "ARTWORK", "GameFontDisableSmall")
    license:SetPoint("TOPLEFT", 16, yOffset)
    license:SetText(L["ABOUT_LICENSE"])

    -- A WoW addon cannot open a browser, and it cannot put text on the
    -- clipboard either. An EditBox the player can click and press Ctrl+C in is
    -- the whole of what the API allows, so that is what the link is.
    local LINKS = {
        { label = "GitHub", url = "https://github.com/Yumash/BabelChat" },
    }
    for index, link in ipairs(LINKS) do
        yOffset = yOffset - 24
        local caption = panel:CreateFontString(nil, "ARTWORK", "GameFontHighlightSmall")
        caption:SetPoint("TOPLEFT", 16, yOffset - 4)
        caption:SetText(link.label .. ":")
        caption:SetWidth(120)
        caption:SetJustifyH("LEFT")

        local box = CreateFrame("EditBox", "WCT_Link" .. index, panel, "InputBoxTemplate")
        box:SetPoint("TOPLEFT", 140, yOffset)
        SetFrameSize(box, 370, 20)
        box:SetAutoFocus(false)
        box:SetText(link.url)
        box:SetCursorPosition(0)
        -- Read-only in effect: any edit snaps back, so a stray keystroke cannot
        -- turn the address into something that no longer goes anywhere.
        box:SetScript("OnTextChanged", function(self, userInput)
            if userInput then
                self:SetText(link.url)
                self:SetCursorPosition(0)
            end
        end)
        box:SetScript("OnEditFocusGained", function(self) self:HighlightText() end)
        box:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
        AddTooltip(box, L["TT_ABOUT_LINK"])
    end

    -- ════════════════════════════════════
    -- REGISTER PANEL
    -- ════════════════════════════════════
    -- 3.3.5: Interface Options > AddOns. The panel's `name` is its entry.
    InterfaceOptions_AddCategory(canvas)
    addonTable.configPanel = canvas
end
