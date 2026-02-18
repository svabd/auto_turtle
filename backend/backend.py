import asyncio
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Dict, List, Any
from pydantic import BaseModel

app = FastAPI()

# --- SWARM CORE ---

class ExcavateTask(BaseModel):
    turtle_ids: List[str]
    depth: int = 5

class TurtleAgent:
    """Represents a single Minecraft Turtle."""
    def __init__(self, turtle_id: str, websocket: WebSocket):
        self.id = turtle_id
        self.websocket = websocket
        self.pending_requests: Dict[str, asyncio.Future] = {}

    async def exec(self, command: str) -> Any:
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending_requests[request_id] = future

        # This 'cmd' key must match 'data.cmd' in the Lua script above
        await self.websocket.send_text(json.dumps({
            "id": request_id,
            "cmd": command
    }))

        # Wait for the response to be 'resolved' by the listener loop
        return await future

    def resolve(self, response: dict):
        """Matches incoming response ID to the waiting future."""
        req_id = response.get("id")
        if req_id in self.pending_requests:
            self.pending_requests[req_id].set_result(response)
            del self.pending_requests[req_id]

class SwarmManager:
    """Manages all connected turtles and task distribution."""
    def __init__(self):
        self.turtles: Dict[str, TurtleAgent] = {}

    def get_turtle(self, turtle_id: str) -> TurtleAgent:
        return self.turtles.get(turtle_id)

swarm = SwarmManager()

# --- DATA DRIVEN TASKS ---

async def task_excavate_chunk(turtle_ids: List[str], depth: int):
    agents = [swarm.get_turtle(tid) for tid in turtle_ids if swarm.get_turtle(tid)]
    if not agents: return

    print(f"Task Started: Excavating with {len(agents)} turtles.")

    for layer in range(depth):
        # Dig and Down (we just care if success is True/False)
        await asyncio.gather(*(a.exec("turtle.digDown()") for a in agents))
        await asyncio.gather(*(a.exec("turtle.down()") for a in agents))

        # Inspect returns the block table in the 'data' field
        inspections = await asyncio.gather(*(a.exec("turtle.inspectDown()") for a in agents))

        for i, report in enumerate(inspections):
            # We look at 'data' now because 'result' is just the boolean True
            block_info = report.get("data")
            block_name = "air"

            if isinstance(block_info, dict):
                block_name = block_info.get("name", "unknown")

            print(f"Layer {layer} | {agents[i].id} reports block: {block_name}")

# --- API ENDPOINTS ---

@app.websocket("/ws/turtle/{turtle_id}")
async def turtle_endpoint(websocket: WebSocket, turtle_id: str):
    await websocket.accept()
    agent = TurtleAgent(turtle_id, websocket)
    swarm.turtles[turtle_id] = agent
    print(f"Turtle '{turtle_id}' joined the swarm.")

    try:
        while True:
            # Listen for responses from the turtle
            data = await websocket.receive_json()
            agent.resolve(data)
    except WebSocketDisconnect:
        del swarm.turtles[turtle_id]
        print(f"Turtle '{turtle_id}' left.")

@app.post("/tasks/excavate")
async def trigger_excavate(task: ExcavateTask): # Use the model here
    # Access data via task.turtle_ids and task.depth
    asyncio.create_task(task_excavate_chunk(task.turtle_ids, task.depth))
    return {"status": "Task dispatched to swarm", "turtles": task.turtle_ids}

# --- DASHBOARD ---

@app.get("/")
async def get():
    return HTMLResponse("""
    <html>
        <head><title>Swarm Control</title></head>
        <body style="font-family:sans-serif; background:#121212; color:white; padding:20px;">
            <h1>Turtle Swarm Dashboard</h1>
            <div id="status">Waiting for turtles...</div>
            <hr>
            <button onclick="runTask()" style="padding:10px; background:green; color:white;">Start 2-Turtle Sync Dig</button>
            <script>
                async function runTask() {
                    const res = await fetch('/tasks/excavate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({turtle_ids: ['turtle1', 'turtle2'], depth: 3})
                    });
                    alert("Task Dispatched!");
                }
            </script>
        </body>
    </html>
    """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)