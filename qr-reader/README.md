# QR Code Reader Station
This project tends to be a prototype of QR Code Reader module for Software Development Practice I
## Contents
1. [Installation](#installation)
2. [Running](#running)

## Installation
Follow these steps to set up the project environment.

### Prerequisites
* Python 3.8+ and `pip`
* Git
* Node.js

### Steps
1. Clone this repository.
```bash
git clone https://github.com/AnMayVaa/QR-Code-Based-Software-Development-Project.git
cd qr-reader
```
2. Install and activate python virtual environment.
   * **Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```
   * **MacOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

```bash
sudo apt install qtbase5-dev
sudo apt-get install -y fonts-noto fonts-noto-unhinted fonts-thai-tlwg
```
3.  Install the required Python packages:
```bash
pip install -r requirements.txt
```

4. Run MQTT Broker:
```bash
node qrscan_pub.js
```

## Running
Use this command
```bash
python main.py
```
Make sure you run the command on the **qr-reader** folder and different terminal from MQTT Broker
