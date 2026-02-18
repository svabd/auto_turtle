local turtle_id = "turtle1" -- Change to turtle2 for the second one
local url = "ws://192.168.1.XX:8000/ws/turtle/" .. turtle_id
local ws = http.websocket(url)

while true do
    local msg = ws.receive()
    if not msg then break end

    local request = textutils.unserializeJSON(msg)
    local funcName = request.func
    local args = request.args
    local reqId = request.id

    -- Dynamically call the function (e.g., turtle.dig)
    -- We map string "turtle.dig" to the actual function _G["turtle"]["dig"]
    local parts = {}
    for part in string.gmatch(funcName, "[^.]+") do
        table.insert(parts, part)
    end

    local func = _G
    for _, part in ipairs(parts) do
        if func then func = func[part] end
    end

    if type(func) == "function" then
        -- Call function with unpacked arguments
        local status, result = pcall(func, table.unpack(args))

        -- Send back result WITH the Request ID
        ws.send(textutils.serializeJSON({
            id = reqId,
            success = status,
            result = result
        }))
    else
        ws.send(textutils.serializeJSON({
            id = reqId,
            success = false,
            error = "Function not found"
        }))
    end
end