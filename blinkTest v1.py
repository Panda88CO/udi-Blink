from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth

blink = Blink()
# Can set no_prompt when initializing auth handler
auth = Auth({"username":'christian@olgaard.com', "password":'coe123COE!@#'}, no_prompt=True)
blink.auth = auth
blink.start()
auth.send_auth_key(blink, '844022')
blink.setup_post_verify()
for name, camera in blink.cameras.items():
  print(name)                   # Name of the camera
  print(camera.attributes) 