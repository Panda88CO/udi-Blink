# Blink Node Server Configuration (PG3 / PG3x)

This node server integrates Blink Camera Systems into Universal Devices IoX / ISY (eisy and Polisy) running PG3 or PG3x.

---

## Initial Setup & Authentication

1. **Configure Credentials:**
   - Under **Configuration** (Custom Parameters), enter:
     - `USERNAME`: Your Blink account email.
     - `PASSWORD`: Your Blink account password.
     - `TEMP_UNIT`: `C` for Celsius or `F` for Fahrenheit (defaults to `C`).
   - Click **Save Changes**.

2. **Complete 2FA:**
   - When the node server starts up for the first time, Blink sends a Two-Factor Authentication (2FA) verification code via SMS or email.
   - Enter the received code in the `AUTH_KEY` parameter field and click **Save Changes** (do **not** restart the node server).
   - The node server completes authentication and automatically discovers your Blink networks.

3. **Enable Discovered Networks:**
   - Discovered networks appear in Custom Parameters with values set to `ENABLED/DISABLED`.
   - Set each network you want to manage in IoX to `ENABLED` (or `DISABLED` to skip), then click **Save Changes**.
   - Network nodes and associated camera nodes are created in IoX.

4. **Token Persistence:**
   - Authentication tokens are persisted securely in Polyglot storage and locally.
   - Subsequent restarts and system reboots bypass 2FA automatically using the saved session tokens.
   - If tokens expire or credentials change, the node server will prompt for a new 2FA code via notice.

---

## Configuration Parameters

### Core Parameters:
- **`USERNAME`** *(Required)*: Blink login email address.
- **`PASSWORD`** *(Required)*: Blink account password.
- **`AUTH_KEY`**: Two-Factor Authentication PIN code sent by Blink upon initial setup or re-authentication.
- **`TEMP_UNIT`**: Temperature unit (`C` or `F`). Defaults to Celsius if omitted.

### Network Management:
- **`<NETWORK_NAME>`**: Each discovered network (e.g. `HOME`, `CABIN`) defaults to `ENABLED/DISABLED`.
  - Setting to `ENABLED` discovers and creates the network node and camera nodes.
  - Setting to `DISABLED` removes or skips the network and its cameras.

### Optional Email Snapshot Notifications:
- **`EMAIL_ENABLED`**: Enable emailing snapped photos (`True` or `False`). Defaults to `False`.
  - When set to `True`, the following SMTP configuration parameters will automatically appear in Custom Parameters:
    - **`SMTP`**: Outgoing SMTP server address (e.g. `smtp-mail.outlook.com` or `smtp.gmail.com`).
    - **`SMTP_PORT`**: Port number for SMTP (default is `587`).
    - **`SMTP_EMAIL`**: Authentication email for the SMTP account.
    - **`SMTP_PASSWORD`**: Password or app password for the SMTP account.
    - **`EMAIL_RECEPIENT`**: Recipient email address where images are delivered.
  - When set to `False`, these parameters are hidden and removed from the UI (any previously entered credentials are saved internally).

---

## Node Types & Driver Controls

### 1. Network Node (`BLINKNETWORK`)
- **`ST`** (Arm Status): `0` = Disarmed, `1` = Armed, `2` = Individually Camera Assigned.
- **`GV0`** (Connected): `0` = Offline, `1` = Online.
- **`TIME`**: Timestamp of last successful status update.
- **Commands**:
  - `Set Arming` (`DON` / `DOF`): Arm or disarm all cameras on the network.
  - `Update Network`: Force query/refresh network data.

### 2. Sync Unit Node (`BLINKSYNC`)
- **`ST`** (Connected): `0` = Offline, `1` = Online.
- **Commands**:
  - `Update SyncUnit`: Force query/refresh sync module data.

### 3. Camera Node (`BLINKCAMERAC` / `BLINKCAMERAF` / `BLINKCAMERA`)
- **`ST`** (Motion Detection): `0` = Disabled, `1` = Enabled.
- **`GV0`** (Connected): `0` = Offline, `1` = Online.
- **`GV1`** (Battery Status): `0` = OK, `1` = Not OK, `3` = External / Wired, `10` = USB powered.
- **`GV3`** (Camera Type): Model identification (`Mini`, `Doorbell`, `Outdoor`, `XT-2`, `Floodlight`, `Outdoor v4`, etc.).
- **`GV5`** (Motion Detected): `0` = No Motion, `1` = Motion Detected.
- **`CLITEMP`** (Temperature): Ambient temperature (for models equipped with temperature sensors).
- **`TIME`**: Timestamp of last update.
- **Commands**:
  - `Set Motion Detection` (`DON` / `DOF`): Enable or disable motion detection.
  - `Take Picture`: Capture a new thumbnail snapshot (replaces app thumbnail, optional email).
  - `Take Video`: Record a 5-second video clip.
  - `Update Camera`: Force query/refresh camera data.

---

## Polling & Heartbeat

- **ShortPoll**: Currently not used.
- **LongPoll**: Default is `180` seconds (minimum recommended is `60` seconds). Updates camera states, temperatures, and battery levels from Blink cloud servers. Do not set too frequently to avoid cloud rate limits.
- **Heartbeat**: During each successful LongPoll update, enabled network nodes send a `DON` followed 5 seconds later by `DOF`. You can write an IoX program to monitor this cycle and alert if updates stop.

---

## Important Notes
- **Naming Conventions**: Please remove special characters from camera and sync module names in the Blink mobile app prior to discovery.
- **Arming Dependency**: Individual cameras can only be enabled/armed when the parent network is armed.
- **Dynamic Profiles**: PG3x manages node profiles dynamically; no static profile reinstalls are necessary.