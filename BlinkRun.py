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
import datetime
import time
import os
import smtplib
import ssl

import queue






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


    def auth (self, userName, password, authenKey = None):
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
        logging.debug('get_sync_arm_info - {} '.format(sync_name ))
        return(self.blink.sync[sync_name].arm)

    def set_sync_arm (self, sync_name, armed=True):
        logging.debug('set_arm_sync = {}- {} '.format(sync_name, armed ))
        self.blink.sync[sync_name].arm = armed
        #self.blink.refresh()

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

    def get_camera_motion_enabled_info(self, camera_name):
        logging.debug('get_camera_motion_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].motion_enabled )

    def set_camera_motion_detect(self, camera_name, enabled=True):
        logging.debug('set_camera_motion_detect = {}- {} '.format(camera_name, enabled ))
        self.blink.cameras[camera_name].set_motion_detect(enabled)



    def get_camera_motion_detected_info(self, camera_name):
        logging.debug('get_camera_motion_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].motion_detected )

    def get_camera_temperatureC_info(self, camera_name):
        logging.debug('get_camera_temperatureC_info - {} '.format(camera_name ))
        return(self.blink.cameras[camera_name].temperature_c)


    def get_camera_recording_info(self, camera_name):
        logging.debug('get_camera_recording_info - {} '.format(camera_name ))
        return(0)
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

       



    

    