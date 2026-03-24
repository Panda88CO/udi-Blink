# udi-Blink
Blink Node Server for IoP/ISY
The node is targeted primarily at arming and disarming cameras, but allows snapping a picture and videos - e.g. triggered by differnt motion sensor.  Videos sometimes have delays in executing if system is busy.  You should receive a notification in Blink App when video is taken.  The video can be viewed in app. Picture overwrites the thumbnail in app
(Furutre will add ability to have the picture emailed automatically to the user account)

# Setup
User needs provide username and password used for the Blink App.  A 2FA authentication is also be needed during start up.  Start the node server.  A 2FA code is sent to your phone - enter the code under configuration (AUTH_KEY) and press save - Do not restart.

The node runs and extracts the differnt networks that are defind in Blink.  
You need to Add each network name as customer parameter with value ENABLED or DISABLED
Save and restart
Go through the 2FA procedure again and the node should be up and running 

Note, the API does not handle special characters in the camera and sync names - please remove/rename those before setting upthe node

ShortPoll is currently not used, 
LongPoll updates data.  Do not run update too often, as system may get throttled by Blink - Suggested to be more than 60sec between updates.
LongPoll sends a DON followed 5sec later by DOF for the differnt network nodes if the node receives data (essentially a heartbeat).  This can be used to send a message if no heartbeat is received 
E.g. have a program that sends a message after 6 min dealy (Assume long poll set to 5 min) and another that stop the first program if a heartbeat is received waits a few secs and then starts is again. 



# misc
Based on blink API https://github.com/fronzbot/blinkpy
