# udi-Blink
Blink Node Server for IoP/ISY (PG3 / PG3x)

The node server is targeted primarily at arming and disarming cameras, but allows snapping pictures and videos - e.g. triggered by different motion sensors. Videos sometimes have delays in executing if the system is busy. You should receive a notification in the Blink App when video is taken. The video can be viewed in the Blink app. Pictures overwrite the thumbnail in the app.
Optionally, snapped pictures can be emailed automatically to a configured recipient address.

# Setup
1. Provide the **USERNAME** and **PASSWORD** used for the Blink App under Configuration (Custom Parameters).
2. Start the node server. On initial setup, two-factor authentication (2FA) is required. A 2FA code is sent to your phone/email by Blink.
3. Enter the 2FA code in the **AUTH_KEY** field and click **Save** (do not restart).
4. The node will authenticate and discover the different networks defined in your Blink system.
5. In Configuration, set each discovered network parameter to **ENABLED** or **DISABLED**, and click **Save**.
6. **Authentication Persistence:** Successful logins persist session tokens locally and in Polyglot storage. On subsequent node restarts or system reboots, the node will reuse the saved tokens and start up directly without requiring 2FA. If tokens ever expire or credentials change, the node will automatically start over and prompt for a new 2FA PIN.

Note: The API does not handle special characters in camera and sync module names - please remove or rename those in the Blink app before setting up the node.

# Polling & Heartbeat
- **ShortPoll** is currently not used.
- **LongPoll** updates data from Blink servers. Do not run updates too often, as the system may get throttled by Blink (suggested interval is 60+ seconds, default is 180s).
- LongPoll sends a DON followed 5 seconds later by DOF for enabled network nodes when data is received (heartbeat). This can be used in ISY/IoX programs to monitor node health and alert if a heartbeat is missed (e.g. have a program that sends a notification if no heartbeat is received within the expected polling window).

# Misc
Based on blinkpy API: https://github.com/fronzbot/blinkpy
