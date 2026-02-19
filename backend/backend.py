import asyncio
import json
import uuid
from numbers import Number

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any

app = FastAPI()

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

turtles: Dict[str, TurtleData] = {}
turtles_lock = asyncio.Lock()

class TurtleData:
    def __init__(self, pos: List[Number], looking: str, agent: TurtleAgent):
        self.pos: List[Number] = pos
        self.looking: str = looking
        self.agent: TurtleAgent = agent

world: Dict[List[Number], str] = Dict()
world_lock = asyncio.Lock()

async def manage_turtle(turtle: str):
    pass

# --- API ENDPOINTS ---

@app.websocket("/ws/turtle/{turtle_id}")
async def turtle_endpoint(websocket: WebSocket, turtle_id: str):
    await websocket.accept()
    agent: TurtleAgent = TurtleAgent(turtle_id, websocket)
    turtles[turtle_id].agent = agent
    print(f"Turtle '{turtle_id}' joined the swarm.")

    asyncio.create_task(manage_turtle(turtle_id))

    try:
        while True:
            # Listen for responses from the turtle
            data = await websocket.receive_json()
            agent.resolve(data)
    except WebSocketDisconnect:
        del turtles[turtle_id]
        print(f"Turtle '{turtle_id}' left.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)