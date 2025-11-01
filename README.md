# Project: QR-Engage Event Management System

This repository contains the complete source code for the **QR-Engage** project, a fault-tolerant, real-time QR code tracking and registration system designed for the university open house.

The system is built on a modern, decoupled architecture featuring a Node.js backend with a local-first SQLite database, a Supabase cloud database for synchronization, and two separate React (Vite) applications for administrators and registration staff.

---

## System Architecture

The core of this project is its **fault-tolerant, local-first architecture**. This design ensures that all participant check-ins and registrations are captured 100% of the time, even if the event's internet connection fails or the cloud database is unavailable.



### Data Flow:
1.  **Capture:** A QR code (from the `Generate Station` or `Check in/out Station`) is scanned. The data (`token`, `location`, `check`, `epoch`) is published as a JSON payload to the central **Local MQTT Broker** (`openhouse/qrscan` topic).
2.  **Local Save (Instant):** The **`listener.js`** service, running 24/7 on the server, receives the MQTT message and **immediately saves it to the local `local_backup.db` (SQLite) file**. This step is instant and does not require an internet connection.
3.  **Cloud Sync (Automatic):** The **`sync.js`** service runs in the background, continuously checking the local database for unsynced records. It uploads these records in batches to the **Supabase (PostgreSQL)** cloud database.
4.  **Visualize & Register:** The **`dashboard-app`** and **`registration-app`** both read data primarily from the **Supabase** cloud to get the most up-to-date, real-time information.

---

## System Modules & Event Stations

The project is divided into the following components and responsibilities:

### 1. Network
* **Managed by:** **Nathaphat Tesviruch**

In our network system, communication operates through an open-source MQTT server, which we run as a local server within the department’s network. The communication protocol code is distributed across each module of the system. You can refer to the README under the section “How to Run Network System” for instructions on how to run the server.

If you plan to use our system, please remember to update your machine’s IP address in each file within every module.

### 2. QR Code Generate Station
* **Folder:** `Qr Code Generate Station/`
* **Managed by:** **Nakharin Boonkorkua**

This station is the starting point for all participants. Its primary role is to provide each visitor with a unique QR code containing their `token`.

*(This module is responsible for the pre-event setup of generating and distributing the unique QR codes to participants.)*

Detailed Module Description — QR Code Generate Station

**What it is?**

A simple station that creates scannable QR images for the event. It takes the event’s internal token string and turns it into a clean, high-contrast QR image that’s ready for print or screen display (no personal data inside the code).

**Tech overview**
- Runtime / Platform: Python 3.x (works on Windows/Raspberry Pi).
- QR generation:
    - qrcode for quick PNG output (auto version/box size, ECC configurable), or
    - segno when SVG/vector output is needed.
- Image handling: Pillow for placing margins (quiet zone), resizing to print-friendly DPI, and optional overlay of a small center logo.
- Batch/automation (if provided in scripts): Basic CLI using argparse for bulk generation from a simple list; outputs PNG (and optionally SVG/PDF sheets if enabled).
- GUI (optional KIOS flavor): A minimal PyQt-based screen to preview the QR and export as PNG—kept lightweight for kiosk usage; no camera required in this station.

**AI usage (optional enhancement)**
- Stylized logo/mascot for the QR center: local paint_model (AnimeGAN/Cartoon-style) can transform a supplied logo/avatar before overlaying it into the QR center. This is purely cosmetic; the QR content remains the same.
    - Guardrails: keep overlay ≤ ~15% of QR area and bump error correction to H to maintain scanability.
    - Tooling: paint_model → Pillow compose → export PNG.

**Defaults & conventions**
- QR appearance: black on white, quiet zone ≥ 4 modules, size ~320–512 px for screens or 30–35 mm on print.
- Content policy: encode only the event token (no PII).
- Artifacts: per-user PNG files; optional PDF badge sheets if the PDF helper is present.

**Where it fits**
- This station runs before the event to produce QR images. Other stations (scanner, register, dashboard) just read/verify the token that’s encoded here.

### 3. Check in/out Station
* **Folder:** `qr-reader/`
* **Managed by:** **Noppanart Pisawongnukulkij**

This module consists of the scanners and applications used by staff at the various activity booths to track participant progress.
Its primary function is to publish MQTT messages with `check: 1` (Check-in) and `check: 0` (Check-out) payloads.

These are two variants of QR Code Reader/Scanner.

1.  **Webcam Variant**: Read a participant's QR Code with a webcam.
2. **2D Barcode Reader**: Read a participant's QR Code with a 2D Barcode Reader.

Both variants' features

* **Validation**: Check in/out Station will only able to read a specific format of QR Code. 
* **Auto and Manual Check in/out toggle**: Staff can force to manually toggle status to a participant's QR Code in some situations.
* **Outcome Display**: Participants can see a status of their QR Code on mini TFT screen which is sent via Serial.
* **Log**: After reading participants' QR Code.
Their token will be written on log file (token, location, status, epoch timestamp).
* **MQTT Publishing**: Log file data will be published on topic `openhouse/qrscan` by `qrscan_pub.js`.


