local turtle_id = "turtle1"
local url = "ws://10.0.0.84:8000/ws/turtle/" .. turtle_id

print("Connecting to: " .. url)
local ws, err = http.websocket(url)

if not ws then
    error("Could not connect: " .. tostring(err))
end

print("Connected as " .. turtle_id)

while true do
    local cmd = ws.receive()
    if not cmd then break end

    print("Executing: " .. cmd)

    -- Execute the string as Lua code
    local func, loadErr = load("return " .. cmd)
    if func then
        local success, result = pcall(func)
        ws.send(textutils.serializeJSON({
            success = success,
            result = result
        }))
    else
        ws.send(textutils.serializeJSON({
            success = false,
            error = loadErr
        }))
    end
end
ws.close()