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

from blinkpy.blinkpy_co import Blink
from blinkpy.auth_co import Auth


import re
import datetime
import time
import os
import smtplib
import ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class blink_system(object):
    def __init__(self):
        #self.userName =userName
        #self.password = password
        #self.AUTHKey = AUTHKey
        self.cameraType = {'owl'}

        logging.info('Accessing Blink system')
        self.blink = Blink()
        self.temp_unit = 'C'
        self.email_en = False


    def auth1 (self, userName, password):
        # Can set no_prompt when initializing auth handler
        auth_OK = Auth({"username":userName, "password":password}, no_prompt=True)
        if auth_OK:
            self.blink.auth = auth_OK
            logging.info('Auth: {}'.format(auth_OK))
            self.blink.start()
            return(not self.blink.key_required)
                #logging.info('Auth key required')
                #return(True)
            #else:
                #return('No need')
            '''
            if self.blink.key_required:
                logging.info('Auth key required')
                if authenKey == None or authenKey == '':
                  
                    return('AuthKey Empty: {}'.format(authenKey))
                else:
                    auth.send_auth_key(self.blink, authenKey)
            logging.debug('setup_post_verify')
            time.sleep(10)
            self.blink.setup_post_verify()
            time.sleep(1)
            self.blink.refresh()
            time.sleep(3)
            return('ok')
        else:
            return{'no login'}
            '''
        
    def auth_key(self, authenKey = None):
        logging.debug('auth_key')
        if self.blink.key_required:
            logging.info('Auth key required')
            if authenKey == None or authenKey == '':
                
                return('AuthKey Empty: {}'.format(authenKey))
            else:
                result = self.blink.auth.send_auth_key(self.blink, authenKey)
                self.key_required = not result
        '''
        logging.debug('setup_post_verify')
        time.sleep(10)
        self.blink.setup_post_verify()
        time.sleep(1)
        self.blink.refresh()
        time.sleep(3)
        return('ok')
        '''
    def finalize_auth(self):
        logging.debug('finalize_auth')
        time.sleep(2)
        self.blink.setup_post_verify()
        time.sleep(5)
        self.blink.refresh()
        time.sleep(3)
        return('ok')
    
    def auth_old (self, userName, password, authenKey = None):
        # Can set no_prompt when initializing auth handler
        auth = Auth({"username":userName, "password":password}, no_prompt=True)
        if auth:
            self.blink.auth = auth
            logging.info('Auth: {}'.format(auth))
            self.blink.start()
            if self.blink.key_required:
                logging.info('Auth key required')
                if authenKey == None or authenKey == '':
                  
                    return('AuthKey Empty: {}'.format(authenKey))
                else:
                    auth.send_auth_key(self.blink, authenKey)
            logging.debug('setup_post_verify')
            time.sleep(10)
            self.blink.setup_post_verify()
            time.sleep(1)
            self.blink.refresh()
            time.sleep(3)
            return('ok')
        else:
            return{'no login'}

    def refresh_data(self):
        logging.debug('blink_refresh_data')
        self.blink.refresh()
        
    def set_temp_unit(self, temp_unit):
        self.temp_unit = temp_unit


    def get_network_list(self):
        logging.debug('get_network_list')
        return( self.blink.homescreen['networks'])



    def get_sync_unit(self, sync_unit_name):
        logging.debug('get_sync_unit - {}: {}'.format(sync_unit_name, self.blink.sync))
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
        logging.debug('get_sync_arm_info - {} {} '.format(sync_name,  self.blink.sync[sync_name].arm))
        return(self.blink.sync[sync_name].arm)

    def set_sync_arm (self, sync_name, armed=True):
        logging.debug('set_arm_sync = {}- {} '.format(sync_name, armed ))
        self.blink.sync[sync_name].arm =armed
        #self.blink.refresh()

    def get_sync_online(self, sync_name):
        logging.debug('get_sync_online - {} {} '.format(sync_name, self.blink.sync[sync_name].online ))
        return(self.blink.sync[sync_name].online )

    #def get_sync_blink_camera_unit(self, sync_unit, camera_name):
    #    logging.debug('get_sync_blink_camera_unit - {} from {}'.format(camera_name,sync_unit ))

    def get_cameras_on_network(self, network_id):
        logging.debug('get_cameras_on_network - {}'.format(network_id))
        camera_list = []
        raw_camera_list = self.blink.homescreen['cameras']
        for indx, camera in enumerate (raw_camera_list):
            if camera['network_id'] == network_id:
                camera_list.append(camera)

        return(camera_list)



    def get_sync_modules_on_network(self, network_id):
        logging.debug('get_sync_modules_on_network - {}'.format(network_id))
        sync_list = []
        raw_sync_list = self.blink.homescreen['sync_modules']
        for indx, sync in enumerate (raw_sync_list):
            if sync['network_id'] == network_id:
                sync_list.append(sync)    
        return(sync_list)
    
    def get_network_arm_state(self, network_id):
        logging.debug('get_network_arm_state {}'.format(network_id))
        arm_state = None
        for indx, network in enumerate(self.blink.homescreen['networks']):
            if network['id'] == network_id:
                arm_state = network['armed']
                return(arm_state)
        return(arm_state)

    def set_networs_arm_state(self, network_id, arm):
        logging.debug('set_network_arm_state {} {}'.format(network_id, arm))
        return(self.blink.set_network_arm(network_id, arm))
       

    def get_camera_data(self, camera_name):
        logging.debug('get_camera_data - {} {}'.format(camera_name, self.blink.cameras[camera_name].attributes ))
        return(self.blink.cameras[camera_name].attributes)


    def get_camera_battery_info(self, camera_name):
        logging.debug('get_camera_battery_info - {} '.format(camera_name ))
        try:
            temp = self.blink.cameras[camera_name].battery
            if temp: 
                return(self.blink.cameras[camera_name].battery)
            else:
                return('No Battery')
        except Exception as e:
            logging.debug('Battery info failed : {}'.format(e))
            return(None)

    def get_camera_battery_voltage_info(self, camera_name):
        logging.debug('get_camera_battery_info - {} '.format(camera_name ))
        try:
            temp = self.blink.cameras[camera_name].battery_voltage 
            if temp:
                return(self.blink.cameras[camera_name].battery_voltage )
            else:
                return('No Battery')
        except Exception as e:
            logging.debug('Battery Voltage info failed : {}'.format(e))
            return(None)        


    def get_camera_arm_info(self, camera_name):
        logging.debug('get_camera_arm_info - {} {}'.format(camera_name, self.blink.cameras[camera_name].arm ))
        return(self.blink.cameras[camera_name].arm)

    def set_camera_arm(self, camera_name, armed=True):
        logging.debug('set_camera_arm - {} {}'.format(camera_name, armed ))
        self.blink.cameras[camera_name].arm = armed

    def get_camera_type_info(self, camera_name):
        logging.debug('get_camera_type_info - {} '.format(camera_name ))
        temp = self.blink.cameras[camera_name].product_type
        if temp == 'owl':
            return('mini')
        elif temp == 'catalina':
            return('Blink Outdoor')
        elif temp == 'lotus':
            return('doorbell')
        elif temp == 'xt2':
            return('XT-2')
        else:
            return('default')

    def refresh(self):
        return(self.blink.refresh())

    def get_camera_motion_enabled_info(self, camera_name):
        logging.debug('get_camera_motion_info - {} {}'.format(camera_name, self.blink.cameras[camera_name].motion_enabled ))
        return(self.blink.cameras[camera_name].motion_enabled )

    def set_camera_motion_detect(self, camera_name, enabled=True):
        logging.debug('set_camera_motion_detect = {}- {} '.format(camera_name, enabled ))
        return(self.blink.cameras[camera_name].set_motion_detect(enabled))



    def get_camera_motion_detected_info(self, camera_name):
        logging.debug('get_camera_motion_info - {} {}'.format(camera_name, self.blink.cameras[camera_name].motion_detected ))
        return(self.blink.cameras[camera_name].motion_detected )

    def get_camera_temperatureC_info(self, camera_name):
        logging.debug('get_camera_temperatureC_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].temperature_c)


    def get_camera_recording_info(self, camera_name):
        logging.debug('get_camera_recording_info - {} '.format(camera_name ))
        return(0)
    
    def get_camera_status(self, camera_name):
        logging.debug('get_camera_staus - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].online_status)
    def get_camera_info(self, camera_name):
        logging.debug('get_camera_temperatureC_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].request_camera_info())
    
    def get_system_notifications(self):
        return(self.blink.request_system_notifications())
    '''
    def snap_picture(self, camera_name):

        logging.debug('snap_picture - {} - {}'.format(camera_name, photo_string ))
        self.blink.cameras[camera_name].snap_picture()
        dinfo = datetime.datetime.now()
        photo_string =  camera_name+dinfo.strftime("_%m_%d_%Y-%H_%M_%S")+'.jpg'
        self.blink.refresh()             # Get new information from server
        self.blink.cameras[camera_name].image_to_file('./'+photo_string)
        #emailMedia.sendEmail('./'+photo_string, 'christian.olgaard@gmail.com', dinfo)
        
    def snap_video(self, camera_name):

        temp = self.blink.cameras[camera_name].record()
        count = 0
        if 'created_at' not in temp and count <4:
            logging.info('Capture did not succeed - trying again in 10 sec')
            time.sleep(10)
            temp = self.blink.cameras[camera_name].record()
            count= count + 1
        if count >= 4:
            return(False)
        dinfo = datetime.datetime.now()
        video_string =  camera_name+dinfo.strftime("_%m_%d_%Y-%H_%M_%S")+'.mp4'
        logging.debug('snap_video - {} - {}'.format(camera_name, video_string ))
        time.sleep(5)
        self.blink.refresh()   
        count = 0
        while None == self.blink.cameras[camera_name].clip and count <4:  # Get new information from server
            time.sleep(10)
            self.blink.refresh()   
            logging.debug('waiting for video clip to appear {}'.format( self.blink.cameras[camera_name].clip))
            count = count + 1
        #link = self.blink.cameras[camera_name].request_videos()
        self.blink.cameras[camera_name].video_to_file('./'+video_string)
        #file = open('./'+video_string, 'rb')
        #emailMedia.sendEmail('./'+video_string, 'christian.olgaard@gmail.com', dinfo)
        if count >= 4:
            return(False)
        else:
            return(True)
    '''

    def snap_picture(self, camera_name):
        self.blink.cameras[camera_name].snap_picture()
        time.sleep(1)
        #self.blink.cameras[camera_name].snap_picture()
        dinfo = datetime.datetime.now()
        timeInf = int(time.time())
        photo_string =  camera_name+dinfo.strftime("_%m_%d_%Y-%H_%M_%S")+'.jpg'
        logging.debug('snap_picture - {} - {}'.format(camera_name, photo_string ))
        self.blink.refresh()  
        thumbnailStr = self.blink.cameras[camera_name].thumbnail
        logging.debug('humbnailStr: {} {}'.format(type(thumbnailStr), thumbnailStr))
        tsIndex = int(thumbnailStr.find('ts='))
        pic_ts = int( thumbnailStr[tsIndex+3:tsIndex+13])
        iter = 0
        while pic_ts < timeInf - 5 and iter < 10: # allow 5 sec diff
            logging.debug('Waiting for pic to update last image  time {} vs  capture time{}'.format(pic_ts, timeInf))
            time.sleep(15)
            self.blink.refresh()  
            thumbnailStr = self.blink.cameras[camera_name].thumbnail
            tsIndex = int(thumbnailStr.find('ts='))
            pic_ts = int( thumbnailStr[tsIndex+3:tsIndex+13])
            iter = iter + 1
            #logging.debug('Waiting for pic to update {} vs  {}'.format(pic_ts, timeInf))
        if iter >= 10:
            logging.error('picture not updated')
        else:
            self.blink.cameras[camera_name].image_to_file('./'+photo_string)
            if self.email_en:
                self.send_email(photo_string, camera_name)
        os.remove(photo_string)
        
        
        
    def snap_video(self, camera_name):
        temp = self.blink.cameras[camera_name].record()
        count = 0
        if 'created_at' not in temp and count <4:
            logging.info('Capture did not succeed - trying again in 10 sec')
            time.sleep(10)
            temp = self.blink.cameras[camera_name].record()
            count= count + 1
        if count >= 4:
            return(False)
        else:
            return(True)
        '''
        dinfo = datetime.datetime.now()
        video_string =  camera_name+dinfo.strftime("_%m_%d_%Y-%H_%M_%S")+'.mp4'
        logging.debug('snap_video - {} - {}'.format(camera_name, video_string ))
        time.sleep(10)
        self.blink.refresh()   
        count = 0
        while None == self.blink.cameras[camera_name].clip and count <4:  # Get new information from server
            time.sleep(10)
            self.blink.refresh()   
            logging.debug('waiting for video clip to appear {}'.format( self.blink.cameras[camera_name].clip))
            count = count + 1
        #link = self.blink.cameras[camera_name].request_videos()
        self.blink.cameras[camera_name].video_to_file('./'+video_string)
        
        if self.email_en:
            
            self.send_email(video_string, camera_name)
        if count >= 4:
            return(False)
        else:
            return(True)
        '''

    def get_camera_unit(self, camera_name):
        logging.debug('get_camera_unit - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name])

    def set_email_info(self, email_info):
        logging.debug('set_email_info:{}'.format(email_info))
        self.email_en = email_info['email_en']
        self.smtp = email_info['smtp']
        self.smtp_port = email_info['smtp_port']
        self.email_sender = email_info['email_sender']
        self.email_password = email_info['email_password']
        self.email_recepient = email_info['email_recepient']

    def send_email(self, mediaFileName, camera_name):
        try:
            logging.debug('send_email: {} {}'.format(mediaFileName,camera_name ))
            subject = 'Captured Media File from {}'.format(camera_name)
            # Create a multipart message and set headers
            message = MIMEMultipart()
            message['From'] = self.email_sender
            message['To'] = self.email_recepient
            message['Subject'] = subject
            msg_content = MIMEText('File from camera attached', 'plain', 'utf-8')
            message.attach(msg_content)
            #part = MIMEBase('application', "octet-stream")

            with open('./'+mediaFileName, 'rb') as f:
                # set attachment mime and file name, the image type is png
                if mediaFileName.__contains__('jpg'):
                    mime = MIMEBase('image', 'jpg', filename=mediaFileName)
                else:
                    mime = MIMEBase('video/mp4', 'mp4', filename=mediaFileName)
                mime.add_header('Content-Disposition', 'attachment', filename=mediaFileName)
                mime.add_header('X-Attachment-Id', '0')
                mime.add_header('Content-ID', '<0>')
                # read attachment file content into the MIMEBase object
                mime.set_payload(f.read())
                # encode with base64
                encoders.encode_base64(mime)
                message.attach(mime)    
                context = ssl.create_default_context()
        
            with smtplib.SMTP(self.smtp , self.smtp_port) as smtp:
                smtp.ehlo()  # Say EHLO to server
                smtp.starttls(context=context)  # Puts the connection in TLS mode.
                smtp.ehlo()
                smtp.login(self.email_sender, self.email_password )
                #smtp.set_debuglevel(1)
                smtp.sendmail(self.email_sender, self.email_recepient, message.as_string())
                smtp.quit()
                logging.info('Email sent')

        except Exception as e:
            logging.error('Exception send_email: ' + str(e))

       



    

    