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


        logging.info('Accessing Blink system')
        self.blink = Blink()



    def blink_auth (self, userName, password, authenKey = None):
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

    #def get_sync_blink_camera_unit(self, sync_unit, camera_name):
    #    logging.debug('get_sync_blink_camera_unit - {} from {}'.format(camera_name,sync_unit ))


    def get_camera_data(self, camera_name):
        logging.debug('get_camera_data - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].attributes)


    def get_camera_battery_info(self, camera_name):
        logging.debug('get_camera_battery_info - {} '.format(camera_name ))

    def get_camera_arm_info(self, camera_name):
        logging.debug('get_camera_arm_info - {} '.format(camera_name ))

    def get_camera_type_info(self, camera_name):
        logging.debug('get_camera_type_info - {} '.format(camera_name ))


    def get_camera_motion_info(self, camera_name):
        logging.debug('get_camera_type_info - {} '.format(camera_name ))

    def get_camera_temperatureC_info(self, camera_name):
        logging.debug('get_camera_type_info - {} '.format(camera_name ))

    def get_camera_recording_info(self, camera_name):
        logging.debug('get_camera_type_info - {} '.format(camera_name ))

    def get_camera_unit(self, camera_name):
        logging.debug('get_camera_unit - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name])

    
    def refresh_data(self):
        logging.debug('blink_refresh_data')
        self.blink.refresh()
        
    