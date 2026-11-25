from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="pulso-chat", version="0.1.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("[pulso-chat] Conectado ao servidor WebSocket!")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Eco do servidor: {data}")
    except WebSocketDisconnect:
        print("[pulso-chat] Cliente desconectado.")