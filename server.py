import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

target_socket = None
controller_sockets = []

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
@app.get("/dashboard")
@app.get("/dashboard.html")
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.get("/target")
@app.get("/target_web.html")
async def get_target():
    return FileResponse(os.path.join(BASE_DIR, "target_web.html"))

@app.websocket("/ws/target")
async def target_endpoint(websocket: WebSocket):
    global target_socket
    await websocket.accept()
    target_socket = websocket
    print("[+] Target connected.")
    try:
        while True:
            data = await websocket.receive_text()
            # Relay messages to all controllers (for WebRTC handshake)
            for ctrl in list(controller_sockets):
                try:
                    await ctrl.send_text(data)
                except Exception:
                    pass
    except WebSocketDisconnect:
        target_socket = None
        print("[-] Target disconnected.")

@app.websocket("/ws/controller")
async def controller_endpoint(websocket: WebSocket):
    await websocket.accept()
    controller_sockets.append(websocket)
    print("[*] Controller connected.")
    try:
        while True:
            data = await websocket.receive_text()
            # Relay messages to the target (for WebRTC handshake)
            if target_socket:
                try:
                    await target_socket.send_text(data)
                except Exception:
                    pass
    except WebSocketDisconnect:
        if websocket in controller_sockets:
            controller_sockets.remove(websocket)
        print("[-] Controller disconnected.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
