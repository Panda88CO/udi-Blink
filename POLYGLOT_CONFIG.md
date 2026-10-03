# udi-blink

This node server is mostly targeted to arm and disarm cameras from within IoP/ISY (e.g. follow arming of alarm system).
It provides the ability to snap pictures and trigger videos based on events (e.g. motion sensor triggers). Snapping a picture replaces the existing thumbnail in the Blink app. Cameras report motion, but state needs to be polled; polling should not happen too frequently or Blink servers may throttle requests.
An option to have snapped pictures emailed to you is also available.

## Installation & Configuration

- **ShortPoll**: Currently not used.
- **LongPoll**: Updates data. Do not set interval too short to avoid being throttled by Blink (suggested: 60s or more, default is 180s).

### Configuration Parameters:
- **TEMP_UNIT**: Temperature unit (`C` or `F`).
- **USERNAME**: Blink login email address.
- **PASSWORD**: Blink account password.
- **AUTH_KEY**: Two-factor authentication (2FA) PIN code received from Blink. Enter this code when requested on initial setup or re-auth, then click **Save** (do not restart). Once authenticated, tokens are saved persistently and subsequent reboots/restarts will bypass 2FA automatically.

### Email Notification Parameters (Optional):
- **EMAIL_ENABLED**: Enable emailing of snapped pictures (`True`/`False`).
- **SMTP**: Address of SMTP server used to send email (e.g. `smtp-mail.outlook.com`).
- **SMTP_PORT**: SMTP port (default is `587`).
- **SMTP_EMAIL**: Email address used to authenticate on SMTP server.
- **SMTP_PASSWORD**: Password for SMTP account.
- **EMAIL_RECEPIENT**: Recipient email address where pictures are sent.

### Network & Camera Configuration:
- **Networks**: Discovered on initial run. Each network parameter (e.g. `HOME`) can be set to `ENABLED` or `DISABLED` in Custom Parameters.
- **Cameras**: Discovered cameras default to `ENABLED/DISABLED` in Custom Parameters (e.g. `CAM_PATIO`). A notification will remain visible until all discovered cameras have been explicitly set to either `ENABLED` or `DISABLED`.
  - Setting a camera to `ENABLED` creates its node in Polyglot/IoX.
  - Setting a camera to `DISABLED` ignores/removes its node.
  - Once all cameras have a selected value of either `ENABLED` or `DISABLED`, the notification is automatically cleared.

## Notes
- **Armed / Disarmed State**: You cannot enable an individual camera if the system/network is disarmed. If the system is armed, individual cameras can be enabled or disabled.
- **Mail Server Setup**: For Outlook/Hotmail, SMTP is `smtp-mail.outlook.com`, port is `587`, and SMTP_EMAIL / SMTP_PASSWORD are your account credentials (or app password if 2FA is enabled on your email account).
- **Authentication Across Reboots**: Authentication tokens are stored locally and in Polyglot storage. On system reboots or node server restarts, the node server will reuse existing tokens so you do not have to re-enter a 2FA PIN. If tokens expire or credentials change, the node server will start over and prompt for a new 2FA PIN via `AUTH_KEY`.