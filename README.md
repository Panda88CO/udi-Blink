# udi-Blink
Blink Node Server for Universal Devices IoX / ISY (PG3 & PG3x)

An integration for Blink Camera Systems with Universal Devices eisy / Polisy running PG3 / PG3x. Allows arming and disarming systems and individual cameras, monitoring connectivity, battery, temperature, and motion status, and triggering picture or video captures from ISY/IoX programs.

## Features
- **Network & Sync Module Control:** Arm and disarm complete Blink systems or individual sync modules.
- **Camera Control:** Enable or disable motion detection on individual cameras.
- **Dynamic Profiles:** Native dynamic JSON profile support in PG3x.
- **Status Monitoring:** Tracks online connectivity, motion detection, battery health, Wi-Fi signal, and ambient temperature.
- **Media Capture:** Take snapshots (updates app thumbnail) and record 5-second video clips via ISY commands.
- **Email Notifications:** Optionally email captured snapshots automatically via SMTP.
- **2FA Persistence:** Session tokens are saved persistently to PG3 and disk, bypassing 2FA on restarts and reboots.
- **Heartbeat Monitoring:** Network nodes pulse a heartbeat signal (`DON` followed by `DOF`) during polls for automated health monitoring.

---

## Node Types & Controls

### 1. Network Node (`BLINKNETWORK`)
Represents a Blink system network.
- **Drivers:**
  - `ST`: Arm Status (`Disarmed`, `Armed`, `Individually Camera Assigned`, `Unknown`)
  - `GV0`: Connected (`Offline`, `Online`)
  - `TIME`: Last Successful Update Time
- **Commands:**
  - `Set Arming` (`DON` / `DOF`): Arm or disarm the network.
  - `Update Network`: Force query and refresh network state.
- **Heartbeat:** Sends `DON` followed 5 seconds later by `DOF` during LongPoll when data is successfully refreshed.

### 2. Sync Unit Node (`BLINKSYNC`)
Represents an individual Sync Module.
- **Drivers:**
  - `ST`: Connected (`Offline`, `Online`)
- **Commands:**
  - `Update SyncUnit`: Query and refresh sync module state.

### 3. Camera Node (`BLINKCAMERAC` / `BLINKCAMERAF` / `BLINKCAMERA`)
Represents individual Blink cameras, doorbells, and floodlights.
- **Drivers:**
  - `ST`: Motion Detection Status (`Disabled`, `Enabled`)
  - `GV0`: Connected (`Offline`, `Online`)
  - `GV1`: Battery Status (`OK`, `Not OK`, `External / Wired`, `USB powered`)
  - `GV3`: Camera Type (`Mini`, `Doorbell`, `Outdoor`, `XT-2`, `Floodlight`, `Outdoor v4`, etc.)
  - `GV5`: Motion Detected (`No Motion`, `Motion Detected`)
  - `CLITEMP`: Temperature (°C or °F based on `TEMP_UNIT`, for supported models)
  - `TIME`: Last Update Time
- **Commands:**
  - `Set Motion Detection` (`DON` / `DOF`): Enable or disable motion detection.
  - `Take Picture`: Snap a new image (updates Blink app thumbnail, optional email).
  - `Take Video`: Record a 5-second video clip.
  - `Update Camera`: Query and refresh camera state.

---

## Installation & Setup

1. **Credentials:** In PG3 Configuration (Custom Parameters), enter your Blink app **USERNAME** and **PASSWORD**.
2. **Temperature Unit:** Set **TEMP_UNIT** to `C` or `F` (defaults to Celsius if omitted).
3. **Start Node Server:** On initial startup, Blink will send a Two-Factor Authentication (2FA) PIN code via SMS/email.
4. **Enter Auth Key:** Enter the received PIN into the **AUTH_KEY** configuration field and click **Save** (do not restart).
5. **Enable Networks:** Discovered networks will appear as configuration parameters defaulted to `ENABLED/DISABLED`. Set each desired network to `ENABLED` (or `DISABLED` to ignore) and click **Save**.
6. **Authentication Persistence:** Successful logins persist session tokens locally and in Polyglot storage. On subsequent node restarts or system reboots, the node will reuse saved tokens and start up directly without requiring 2FA. If tokens ever expire or credentials change, the node will prompt for a new 2FA PIN.

---

## Configuration Parameters

| Parameter | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `USERNAME` | **Yes** | — | Blink account email address. |
| `PASSWORD` | **Yes** | — | Blink account password. |
| `AUTH_KEY` | Initial Setup | — | 2FA PIN code sent by Blink upon login. |
| `TEMP_UNIT` | Optional | `C` | Temperature unit (`C` or `F`). |
| `<NETWORK_NAME>` | **Yes** | `ENABLED/DISABLED` | Set each discovered network to `ENABLED` or `DISABLED`. |

### Optional Email Configuration:
| Parameter | Default | Description |
| :--- | :--- | :--- |
| `EMAIL_ENABLED` | `False` | Set to `True` to email snapped pictures. |
| `SMTP` | — | SMTP server address (e.g., `smtp-mail.outlook.com`). |
| `SMTP_PORT` | `587` | SMTP port. |
| `SMTP_EMAIL` | — | Sender email address for SMTP authentication. |
| `SMTP_PASSWORD` | — | Password (or app password) for SMTP account. |
| `EMAIL_RECEPIENT` | — | Recipient email address where photos are sent. |

---

## Polling & Heartbeat
- **ShortPoll:** Reserved (not currently used).
- **LongPoll:** Interval (default `180` seconds, recommended >= `60`s) to fetch updates from Blink cloud servers. Avoid setting too short to prevent rate-limiting by Blink.
- **Heartbeat Monitoring:** When data is received on LongPoll, enabled network nodes cycle `DON` followed 5 seconds later by `DOF`. Use an IoX program to monitor this cycle for heartbeat alerts.

---

## Notes & Best Practices
- **Camera Naming:** Avoid special characters in camera and sync module names in the Blink app prior to adding.
- **Arming Hierarchy:** Individual cameras can only be enabled/armed if their parent network is armed.
- **Dynamic Profiles:** Dynamic JSON profiles are emitted automatically to PG3x.
- **API Credits:** Built upon the open-source [blinkpy](https://github.com/fronzbot/blinkpy) library.
