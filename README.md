# Project: QR-Engage Event Management System

This repository contains the complete source code for the **QR-Engage** project, a fault-tolerant, real-time QR code tracking and registration system designed for the university open house.

The system is built on a modern, decoupled architecture featuring a Node.js backend with a local-first SQLite database, a Supabase cloud database for synchronization, and two separate React (Vite) applications for administrators and registration staff.

---

## 🏛️ System Architecture

The core of this project is its **fault-tolerant, local-first architecture**. This design ensures that all participant check-ins and registrations are captured 100% of the time, even if the event's internet connection fails or the cloud database is unavailable.



### Data Flow:
1.  **Capture:** A QR code (from the `Generate Station` or `Check in/out Station`) is scanned. The data (`token`, `location`, `check`, `epoch`) is published as a JSON payload to the central **Local MQTT Broker** (`openhouse/qrscan` topic).
2.  **Local Save (Instant):** The **`listener.js`** service, running 24/7 on the server, receives the MQTT message and **immediately saves it to the local `local_backup.db` (SQLite) file**. This step is instant and does not require an internet connection.
3.  **Cloud Sync (Automatic):** The **`sync.js`** service runs in the background, continuously checking the local database for unsynced records. It uploads these records in batches to the **Supabase (PostgreSQL)** cloud database.
4.  **Visualize & Register:** The **`dashboard-app`** and **`registration-app`** both read data primarily from the **Supabase** cloud to get the most up-to-date, real-time information.

---

## 🧩 System Modules & Event Stations

The project is divided into the following components and responsibilities:

### 1. Network
* **Folder:** `backend-services/`
* **Managed by:** **Nathaphat Tesviruch**

**[--- Tonnum: Please add your detailed description of this module here. ---]**

### 2. QR Code Generate Station
* **Folder:** (Please specify folder, e.g., `qr-generator/`)
* **Managed by:** **Nakharin Boonkorkua**

This station is the starting point for all participants. Its primary role is to provide each visitor with a unique QR code containing their `token`.

*(This module is responsible for the pre-event setup of generating and distributing the unique QR codes to participants.)*

**[--- Klong: Please add your detailed description of this module here. ---]**
* *(e.g., Describe the technology used to generate the codes.)*
* *(e.g., What data is embedded in the QR code? Just the token?)*
* *(e.g., How are the codes distributed to visitors? Printed? Emailed?)*

### 3. Check in/out Station
* **Folder:** (Please specify folder, e.g., `check-in-app/`)
* **Managed by:** **Noppanart Pisawongnukulkij**

This module consists of the scanners and applications used by staff at the various activity booths to track participant progress.
Its primary function is to publish MQTT messages with `check: 1` (Check-in) and `check: 0` (Check-out) payloads.

**[--- Nemo: Please add your detailed description of this module here. ---]**
* *(e.g., What hardware is used? Mobile phones? Laptops with scanners?)*
* *(e.g., Is it a web app? A mobile app? What technology is it built with?)*
* *(e.g., Describe the user interface for staff at the station.)*

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

## 🚀 How to Run Admin Dashboard & Registration App

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
