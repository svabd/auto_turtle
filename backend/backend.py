import asyncio
import copy
import json
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any

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
    def __init__(self, min_data: TurtleDataMin, agent: TurtleAgent):
        self.min = min_data
        self.agent: TurtleAgent = agent

    def __json__(self):
        return self.min.__json__()

world: Dict[Pos, str] = {}
world_lock = asyncio.Lock()

class TurtleDataMin:
    def __init__(self, pos: Pos, looking: int):
        self.pos: Pos = pos
        self.looking: int = looking

    def __json__(self):
        return {"pos": self.pos.__json__(), "looking": self.looking}

    def print(self):
        return {"pos": self.pos.__json__(), "looking": looking_to_name(self.looking)}

class Pos:
    def __init__(self, x: int, y: int, z: int):
        self.x = x
        self.y = y
        self.z = z

    def __json__(self):
        return {"x": self.x, "y": self.y, "z": self.z}

async def manage_turtle(turtle: str):
    await forward(turtle)
    async with turtles_lock:
        async with world_lock:
            print(json.dumps((await get_min_turtle_form_turtles(turtle)).print()))
            for i in world.values(): print(i)
            for j in world.keys(): print(j.__json__())
            print(len(world.values()))


async def forward(turtle: str) -> bool:
    suc: Dict = (await run("turtle.forward()", turtle))
    if suc["success"]:
        await check(turtle)
        return True
    else:
        return False

async def check(turtle: str):
    for i in range(4):
        pos: Pos = (await get_min_turtle_form_turtles(turtle)).pos
        looking: int = (await get_min_turtle_form_turtles(turtle)).looking
        print(looking_to_name(looking))
        ret: dict = await run("turtle.inspect()", turtle)
        data = ret["data"]["name"]
        print(get_block_form_pos_and_looking(pos, looking).__json__())
        await set_block_form_world(get_block_form_pos_and_looking(pos, looking), data)
        await turn_left(turtle)


async def turn_left(turtle: str):
    await run("turtle.turnLeft()", turtle)
    async with turtles_lock:
        turtles[turtle].min.looking = (turtles[turtle].min.looking - 1) % 4

def get_block_form_pos_and_looking(pos: Pos, looking: int) -> Pos:
    poss: Pos = copy.deepcopy(pos)
    looking_two: int = copy.deepcopy(looking)
    if looking_two == 0:
        poss.z -= 1
    elif looking_two == 1:
        poss.x += 1
    elif looking_two == 2:
        poss.z += 1
    else:
        poss.x -= 1
    return poss

async def run(command: str, turtle: str) -> Any:
    async with turtles_lock:
        it = turtles[turtle].agent.exec(command)
    return await it

async def get_min_turtle_form_turtles(turtle: str) -> TurtleDataMin:
    async with turtles_lock:
        return copy.deepcopy(turtles[turtle].min)

async def set_turtle_pos_form_turtles(turtle_id: str, pos: Pos):
    async with turtles_lock:
        turtles[turtle_id].min.pos = copy.deepcopy(pos)

async def set_turtle_looking_form_turtles(turtle_id: str, looking: str):
    async with turtles_lock:
        turtles[turtle_id].min.looking = copy.deepcopy(looking)

async def get_block_form_world(block_pos: Pos) -> str:
    async with world_lock:
        return copy.deepcopy(world[block_pos])

async def set_block_form_world(block_pos: Pos, block: str):
    async with world_lock:
        world[block_pos] = copy.deepcopy(block)

def looking_to_name(looking: int) -> str:
    if looking == 0:
        return "north"
    elif looking == 1:
        return "east"
    elif looking == 2:
        return "south"
    elif looking == 3:
        return "west"
    else:
        return "AAAAAAAAAAAAAAAAAAAA"

# --- API ENDPOINTS ---

@app.websocket("/ws/turtle/{turtle_id}")
async def turtle_endpoint(websocket: WebSocket, turtle_id: str):
    await websocket.accept()
    agent: TurtleAgent = TurtleAgent(turtle_id, websocket)
    turtle_data = TurtleData(TurtleDataMin(Pos(0,0,0), 0), agent)
    async with turtles_lock:
        turtles[turtle_id] = turtle_data
    print(f"Turtle '{turtle_id}' joined the swarm.")

    asyncio.create_task(manage_turtle(turtle_id))

    try:
        while True:
            # Listen for responses from the turtle
            data = await websocket.receive_json()
            agent.resolve(data)
    except WebSocketDisconnect:
        async with turtles_lock:
            del turtles[turtle_id]
        print(f"Turtle '{turtle_id}' left.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)