-- Timer.lua — C_Timer.After / C_Timer.NewTicker for the 3.3.5 client
--
-- C_Timer arrived in patch 6.0. The WotLK client has nothing like it, so the
-- addon carries its own, built on one frame's OnUpdate. It lives on the addon
-- table rather than in the global namespace: other 3.3.5 addons ship their own
-- C_Timer shims with their own ideas about catching up, and the companion
-- buffer's 0.25 s flush and 2 s idle pulse must not depend on whichever of them
-- loaded first.
--
-- Semantics, matching the retail API the rest of the addon was written for:
--   C_Timer.After(delay, fn)          fn() once, `delay` seconds from now
--   C_Timer.NewTicker(interval, fn)   fn(ticker) every `interval` seconds,
--                                     first call one interval from now;
--                                     returns an object with :Cancel()
--
-- A ticker that falls behind (a frame longer than its interval, a loading
-- screen) fires ONCE on the next frame and then resumes its cadence. It never
-- bursts to catch up: four flushes in one frame would be four identical
-- rebuilds of the buffer, which buys the companion nothing.

local ADDON_NAME, addonTable = ...

local C_Timer = {}
addonTable.C_Timer = C_Timer

local active = {}            -- every live timer, in creation order

-- Must be SHOWN to receive OnUpdate — a hidden frame gets none — but it has no
-- size and no textures, so there is nothing on screen. It is hidden only while
-- there are no timers, which is when there is nothing to do.
local driver = CreateFrame("Frame")
driver:Hide()

local function Report(err)
    local handler = geterrorhandler and geterrorhandler()
    if handler then handler(err) end
end

local function OnUpdate(self, elapsed)
    -- Snapshot the count: a callback may add a timer, and a new timer must not
    -- be advanced by the frame time that elapsed before it existed.
    local count = #active
    for index = 1, count do
        local timer = active[index]
        if not timer.cancelled then
            timer.remaining = timer.remaining - elapsed
            if timer.remaining <= 0 then
                if timer.interval then
                    -- Re-arm BEFORE calling, so an error in the callback cannot
                    -- leave the ticker due on every frame from now on.
                    timer.remaining = timer.remaining + timer.interval
                    if timer.remaining <= 0 then
                        timer.remaining = timer.interval
                    end
                else
                    timer.cancelled = true
                end
                local ok, err = pcall(timer.callback, timer.handle)
                if not ok then Report(err) end
            end
        end
    end

    -- Compact: drop finished and cancelled timers, keep the order of the rest.
    local kept = 0
    for index = 1, #active do
        local timer = active[index]
        active[index] = nil
        if not timer.cancelled then
            kept = kept + 1
            active[kept] = timer
        end
    end
    if kept == 0 then
        self:Hide()
    end
end

driver:SetScript("OnUpdate", OnUpdate)

local function Schedule(delay, callback, interval)
    local timer = {
        remaining = delay,
        interval = interval,
        callback = callback,
        cancelled = false,
    }
    local handle = {}
    function handle:Cancel()
        timer.cancelled = true
    end
    function handle:IsCancelled()
        return timer.cancelled
    end
    timer.handle = handle
    active[#active + 1] = timer
    driver:Show()
    return handle
end

function C_Timer.After(delay, callback)
    Schedule(delay, callback, nil)
end

function C_Timer.NewTicker(interval, callback)
    return Schedule(interval, callback, interval)
end

-- How many timers are live. For the status command and the tests.
function C_Timer.ActiveCount()
    local live = 0
    for index = 1, #active do
        if not active[index].cancelled then live = live + 1 end
    end
    return live
end
