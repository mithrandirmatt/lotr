from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

from server.engine.schema import GameState

app = FastAPI(title="LOTR Host-Referee")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.websocket("/ws/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str):
    await websocket.accept()
    await websocket.send_text("connected")
    try:
        while True:
            data = await websocket.receive_text()
            # Echo for now; real protocol will validate actions
            await websocket.send_text(f"echo:{data}")
    except Exception:
        await websocket.close()
