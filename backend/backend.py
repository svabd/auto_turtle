from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json

app = FastAPI()

# --- THE STOREFRONT (HTML UI) ---
html_content = """
<!DOCTYPE html>
<html>
    <head>
        <title>Turtle Control</title>
        <style>
            body { font-family: sans-serif; background: #222; color: #fff; text-align: center; }
            .btn-group { margin: 20px; }
            button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #444; color: white; border: 1px solid #666; }
            button:hover { background: #666; }
            #log { background: #000; color: #0f0; padding: 10px; height: 200px; overflow-y: scroll; text-align: left; margin: 20px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🐢 Turtle Command Center</h1>
        <div>
            <label>Turtle ID:</label>
            <input type="text" id="tId" value="turtle1">
        </div>
        <div class="btn-group">
            <button onclick="send('turtle.forward()')">Forward</button>
            <button onclick="send('turtle.back()')">Back</button><br><br>
            <button onclick="send('turtle.turnLeft()')">Turn Left</button>
            <button onclick="send('turtle.turnRight()')">Turn Right</button><br><br>
            <button onclick="send('turtle.dig()')">Dig Down</button>
        </div>
        <div id="log"></div>

        <script>
            // Connect to the dashboard websocket
            const ws = new WebSocket("ws://localhost:8000/ws/dashboard");
            const logBox = document.getElementById('log');

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                logBox.innerHTML += `<div><strong>${data.from}:</strong> ${data.msg}</div>`;
                logBox.scrollTop = logBox.scrollHeight;
            };

            function send(command) {
                const id = document.getElementById('tId').value;
                ws.send(JSON.stringify({target: id, cmd: command}));
            }
        </script>
    </body>
</html>
"""

# --- THE BACKEND LOGIC ---
class ConnectionManager:
    def __init__(self):
        self.turtles: dict[str, WebSocket] = {}
        self.dashboards: list[WebSocket] = []

    async def connect_turtle(self, turtle_id: str, websocket: WebSocket):
        await websocket.accept()
        self.turtles[turtle_id] = websocket
        print(f"Turtle {turtle_id} connected.")

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboards.append(websocket)

    async def send_to_turtle(self, turtle_id: str, command: str):
        if turtle_id in self.turtles:
            await self.turtles[turtle_id].send_text(command)

manager = ConnectionManager()

@app.get("/")
async def get():
    return HTMLResponse(content=html_content)

@app.websocket("/ws/turtle/{turtle_id}")
async def turtle_endpoint(websocket: WebSocket, turtle_id: str):
    await manager.connect_turtle(turtle_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Forward turtle response to all dashboards
            for dash in manager.dashboards:
                await dash.send_text(json.dumps({"from": turtle_id, "msg": data}))
    except WebSocketDisconnect:
        if turtle_id in manager.turtles:
            del manager.turtles[turtle_id]

@app.websocket("/ws/dashboard")
async def dashboard_endpoint(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            await manager.send_to_turtle(payload["target"], payload["cmd"])
    except WebSocketDisconnect:
        manager.dashboards.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)