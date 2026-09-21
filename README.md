# 🚨 112 Emergency SOS & CAD Tactical Intelligence Platform (ERSS 112)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688.svg)](https://fastapi.tiangolo.com)
[![WebRTC](https://img.shields.io/badge/Streaming-WebRTC%20Full%20Duplex-3b82f6.svg)](https://webrtc.org/)
[![Android](https://img.shields.io/badge/Mobile-Native%20Android%20%2B%20PWA-3DDC84.svg)](https://developer.android.com)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose-2496ED.svg)](https://www.docker.com)

> **Next-Generation 112 (NG-112 / Next-Gen 911) Public Safety & Emergency Response Platform**  
> Designed for State Police Control Rooms (ERSS 112), Ambulance Services (108), Fire & Disaster Management (101), and Smart City Integrated Command & Control Centers (ICCC).

---

## 🌟 Key Highlights & Next-Gen Innovations

### 1. 🚗 4-Layer Auto-Crash & Severe Impact Detection Engine
* **High-G Impact Telemetry:** Real-time on-device accelerometer monitoring detecting severe collisions (>18G / 176 m/s²).
* **Pre-Impact Speed Verification:** Distinguishes between accidental phone drops and actual vehicular collisions by verifying pre-impact GPS speed (>25 km/h).
* **10-Second Acoustic Grace Period:** Emits a loud emergency siren and provides a full-screen countdown modal with a 1-tap **`[✅ I AM OK - CANCEL]`** button to prevent false alarms.
* **Auto-Dispatch for Unconscious Victims:** If the victim is unresponsive when the timer reaches zero, the system automatically transmits live GPS coordinates and crash force telemetry to 112 dispatchers.

### 2. 🏢 3D Indoor Barometric Floor & Elevation Estimator
* **Vertical Z-Axis Tracking:** Hypsometric calculation using device atmospheric pressure sensors (`Barometer` API) with sea-level calibration to estimate exact building story/floor level (e.g. `🏢 4th Floor (±3m)`).
* **Hybrid GPS Altitude Fallback:** Automatically switches to high-accuracy GPS altitude delta calculation on devices lacking barometric sensors.

### 3. 🔘 Physical 5-Click Hardware Power-Key Trigger (Android Native)
* **Covert Activation:** Rapidly clicking the physical power button 5 times within 3.5 seconds launches a background Android Foreground Service that begins streaming location and audio even if the screen is locked or in a pocket.

### 4. 🎙️ Real-Time Audio Intelligence & Threat NLP
* **Ambient Speech-to-Text:** Live transcription on the victim device streamed over encrypted WebSockets to the dispatcher console.
* **Multilingual Danger Keyword Spotter:** Scans conversations for distress and threat terminology (*"gun"*, *"knife"*, *"fire"*, *"accident"*, *"blood"*, *"chaku"*, *"goli"*, *"bachao"*), instantly elevating incident priority.

### 5. 📄 Court-Admissible Forensic PCR Dossier Generator
* **1-Click Forensic Dossier:** Generates an official state-format Police Incident Report including:
  * Unique Incident Case ID (`CAD-2026-XXXXX`).
  * Citizen terminal ID, reverse-geocoded street address, and high-precision GPS coordinates.
  * 3D Building Floor elevation and Crash G-Force telemetry.
  * Time-stamped verbal speech transcript and threat keyword tags.
  * Captured Front & Rear camera evidence snapshots.
  * **Cryptographic SHA-256 Chain-of-Custody Checksum** for legal and judicial admissibility.
  * Dispatcher, field officer, and magistrate signature blocks.

### 6. 📱 Disguised Stealth Calculator Mode
* **Dual Disguise Interface:** Functional arithmetic calculator interface to protect victims under surveillance or hostage situations.
* **Secret Unlock Sequence:** Entering `112=` or triple-tapping the header restores the full emergency HUD.

### 7. 📡 Offline Blackbox GPS Caching & Zero-Network 1-Tap SMS Fallback
* **Local Trail Buffering:** Stores GPS breadcrumbs in `localStorage` when network connectivity is lost.
* **1-Tap Direct SMS Gateway:** Automatically offers a pre-formatted SMS to `112` containing exact Google Maps coordinates over standard 2G GSM cellular networks.
* **Automatic Cloud Sync:** Flushes the offline blackbox trail to central dispatch the moment data connectivity resumes.

---

## 🏗️ Architecture Overview

```
                        ┌────────────────────────────────────────────────────────┐
                        │              Victim Client Terminal                    │
                        │    (Android Native Service / Progressive Web App)       │
                        └──────────┬───────────────────────────────┬─────────────┘
                                   │                               │
                      WebRTC Video │ & Ambient Mic                 │ WebSocket Telemetry
                      (DTLS-SRTP)  │                               │ (GPS, 3D Floor, Crash, NLP)
                                   ▼                               ▼
                        ┌────────────────────────────────────────────────────────┐
                        │        FastAPI Central Dispatch & Signaling Server     │
                        │                (Python 3.10+ / Uvicorn)                │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                                                   ▼
                        ┌────────────────────────────────────────────────────────┐
                        │            112 CAD Command Dispatcher Dashboard        │
                        │     - HD Leaflet / Google Maps Satellite Tracking       │
                        │     - Dual Camera Live Surveillance (Front / Rear)      │
                        │     - Multi-Agency CAD Fleet Dispatch (112, 108, 101)  │
                        │     - Court-Admissible Forensic PCR Dossier Export      │
                        └────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start & Deployment

### Method 1: Docker (Recommended for Police / Government Servers)

Run the entire platform with a single command:

```bash
docker compose up -d --build
```

Access the services:
* **CAD Dispatcher Dashboard:** `http://localhost:8000/dashboard`
* **Victim SOS Interface:** `http://localhost:8000/target`
* **Android APK Direct Download:** `http://localhost:8000/download-apk`

---

### Method 2: Local Python Environment

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch Central Server:**
   ```bash
   python server.py
   ```
   Or:
   ```bash
   uvicorn server.py:app --host 0.0.0.0 --port 8000 --reload
   ```

---

### Method 3: Native Android App Compilation

1. Open the `/android` directory in Android Studio or compile using Gradle:
   ```bash
   cd android
   ./gradlew assembleDebug
   ```
2. The output APK will be generated at:
   `android/app/build/outputs/apk/debug/app-debug.apk`

---

## 🔒 Security & Privacy Architecture

* **Zero Pre-SOS Transmission:** Camera, microphone, and location tracking remain strictly dormant in Armed Standby mode until explicitly triggered by the user or confirmed high-G impact.
* **Encrypted WebRTC Feeds:** Video and audio streams are encrypted end-to-end using standard DTLS-SRTP.
* **Data Sovereignty:** Entire backend is self-hostable with zero external cloud dependencies.

---

## 📄 License

This project is licensed under the MIT License.