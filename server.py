import os
import uuid
import json
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

# Store multiple targets: {target_id: websocket}
active_targets: dict[str, WebSocket] = {}
controller_sockets: set[WebSocket] = set()

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
    await websocket.accept()
    target_id = uuid.uuid4().hex[:8]
    active_targets[target_id] = websocket
    print(f"[+] Target connected: {target_id}")

    # Send assigned target ID back to the target client
    await websocket.send_text(json.dumps({"type": "init", "targetId": target_id}))

    # Notify all active controllers immediately
    join_notification = json.dumps({"type": "target_joined", "targetId": target_id})
    for ctrl in list(controller_sockets):
        try:
            await ctrl.send_text(join_notification)
        except Exception:
            pass

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            msg["targetId"] = target_id
            payload = json.dumps(msg)

            # Relay signaling messages to all connected controllers
            for ctrl in list(controller_sockets):
                try:
                    await ctrl.send_text(payload)
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        active_targets.pop(target_id, None)
        print(f"[-] Target disconnected: {target_id}")
        leave_notification = json.dumps({"type": "target_left", "targetId": target_id})
        for ctrl in list(controller_sockets):
            try:
                await ctrl.send_text(leave_notification)
            except Exception:
                pass

@app.websocket("/ws/controller")
async def controller_endpoint(websocket: WebSocket):
    await websocket.accept()
    controller_sockets.add(websocket)
    print("[*] Controller connected.")

    # Send current active target list to new controller
    initial_targets = json.dumps({
        "type": "active_targets",
        "targets": list(active_targets.keys())
    })
    await websocket.send_text(initial_targets)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            target_id = msg.get("targetId")
            # Forward signaling to the specific target
            if target_id and target_id in active_targets:
                target_ws = active_targets[target_id]
                try:
                    await target_ws.send_text(json.dumps(msg))
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    finally:
        controller_sockets.discard(websocket)
        print("[-] Controller disconnected.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

