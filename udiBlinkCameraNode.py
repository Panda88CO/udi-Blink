#!/usr/bin/env python3
import os
import time
import re

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



               
class blink_camera_node(udi_interface.Node):
    #import udiFunctions

    def __init__(self, polyglot, primary, address, name, camera, blinkSys):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink INIT- {}'.format(name))
        self.camera = camera
        self.name = name
        self.node = None
        self.blink = blinkSys
        self.pic_email_enabled = False
        self.nodeDefineDone = False
        self.poly = polyglot
        self.cameraType= {  'mini' : 0, #mini/owl
                            'doorbell': 1, #doorbell/lotus
                            'Blink Outdoor':2, #outdoor/catalena
                            'outdoorOld1':4,
                            'XT-2':3,
                            'indoorOld':5,
                            'default':99,
                             }

        self.n_queue = []     
        #polyglot.subscribe(polyglot.POLL, self.poll)
        polyglot.subscribe(polyglot.START, self.start, self.address)
        polyglot.subscribe(polyglot.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
           

        # start processing events and create add our controller node
        polyglot.ready()
        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        self.nodeDefineDone = True
        
    
    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()



    def bat2isy(self, bat_status):
        if 'ok'  == bat_status:
            return (0)
        elif None == bat_status:
            return(10)
        else:
            return(1)

        #self.heartbeat()

    def bool2isy(self, val):
        if val:
            return(1)
        else:
            return(0)

    def start(self):   
        time.sleep(2)
        logging.info('Start {} camera module Node'.format(self.name))               
        while not self.nodeDefineDone or self.node == None or self.drivers == None:
            logging.debug('camera - wait to node completed')
            time.sleep(2)
        
        self.updateISYdrivers()


    def stop(self):
        logging.info('stop {} - Cleaning up '.format(self.name))

    def getCameraData(self):
        #data is updated 
        logging.debug('Node getCameraData')

    def updateISYdrivers(self):
        logging.info('Camera updateISYdrivers - {}'.format(self.camera.name))

        self.node.setDriver('GV0', self.bool2isy(self.blink.get_camera_arm_info(self.camera.name)), True, True)
        self.node.setDriver('GV1', self.bat2isy(self.blink.get_camera_battery_info(self.camera.name)), True, True)
        if None == self.blink.get_camera_battery_voltage_info(self.camera.name):
            self.node.setDriver('GV2', 99, True, True, 25)
        else:
            self.node.setDriver('GV2', self.blink.get_camera_battery_voltage_info(self.camera.name), True, True, 72)
        self.node.setDriver('GV3', self.cameraType[self.blink.get_camera_type_info(self.camera.name)])
        #self.node.setDriver('GV4', self.bool2isy(self.blink.get_camera_motion_enabled_info(self.camera.name)), True, True)
        self.node.setDriver('GV5', self.bool2isy(self.blink.get_camera_motion_detected_info(self.camera.name)), True, True)
        temp_info = self.blink.get_camera_temperatureC_info(self.camera.name)

        if  None ==  temp_info:
            self.node.setDriver('GV6', 0, True, True,  25)
        elif 'K' == self.blink.temp_unit or 'k' == self.blink.temp_unit:
            self.node.setDriver('GV6', temp_info+273.15, True, True, 26)
        elif 'F' == self.blink.temp_unit or 'f' == self.blink.temp_unit:
            self.node.setDriver('GV6', (temp_info*9/5)+32, True, True, 17)
        else:
             self.node.setDriver('GV6', temp_info, True, True, 4)
        #self.node.setDriver('GV7', self.blink.get_camera_recording_info(self.camera.name))
        #self.node.setDriver('GV8', self.bool2isy(self.pic_email_enabled))

    
    def ISYupdate (self, command = None):
        logging.info(' ISYupdate: {}'.format(self.camera.name ))
        self.blink.refresh_data()
        logging.debug('Camera {} data: {}'.format(self.camera.name,  self.blink.get_camera_data(self.camera.name )))
        self.updateISYdrivers()
    
    def snap_pitcure (self, command=None):
        logging.info(' snap_pitcure: {}'.format(self.camera.name))
        self.blink.snap_picture(self.camera.name)
     
        
    def snap_video (self, command=None):
        logging.info(' snap_pitcure: {}'.format(self.camera.name))
        self.blink.snap_video(self.camera.name)
             
    def motion_detection (self, command):
        motion_enable = ('1' == int(command.get('value')) )
        logging.info(' arm_cameras: {} - {}'.format(self.camera.name, motion_enable ))
        logging.debug('temp = {}'.format(temp))
        temp = self.blink.set_camera_motion_detect(self.camera.name,  motion_enable )
        logging.debug('blink.set_camera_motion_detect({}, {}):{}'.format(self.camera.name,  motion_enable, self.blink.get_camera_data(self.camera.name ) ))
        self.blink.refresh_data()
        time.sleep(3)
        self.updateISYdrivers()

    def arm_camera (self, command):
        try:
            value = int(command.get('value'))
            arm_enable = (1 == int(command.get('value')) )
            logging.info(' arm_cameras: {} - {}'.format(self.camera.name, arm_enable))

            temp = self.blink.set_camera_arm(self.camera.name,  arm_enable )
            logging.debug('temp = {}'.format(temp))
            logging.debug('blink.set_camera_arm({}, {}):{}'.format(self.camera.name,  arm_enable,  self.blink.get_camera_data(self.camera.name )))
            if arm_enable:
                self.node.reportCmd('DON')
            else:
                self.node.reportCmd('DOF')
            self.node.setDriver('GV0', value, True, True)
            self.blink.refresh_data()
            time.sleep(3)
            self.updateISYdrivers()
        except Exception as e:
            logging.debug('Exception arm_camera: {}'.format(e))

    def enable_email_picture (self, command):
        status  = (1 == int(command.get('value')) )     
        logging.info(' enable_email_picture: {} - {}'.format(self.camera.name, status ))
        self.pic_email_enabled = (status)

    def enable_email_video (self, command):
        status  = (1 == int(command.get('value')) )     
        logging.info(' enable_email_video: {} - {}'.format(self.camera.name, status ))
        self.pic_email_enabled = (status)


    id = 'blinkcamera'

    commands = { 'UPDATE': ISYupdate,
                 'ARM' : arm_camera,
                 #'MOTION' : motion_detection,
                 'SNAPPIC' : snap_pitcure,
                 'SNAPVIDEO' : snap_video,
                 'QUERY' : ISYupdate,
                 #'EMAILPIC' : enable_email_picture,
                }


    drivers= [  {'driver': 'ST' , 'value':0,  'uom':25},
                {'driver': 'GV0', 'value':99, 'uom':25},  #Arm status
                {'driver': 'GV1', 'value':99, 'uom':25}, # Battery
                {'driver': 'GV2', 'value':99, 'uom':25}, # Battery
                {'driver': 'GV3', 'value':99, 'uom':25}, # Camera Type 
                #{'driver': 'GV4', 'value':99, 'uom':25}, # Motion Detection Enabled
                {'driver': 'GV5', 'value':99, 'uom':25}, # Motion Detected
                {'driver': 'GV6', 'value':99, 'uom':25}, # TempC
                #{'driver': 'GV7', 'value':99, 'uom':25}, # Recording
                #{'driver': 'GV8', 'value':0, 'uom':25}, # Email Picture Eanble
                 ] 

        

