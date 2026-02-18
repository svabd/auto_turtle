import asyncio
import json
import uuid
from typing import Dict, Any, Callable, Awaitable
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# --- THE TURTLE AGENT ---
# This class wraps the WebSocket connection and makes it "awaitable"
class TurtleAgent:
    def __init__(self, turtle_id: str, websocket: WebSocket):
        self.id = turtle_id
        self.websocket = websocket
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def _send_command(self, func: str, args: list = None) -> Any:
        """Internal: Sends JSON to turtle and creates a Future to wait for the reply."""
        request_id = str(uuid.uuid4())
        payload = {
            "id": request_id,
            "func": func,
            "args": args or []
        }

        # Create a "promise" that will be resolved later when the turtle replies
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_requests[request_id] = future

        await self.websocket.send_text(json.dumps(payload))

        # Wait here until the WebSocket handler calls set_result()
        return await future

    # --- HIGH LEVEL API (These return values!) ---
    async def dig(self):
        return await self._send_command("turtle.dig")

    async def forward(self):
        return await self._send_command("turtle.forward")

    async def turnLeft(self):
        return await self._send_command("turtle.turnLeft")

    async def inspect(self):
        # This returns the ACTUAL block data (e.g., {name: "minecraft:stone"})
        return await self._send_command("turtle.inspect")

    def resolve_response(self, response: dict):
        """Called when a JSON packet arrives from the turtle."""
        req_id = response.get("id")
        if req_id in self.pending_requests:
            # Wake up the task that was waiting for this
            self.pending_requests[req_id].set_result(response)
            del self.pending_requests[req_id]

# --- SWARM MANAGER ---
class SwarmManager:
    def __init__(self):
        self.agents: Dict[str, TurtleAgent] = {}

    async def register(self, turtle_id: str, websocket: WebSocket):
        agent = TurtleAgent(turtle_id, websocket)
        self.agents[turtle_id] = agent
        return agent

    def remove(self, turtle_id: str):
        if turtle_id in self.agents:
            del self.agents[turtle_id]

    def get_agent(self, turtle_id: str):
        return self.agents.get(turtle_id)

swarm = SwarmManager()

# --- THE TASK LOGIC (Where the magic happens) ---

# --- ADD THIS TO YOUR PYTHON ROUTES ---

@app.post("/run-sync-task")
async def run_sync():
    t1 = swarm.get_agent("turtle1")
    t2 = swarm.get_agent("turtle2")

    if t1 and t2:
        # We use asyncio.create_task so the web request finishes immediately
        # while the turtles keep working in the background.
        asyncio.create_task(task_synced_dig(t1, t2))
        return {"message": "Sync task started!"}
    return {"message": "Missing turtles!", "t1": bool(t1), "t2": bool(t2)}, 400

async def task_synced_dig(t1: TurtleAgent, t2: TurtleAgent):
    """
    Task: Two turtles dig together.
    We wait for BOTH to finish one step before starting the next.
    """
    print(f"Starting sync dig with {t1.id} and {t2.id}")

    for _ in range(3):
        # Run both forwards in parallel!
        # This sends commands to both immediately, then waits for both replies.
        results = await asyncio.gather(t1.forward(), t2.forward())

        success1 = results[0].get("success")
        success2 = results[1].get("success")

        print(f"Step status: {t1.id}={success1}, {t2.id}={success2}")

        # Logic: If T1 hits a block, ask T2 to inspect its own surroundings
        if not success1:
            print(f"{t1.id} blocked! Asking {t2.id} to check block data...")
            data = await t2.inspect()
            print(f"{t2.id} sees: {data.get('result')}")

async def task_finder(scout: TurtleAgent):
    """
    Task: Scout moves until it finds a specific block type.
    """
    print(f"{scout.id} starts scouting...")
    while True:
        # Ask turtle what is in front
        response = await scout.inspect()
        block_data = response.get("result") # Lua returns {name="minecraft:stone", ...}

        if block_data and block_data.get("name") == "minecraft:diamond_ore":
            print("DIAMOND FOUND! Stopping.")
            break

        # Not found? Move and try again
        await scout.dig()
        await scout.forward()

# --- WEBSOCKET ENDPOINTS ---

@app.websocket("/ws/turtle/{turtle_id}")
async def turtle_endpoint(websocket: WebSocket, turtle_id: str):
    await websocket.accept()
    agent = await swarm.register(turtle_id, websocket)
    print(f"Agent {turtle_id} online.")

    try:
        while True:
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            # Route the response to the specific Future waiting for it
            agent.resolve_response(data)

    except WebSocketDisconnect:
        swarm.remove(turtle_id)
        print(f"Agent {turtle_id} offline.")

@app.get("/")
async def get():
    return HTMLResponse(content=html_content) # Use same HTML as before

# Trigger tasks via simple HTTP (for testing)
@app.get("/start/sync")
async def start_sync_task():
    t1 = swarm.get_agent("turtle1")
    t2 = swarm.get_agent("turtle2")
    if t1 and t2:
        # Fire and forget the task in the background
        asyncio.create_task(task_synced_dig(t1, t2))
        return {"status": "Task started"}
    return {"error": "Need both turtles connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)