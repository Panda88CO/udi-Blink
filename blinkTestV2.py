from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth
import re
from BlinkSystem import blink_system

def getValidName( name):
    name = bytes(name, 'utf-8').decode('utf-8','ignore')
    return re.sub(r"[^A-Za-z0-9_ ]", "", name)

# remove all illegal characters from node address
def getValidAddress( name):
    name = bytes(name, 'utf-8').decode('utf-8','ignore')
    return re.sub(r"[^A-Za-z0-9_]", "", name.lower()[:14])

def strip_syncUnitStringtoList(syncString ):
    tmp = re.sub(r"[^A-Za-z0-9_,]", "", syncString)
    tmpList = tmp.split(',')
    unitList = []
    for syncunit in tmpList:
        unitList.append(syncunit.upper())
    return(unitList)

blink = blink_system()
# Can set no_prompt when initializing auth handler
userName ='christian@olgaard.com'
password = 'coe123COE!@#'
authKey ='844022'
blink = blink_system()
success = blink.blink_auth(userName, password, authKey )


syncStr = 'SarATOGA, tAHOE  ,   TEST'
#syncUnits  = ['SARATOGA', 'TAHOE', 'TEST'] 
syncUnits = strip_syncUnitStringtoList(syncStr)

for sync_name in syncUnits:
    sync_unit = blink.get_sync_unit(sync_name)
    sync_arm = blink.get_sync_arm_info(sync_name)
    print(sync_arm )
    print(blink.set_sync_arm(sync_name, not sync_arm ))
    print(blink.set_sync_arm(sync_name,  sync_arm ))
    if sync_unit == None: #no sync units used
        camera_list = blink.get_camera_list()
    elif sync_unit == False:
        camera_list = []
        print('Sync Unit specified not found')
    else:
        camera_list = blink.get_sync_camera_list(sync_unit )

    for camera_name in camera_list:
        camera_unit = blink.get_camera_unit(camera_name)  
        print(camera_name)
        print(blink.get_camera_data(camera_name))
        print(blink.get_camera_battery_info(camera_name))
        print(blink.get_camera_arm_info(camera_name))
        print(blink.get_camera_type_info(camera_name))
        temp = blink.get_camera_motion_info(camera_name)
        print(temp)
        print(blink.set_camera_motion(camera_name))
        print(blink.set_camera_motion(camera_name, False))
        print(blink.set_camera_motion(camera_name, temp['motion_enabled']))

        print(blink.get_camera_temperatureC_info(camera_name))
        print(blink.get_camera_recording_info(camera_name))
        print(blink.snap_picture(camera_name))

'''
if  blink.key_required:
    blink.auth.send_auth_key(blink, '844022')
blink.setup_post_verify()
blink.refresh()
for name in blink.cameras:
  print(name)                   # Name of the camera
  #print(camera.attributes) 


for sync in blink.sync:
  print (sync)
  print(blink.sync[sync].arm)
syncUnitList = []
temp = syncStr.upper()
for sync1 in blink.sync:
    unit = blink.sync[sync1]
    
    print(sync1.upper(), temp)
    print (temp.find(sync1.upper()))
    if temp.find(sync.upper()) >= 0:
        syncUnitList.append(sync)
    for camera in unit.camera_list:
        cam_name = camera['name']
        tempCamera = cam_name
        cameraName = getValidName(str(cam_name))
        #cameraName = str(name)#.replace(' ','')
        nodeAdr = getValidAddress(str(cam_name))

        camera1 = unit.cameras[cam_name]
        print('camera: {}:{} {} {}'.format(cam_name, cameraName,nodeAdr, camera1.product_type))
'''

'''
for syncUnit in syncUnitList:
  print('\n {}'.format(syncUnit))
  for syncTemp in blink.sync[syncUnit]:

    print(camera_name )
    if camera.attributes['sync_module'] == syncUnit:
      print(camera.attributes['name'],camera.attributes['camera_id'] )
      print(camera.attributes) 

print('end')
'''