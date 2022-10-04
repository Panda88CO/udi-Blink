# udi-Blink
Blink Node Server for IoP/ISY
The node is targeted primarily at arming and disarming cameras, but allows snapping a picture and videos - e.g. triggered by differnt motion sensor.  Videos sometimes have delays in executing if system is busy.  You should receive a notification in Blink App when video is taken.  The video can be viewed in app. Picture overwrites the thumbnail in app
(Furutre will add ability to have the picture emailed automatically to the user account)

# Setup
User needs provide username and password used for the Blink App.  A one time/2way authentication may also be needed.  In the case of 2 way autenticantion.  Obtain the code using the Blink app and enter the data under configuration

The user must specify the sync unit(s) where the cameras are registered - A comman separated list is ok if more than 1 sync unit is being used.  If no sync unit is used specify NONE

Note, the API does not handle special characters in the camera and sync names - please remove/rename those before setting upthe node

ShortPoll is heart beat from controller node, LongPoll updates data.  Do not run update too often, as system may get throttled by Blink - Suggested to be more than 60sec between updates

# Still to be done
I only have 3 camera types - Mini, doorbell and Outdoot (new) - I do not know the older camera's name. If you have those please enable debug and click update camera and provide log file and I can update this 

Plan is to add ability to send pictures of emails/videos taken.

# misc
Based on blink API https://github.com/fronzbot/blinkpy
