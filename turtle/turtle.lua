local turtle_id = "turtle1" -- Change this for each turtle
local server_url = "ws://10.0.0.84:8000/ws/turtle/" .. turtle_id

print("Connecting to: " .. server_url)
local ws, err = http.websocket(server_url)

if not ws then
    error("Connection failed: " .. tostring(err))
end

print("Connected! Waiting for Task Objects...")

while true do
    local message = ws.receive()
    if not message then
        print("Connection lost.")
        break
    end

    local data = textutils.unserializeJSON(message)

    if data and data.cmd then
        local reqId = data.id -- Capture the ID from Python
        print("Executing: " .. data.cmd)

        -- load() handles the full command string like "turtle.forward()"
        local func, loadErr = load("return " .. data.cmd)

        local success, actionSuccess, actionData
        if func then
            -- We no longer need table.unpack(args) because
            -- the arguments are already inside the 'data.cmd' string.
            local results = { pcall(func) }
            success = results[1]       -- pcall status
            actionSuccess = results[2] -- turtle result (true/false)
            actionData = results[3]    -- extra data (block info)
        else
            success = false
            actionData = loadErr
        end

        -- Send the response back to Python
        ws.send(textutils.serializeJSON({
            id = reqId,
            success = success,
            result = actionSuccess,
            data = actionData
        }))
    else
        print("Received malformed data.")
    end
end

ws.close()