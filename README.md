# udi-Blink
Blink Node Server for IoP/ISY
The node is primarily targeted at arming and disarming cameras, but allows snapping a picture (Furutre will add ability to have the picture emailed automatically to the user account)

# Setup
User needs provide username and password used for the Blink App.  A one time authndication may also be needed.
Furthermore the user must specify the sync unit(s) where the cameras are registered - A comman separated list is ok if more than 1 sync unit is being used.  If not sync unit is used specify NONE


# Still to be done
Plan is to add ability to send pictures of emails taken - Hopefully using the ISY/IoP email server.
May look at adding ability to take a video (not only picture)
I only have 3 camera types - Mini, doorbell and Outdoot (new) - I do not know the older camera's name. If you have those please enable debug and click update camera and provide log file and I can update this 