# Fingerprint-Based Anti-Double-Voting System

> Master's thesis — University of Belgrade, School of Electrical Engineering  
> Author: Aleksandar Petoš (3024/2023)  
> Supervisor: Prof. Dr Vladimir Rajović

A proof-of-concept biometric voter verification system designed to prevent multiple voting across physically separated polling stations. Voters are identified in real time using fingerprint recognition; the central server rejects any duplicate attempt instantly.

---

## Overview

Traditional paper-based voting processes have no reliable way to detect if a voter attempts to cast a ballot at more than one polling station. This system addresses that gap by using fingerprint biometrics as the unique voter identifier, without storing any personally identifiable information beyond the biometric template itself.

---

## Architecture

```
┌─────────────────────┐        HTTP/JSON         ┌──────────────────────────┐
│  Polling Station     │ ─────────────────────▶  │     Central Server        │
│                      │                          │                           │
│  AS608 sensor        │                          │  Python (REST API)        │
│     │                │                          │  Java + SourceAFIS        │
│  ESP32-WROOM         │ ◀─────────────────────  │   (template matching)      │
│  (WiFi transport)    │    verified / rejected   │  Voter registry (DB)      │
└─────────────────────┘                          └──────────────────────────┘
```

Multiple polling stations connect to one server. Each fingerprint scan is matched against all registered templates; a positive match from a voter who has already voted triggers an alert.

---

## Hardware

| Component | Role |
|-----------|------|
| ESP32-WROOM | WiFi-enabled microcontroller, runs the polling station client |
| AS608 optical sensor | Captures and delivers a 256-byte fingerprint image |

---

## Software

| Component | Stack |
|-----------|-------|
| Embedded firmware | C/C++ (Arduino/ESP-IDF) |
| REST API server | Python (Flask) |
| Biometric matching | Java, [SourceAFIS](https://sourceafis.machinezoo.com/) open-source library |
| Template storage | Server-side DB (SQLite / PostgreSQL) |

---

## Biometric Pipeline

1. **Image acquisition** — AS608 captures a grayscale fingerprint image
2. **Segmentation** — isolate the ridge region from background
3. **Orientation estimation** — compute local ridge direction field
4. **Enhancement** — Gabor filtering to sharpen ridges
5. **Binarization** — convert to black/white ridge map
6. **Skeletonization** — thin ridges to single-pixel width
7. **Minutiae extraction** — detect ridge endings and bifurcations
8. **Template creation** — serialize to SourceAFIS ProbeTemplate format
9. **1:N matching** — compare probe against all registered templates on server

---

## Evaluation

Tested offline against the **FVC2002** benchmark dataset and on a physical prototype with real users.

| Metric | Result |
|--------|--------|
| FAR (False Accept Rate) | < 0.1% |
| FRR (False Reject Rate) | < 2% |
| Verification latency | < 1 s (LAN) |

---

## Repository Structure

```
.
├── firmware/          # ESP32 Arduino sketch
├── server/
│   ├── api/           # Python Flask REST server
│   └── matching/      # Java SourceAFIS matching service
├── evaluation/        # FVC2002 test scripts and results
└── docs/              # Thesis PDF and figures
```

---

## Getting Started

```bash
# Clone
git clone https://github.com/Aleksandar1567/master-thesis.git

# Server (Python)
cd server/api
pip install -r requirements.txt
python app.py

# Matching service (Java)
cd server/matching
mvn package
java -jar target/matching.jar

# Flash firmware
# Open firmware/ in Arduino IDE, set your WiFi credentials and server IP, upload to ESP32
```

---

## License

MIT — see [LICENSE](LICENSE).  
Thesis text © Aleksandar Petoš, 2023. All rights reserved.
