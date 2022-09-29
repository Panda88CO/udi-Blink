#!/usr/bin/env python3
try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    import sys
    #logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[
        logging.FileHandler("debug1.log"),
        logging.StreamHandler(sys.stdout) ]
    )

from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth
import re


class blink_system(object):
    def __init__(self):
        #self.userName =userName
        #self.password = password
        #self.AUTHKey = AUTHKey
        self.cameraType = {'owl'}

        logging.info('Accessing Blink system')
        self.blink = Blink()
        self.temp_unit = 'C'
        self.pic_email_enabled = False


    def auth (self, userName, password, authenKey = None):
        # Can set no_prompt when initializing auth handler
        auth = Auth({"username":userName, "password":password}, no_prompt=True)
        if auth:
            self.blink.auth = auth
            logging.info('Auth: {}'.format(auth))
            self.blink.start()
            if self.blink.key_required:
                logging.info('Auth key required')
                if self.authkey == None or self.authKey == '':
                  
                    return('AuthKey')
                else:
                    auth.send_auth_key(self.blink, self.authKey)
            logging.debug('setup_post_verify')
            self.blink.setup_post_verify()
            self.blink.refresh()
            return('ok')
        else:
            return{'no login'}

    def refresh(self):
         logging.debug('refresh')
         return(self.blink.refresh())

    def set_temp_unit(self, temp_unit):
        self.temp_unit = temp_unit

    #def set_pic_email_enabled(self, status):
    #   self.pic_email_enabled = status

    def get_sync_unit(self, sync_unit_name):
        logging.debug('get_sync_unit - {}'.format(sync_unit_name))
        for sync_name in self.blink.sync:
            tmp = re.sub(r"[^A-Za-z0-9_,]", "", sync_name)
            if tmp.upper() == sync_unit_name:
                 return(self.blink.sync[sync_name])
        return(False)
        
    def get_camera_list(self):
        logging.debug('get_camera_list')
        cam_list = []
        for cam_name in self.blink.cameras:
            cam_list.append(cam_name)
        return(cam_list)
        
    def get_sync_camera_list(self, sync_unit):
        logging.debug('get_sync_camera_list')
        cam_list = []
        for camera in sync_unit.camera_list:
             cam_name = camera['name']
             cam_list.append(cam_name)
        return(cam_list)
 
    def get_sync_arm_info(self, sync_name):
        logging.debug('get_sync_arm_info - {} '.format(sync_name ))
        return(self.blink.sync[sync_name].arm)

    def set_sync_arm (self, sync_name, armed=True):
        logging.debug('set_arm_sync = {}- {} '.format(sync_name, armed ))
        self.blink.sync[sync_name].arm = armed
        self.blink.refresh()

    def get_sync_online(self, sync_name):
        logging.debug('get_sync_online - {} {} '.format(sync_name, self.blink.sync[sync_name].online ))
        return(self.blink.sync[sync_name].online )

    #def get_sync_blink_camera_unit(self, sync_unit, camera_name):
    #    logging.debug('get_sync_blink_camera_unit - {} from {}'.format(camera_name,sync_unit ))


    def get_camera_data(self, camera_name):
        logging.debug('get_camera_data - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].attributes)


    def get_camera_battery_info(self, camera_name):
        logging.debug('get_camera_battery_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].battery)


    def get_camera_battery_voltage_info(self, camera_name):
        logging.debug('get_camera_battery_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].battery_voltage )


    def get_camera_arm_info(self, camera_name):
        logging.debug('get_camera_arm_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].arm)


    def set_camera_arm(self, camera_name, armed=True):
        logging.debug('set_camera_arm - {} {}'.format(camera_name, armed ))
        self.blink.cameras[camera_name].arm = armed
        self.blink.refresh()

    def get_camera_type_info(self, camera_name):
        logging.debug('get_camera_type_info - {} '.format(camera_name ))
        temp = self.blink.cameras[camera_name].product_type
        if temp == 'owl':
            return('mini')
        elif temp == 'catalina':
            return('Blink Outdoor')
        elif temp == 'lotus':
            return('doorbell')
        else:
            return('default')


    def get_camera_motion_enabled_info(self, camera_name):
        logging.debug('get_camera_motion_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].motion_enabled )

    def get_camera_motion_detected_info(self, camera_name):
        logging.debug('get_camera_motion_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].motion_detected )



    def get_camera_temperatureC_info(self, camera_name):
        logging.debug('get_camera_temperatureC_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].temperature_c)


    def get_camera_recording_info(self, camera_name):
        logging.debug('get_camera_recording_info - {} '.format(camera_name ))
        return(0)

    def snap_picture(self, camera_name):
        logging.debug('snap_picture - {} '.format(camera_name ))
        self.blink.cameras[camera_name].snap_picture()
        self.blink.refresh()             # Get new information from server
        self.blink.cameras[camera_name].image_to_file('./'+camera_name+'_image.jpg')

    def get_camera_unit(self, camera_name):
        logging.debug('get_camera_unit - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name])

    
    def refresh_data(self):
        logging.debug('blink_refresh_data')
        self.blink.refresh()
        
    