### 4. Register Station
* **Folder:** `registration-app/`
* **Managed by:** **Pitak Patumwan**

This is a dedicated React (Vite) web application for staff at the final prize/registration station.
* **Multi-Modal Input:** Allows staff to find a participant's record in three ways:
    1.  Typing the token ID (with an autocomplete suggestion list).
    2.  Scanning the QR code with the device's camera.
    3.  Direct input from a USB barcode scanner (emulating a keyboard).
* **Eligibility Check:** The app automatically queries the Supabase database to verify that the participant has completed all required stations (e.g., "3 of 3 stations completed").
* **Registration Form:** If eligible, staff are presented with a form to enter the participant's details (Name, Age, School, etc.).
* **MQTT Publishing:** Submitting the form publishes a final `eventType: 'register'` payload to the MQTT broker, which is then captured by `listener.js` and saved to the database.

### 5. Admin Dashboard
* **Folder:** `dashboard-app/`
* **Managed by:** **Pitak Patumwan**

This is a real-time React (Vite) web application for event organizers to monitor the entire event.
* **Live Statistics:** Displays KPI cards for "Total Participants," "Completed," and "Registered."
* **Real-time Occupancy:** Shows a live bar chart of how many people are currently checked into each station.
* **Participant Tracking:** Features a searchable and filterable table of all participants and their progress.
* **Detailed Drill-Down:** Organizers can click on any participant or station to open a modal window with detailed information, such as a full history of check-ins/outs for a specific person.

### 6. Backend Services
* **Folder:** `backend-services/`
* **Managed by:** **Pitak Patumwan**

This component is the "brain" of the entire system, running on the central on-premise server (Raspberry Pi).
* **`listener.js`:** The primary data capture service. It listens to the MQTT topic and uses `better-sqlite3` to write all incoming data to the local SQLite database instantly.
* **`sync_local_to_supabase.js`:** The synchronization service. It automatically pushes new data from the local SQLite database to the Supabase cloud.
* **`api_server.js`:** The emergency fallback API server. It is run only if Supabase fails, allowing the dashboard to read data from the local backup.

---

## How to Run Admin Dashboard & Registration App

To run the complete system, you must start all components.

### 1. Run the Backend Services (On Server)
These services must be running for the system to work.
```bash
# In Terminal 1: Run the listener
cd backend-services
node listener.js

# In Terminal 2: Run the sync service
cd backend-services
node sync_local_to_supabase.js
```

### 2. Run the Frontend Applications (On Staff/Admin Machines)
```bash
# In Terminal 3: Run the Admin Dashboard
cd dashboard-app
npm run dev

# In Terminal 4: Run the Registration App
cd registration-app
npm run dev
```

### 3. Run the Event Stations
* Start the Check in/out Station application.
* Begin scanning QR codes. Data should now flow through the entire system.

---

## How to Run Network System

### 1. Install mosquitto
Need a Eclipse Mosquitto to implements the MQTT protocol [ https://mosquitto.org/download/ ]

### 2. Setup the config file
in window go to "C:\Program Files\mosquitto\mosquitto.conf"

in linux go to "/etc/mosquitto/mosquitto.conf"

add this config to "mosquitto.conf" file
```bash
# Broker
listener 8883 0.0.0.0
protocol mqtt
# cafile /path/to/ca.crt
# certfile /path/to/server.crt
# keyfile /path/to/server.key
# require_certificate true

# WebSocket
listener 8081 0.0.0.0
protocol websockets
# cafile /path/to/ca.crt
# certfile /path/to/server.crt
# keyfile /path/to/server.key
# require_certificate true

# No login required
allow_anonymous true
```

### 3. Run MQTT Server
in window
```bash
cd "C:\Program Files\mosquitto\"
mosquitto -c "C:\Program Files\mosquitto\mosquitto.conf" -v
```
in linux
```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
sudo systemctl status mosquitto
# if not work you can run this command
mosquitto -c /etc/mosquitto/mosquitto.conf -v
```

### 4. Stop MQTT Server
in window
```bash
net stop mosquitto
```
in linux
```bash
sudo systemctl stop mosquitto
```

### 5. Check port & kill process
*server port* broker : 8883 | web sockert : 8081

in window
```bash
netstat -ano | findstr *server port*
taskkill /PID *your port* /F
```
in linux
```bash
sudo netstat -tulnp | grep *server port*
sudo kill -9 *your port*
```

### 6. Setup firewall (if your can run mqtt server but it not working)
*server port* broker : 8883 | web sockert : 8081

in window use this command and stop firewall in window setting
```bash
New-NetFirewallRule -DisplayName "Mosquitto *server port*" -Direction Inbound -LocalPort *server port* -Protocol TCP -Action Allow
```
in linux
```bash
sudo ufw allow *server port*/tcp
sudo ufw reload
```
