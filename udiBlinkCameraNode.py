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
        self.blink = blinkSys
        self.pic_email_enabled = False
        self.nodeDefineDone = False
        self.poly = polyglot
        self.cameraType= {  'mini' : 0, #mini/owl
                            'doorbell': 1, #doorbell/lotus
                            'Blink Outdoor':2, #outdoor/catalena
                            'outdoorOld1':4,
                            'outdoorOld2':5,
                            'indoorOld':3,
                            'default':99,
                             }


        #polyglot.subscribe(polyglot.POLL, self.poll)
        polyglot.subscribe(polyglot.START, self.start, self.address)
        polyglot.subscribe(polyglot.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
        self.n_queue = []        

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
                
        logging.debug('Start {} camera module Node'.format(self.name))               
        while not self.nodeDefineDone:
            logging.debug('camera - wait to node completed')
            time.sleep(2)

        self.updateISYdrivers()


    def stop(self):
        logging.debug('stop - Cleaning up')

    def getCameraData(self):
        #data is updated 
        logging.debug('Node getCameraData')

    def updateISYdrivers(self):
        logging.debug('Camera updateISYdrivers - {}'.format(self.camera.name))
        bat_info = self.blink.get_camera_battery_info(self.camera.name)
        logging.debug(bat_info)
        self.node.setDriver('GV1', self.bat2isy(bat_info['battery']))
        if None == bat_info['battery_voltage']:
            self.node.setDriver('GVn2', 0)
        else:
            self.node.setDriver('GV2', bat_info['battery_voltage'])
        self.node.setDriver('GV3', self.cameraType[self.blink. get_camera_type_info(self.camera.name)])
        mot_info = self.blink.get_camera_motion_info(self.camera.name)
        logging.debug(mot_info)
        self.node.setDriver('GV4', self.bool2isy(mot_info['motion_enabled']))
        self.node.setDriver('GV5', self.bool2isy(mot_info['motion_detected']))
        temp_info = self.blink.get_camera_temperatureC_info(self.camera.name)
        if  None ==  temp_info['temp_c']:
            self.node.setDriver('GV6', 0, True, True,  25)
        elif 'k' == self.blink.temp_unit:
             self.node.setDriver('GV6', temp_info['temp_c'], True, True, 26)
        elif 'f' == self.blink.temp_unit:
             self.node.setDriver('GV6', temp_info['temp_c'], True, True, 17)
        else:
             self.node.setDriver('GV6', temp_info['temp_c'], True, True, 4)
        self.node.setDriver('GV7', self.blink.get_camera_recording_info(self.camera.name))
        self.node.setDriver('GV8', self.bool2isy(self.pic_email_enabled))

    
    def ISYupdate (self, command = None):
        self.updateISYdrivers()
    
    def snap_pitcure (self, command=None):
        pass

    def enable_email_picture (self, command):
        status  = (1 == int(command.get('value')) )
        self.pic_email_enabled = (status)

    def arm_camera (self, command):
        arm_enable = (1 == int(command.get('value')) )
        logging.debug(' arm_cameras: {} - {}'.format(self.camera.name, arm_enable ))
        self.blink.set_camera_arm(self.camera.name,  arm_enable )
        self.updateISYdrivers()
        pass

    id = 'blinkcamera'

    commands = { 'UPDATE': ISYupdate,
                 'ARM' : arm_camera,
                 'SNAPPIC' : snap_pitcure,
                 'QUERY' : ISYupdate,
                 'EMAILPIC' : enable_email_picture,
                }


    drivers= [  {'driver': 'ST', 'value':0, 'uom':25},
                {'driver': 'GV1', 'value':99, 'uom':25}, # Battery
                {'driver': 'GV2', 'value':99, 'uom':25}, # Battery
                {'driver': 'GV3', 'value':99, 'uom':25}, # Camera Type 
                {'driver': 'GV4', 'value':99, 'uom':25}, # Motion Detection Enabled
                {'driver': 'GV5', 'value':99, 'uom':25}, # Motion Detected
                {'driver': 'GV6', 'value':0, 'uom':17}, # TempC
                {'driver': 'GV7', 'value':99, 'uom':25}, # Recording
                {'driver': 'GV8', 'value':0, 'uom':25}, # TBD
                 ] 

        

