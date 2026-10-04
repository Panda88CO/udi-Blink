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
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, connection2isy, bat_V2isy, node_queue, wait_for_node_done

    id = 'BLINKCAMERAC' 
    drivers= [  {'driver': 'ST' , 'value':99,  'uom':25}, # Motion Detection Status
                {'driver': 'GV0', 'value':0, 'uom':25},  # Connected / Online
                {'driver': 'GV1', 'value':99, 'uom':25}, # Battery
                #{'driver': 'GV2', 'value':99, 'uom':25}, # Battery
                {'driver': 'GV3', 'value':99, 'uom':25}, # Camera Type 
                #{'driver': 'GV4', 'value':99, 'uom':25}, # Motion Detection Enabled
                {'driver': 'GV5', 'value':99, 'uom':25}, # Motion Detected
                {'driver': 'CLITEMP', 'value':0, 'uom':4}, # Temp
                #{'driver': 'GV7', 'value':99, 'uom':25}, # Recording
                #{'driver': 'GV8', 'value':0, 'uom':25}, # Email Picture Eanble
                {'driver': 'TIME', 'value':0, 'uom':151},
                 ] 
        
    cameraType= {  'mini' : 0, #mini/owl
                    'doorbell': 1, #doorbell/lotus/tulip/freesia
                    'Blink Outdoor':2, #outdoor/catalena
                    'XT-2':3,
                    'wiredFloodLight':4,
                    'gen3':5,
                    'outdoor4' : 6, #outdoor v4
                    'mini2' : 7, #hawk
                    'gen2' : 8, #hawk
                    'floodlight' : 9, #trogon
                    'mini2K+' : 10, #chickade
                    'outdoor2K+' : 11, #sonoran
                    'default':99,
                     }

    def __new__(cls, polyglot, primary, address, name, camera, blinkSys, *args, **kwargs):
        if cls is blink_camera_node:
            cam_name = getattr(camera, 'name', str(camera))
            if hasattr(blinkSys, 'camera_supports_temperature') and not blinkSys.camera_supports_temperature(cam_name):
                return blink_camera_no_temp_node(polyglot, primary, address, name, camera, blinkSys, *args, **kwargs)
        return super().__new__(cls)

    def __init__(self, polyglot, primary, address, name, camera, blinkSys):
        super().__init__( polyglot, primary, address, name)   
        # logging.debug('blink INIT- {}'.format(name))

        self.camera = camera
        self.name = name
        self.node = None
        self.blink = blinkSys
        self.temp_unit = self.blink.get_temp_unit()
        if self.temp_unit == 'F':
            self.id = 'BLINKCAMERAF'
            for d in self.drivers:
                if d['driver'] == 'CLITEMP':
                    d['uom'] = 17
        else:
            self.id = 'BLINKCAMERAC'
            for d in self.drivers:
                if d['driver'] == 'CLITEMP':
                    d['uom'] = 4

        self.pic_email_enabled = False
        self.nodeDefineDone = False
        self.poly = polyglot

        self.n_queue = []     
        #polyglot.subscribe(polyglot.POLL, self.poll)
        self.poly.subscribe(polyglot.START, self.start, self.address)
        self.poly.subscribe(polyglot.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
           

        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        self.nodeDefineDone = True
        self.updateISYdrivers()

    def start(self):   
        logging.info('Start {} camera module Node'.format(self.name))
        while not self.nodeDefineDone:
            time.sleep(0.1)
        self.updateISYdrivers()


    def stop(self):
        logging.info('stop {} - Cleaning up '.format(self.name))

    def getCameraData(self):
        #data is updated 
        # logging.debug('Node getCameraData')
        pass

    def updateISYdrivers(self):
        if self.drivers != [] and self.nodeDefineDone:
            try:
                logging.info('Camera updateISYdrivers - {}'.format(self.camera.name))
                if self.camera.name not in self.blink.cameras:
                    logging.warning('Camera %s not found in Blink system - skipping TIME update', self.camera.name)
                    return

                camera_data = self.blink.get_camera_data(self.camera.name)
                if not camera_data:
                    logging.warning('Camera %s: No data/attributes received from Blink - skipping TIME update', self.camera.name)
                    return

                temp = self.blink.get_camera_status(self.camera.name)
                if temp is None:
                    logging.warning('Camera %s status is None - skipping TIME update', self.camera.name)
                    return
                # logging.debug('get_camera_info: {}'.format(temp))
                self.BLINK_setDriver('GV0', self.connection2isy(str(temp)))

                temp = self.blink.get_camera_arm_info(self.camera.name)
                # logging.debug('ST : {}'.format(temp))
                self.BLINK_setDriver('ST', self.bool2isy(temp))

                temp = self.blink.get_camera_battery_info(self.camera.name)
                # logging.debug('GV1 : {}'.format(temp))          
                self.BLINK_setDriver('GV1', self.bat2isy(temp))

                cam_type = self.blink.get_camera_type_info(self.camera.name)
                temp = int(self.cameraType.get(cam_type, 99))
                # logging.debug('GV3 : {}'.format(temp))
                self.BLINK_setDriver('GV3', temp)

                temp = self.blink.get_camera_motion_detected_info(self.camera.name)
                # logging.debug('GV5 : {}'.format(temp))            
                self.BLINK_setDriver('GV5', self.bool2isy(temp))

                temp_info = self.blink.get_camera_temperatureC_info(self.camera.name)
                # logging.debug('CLITEMP : {}'.format(temp_info))
                if temp_info is not None:
                    if 'F' == self.blink.temp_unit or 'f' == self.blink.temp_unit:
                        self.BLINK_setDriver('CLITEMP', (temp_info*9/5)+32, 17)
                    else:
                        self.BLINK_setDriver('CLITEMP', temp_info, 4)

                # Only update TIME if all camera data was received and drivers updated with no errors
                self.BLINK_setDriver('TIME', int(time.time()), 151)
            except Exception as e:
                logging.error('Error updating ISY drivers for camera %s: %s', self.camera.name, e)
        else:
            # logging.debug('Drivers not ready')
            pass
    
    def ISYupdate (self, command = None):
        logging.info(' ISYupdate: {}'.format(self.camera.name ))
        if not self.blink.refresh():
            logging.warning('Blink refresh failed for camera %s - skipping driver update', self.camera.name)
            return
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
        #logging.debug('temp = {}'.format(temp))
        temp = self.blink.set_camera_motion_detect(self.camera.name,  motion_enable )
        logging.debug('blink.set_camera_motion_detect({}, {}):{}'.format(self.camera.name,  motion_enable, self.blink.get_camera_data(self.camera.name ) ))
        self.blink.refresh()
        time.sleep(3)
        self.updateISYdrivers()

    def arm_camera (self, command):
        try:

            value = int(command.get('value'))
            arm_enable = (1 == int(command.get('value')) )
            logging.info(' arm_cameras: {} - {}'.format(self.camera.name, arm_enable))

            temp = self.blink.set_camera_arm(self.camera.name,  arm_enable )
            time.sleep(1)
            logging.debug('blink.set_camera_arm({}, {}):{}'.format(self.camera.name,  arm_enable,  self.blink.get_camera_data(self.camera.name )))
            if arm_enable:
                self.node.reportCmd('DON')
            else:
                self.node.reportCmd('DOF')
            self.BLINK_setDriver('ST', value)
            self.blink.refresh()
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




    commands = { 'UPDATE': ISYupdate,
                 'ARM' : arm_camera,
                 #'MOTION' : motion_detection,
                 'SNAPPIC' : snap_pitcure,
                 'SNAPVIDEO' : snap_video,
                 #'EMAILPIC' : enable_email_picture,
                }


class blink_camera_no_temp_node(udi_interface.Node):
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, connection2isy, bat_V2isy, node_queue, wait_for_node_done

    id = 'BLINKCAMERA'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25},  # Motion Detection Status
        {'driver': 'GV0', 'value': 0, 'uom': 25},  # Connected / Online
        {'driver': 'GV1', 'value': 99, 'uom': 25},  # Battery
        {'driver': 'GV3', 'value': 99, 'uom': 25},  # Camera Type
        {'driver': 'GV5', 'value': 99, 'uom': 25},  # Motion Detected
        {'driver': 'TIME', 'value': 0, 'uom': 151},
    ]

    def __init__(self, polyglot, primary, address, name, camera, blinkSys):
        super().__init__(polyglot, primary, address, name)
        self.camera = camera
        self.name = name
        self.node = None
        self.blink = blinkSys
        self.supports_temperature = False
        self.id = 'BLINKCAMERA'
        self.pic_email_enabled = False
        self.nodeDefineDone = False
        self.poly = polyglot
        self.cameraType = blink_camera_node.cameraType
        self.n_queue = []
        self.poly.subscribe(polyglot.START, self.start, self.address)
        self.poly.subscribe(polyglot.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        self.nodeDefineDone = True
        self.updateISYdrivers()

    def start(self):
        logging.info('Start {} camera module Node (no temperature)'.format(self.name))
        while not self.nodeDefineDone:
            time.sleep(0.1)
        self.updateISYdrivers()

    def stop(self):
        logging.info('stop {} - Cleaning up '.format(self.name))

    def getCameraData(self):
        pass

    def updateISYdrivers(self):
        if self.drivers != [] and self.nodeDefineDone:
            try:
                logging.info('Camera updateISYdrivers (no temp) - {}'.format(self.camera.name))
                if self.camera.name not in self.blink.cameras:
                    logging.warning('Camera %s not found in Blink system - skipping TIME update', self.camera.name)
                    return

                camera_data = self.blink.get_camera_data(self.camera.name)
                if not camera_data:
                    logging.warning('Camera %s: No data/attributes received from Blink - skipping TIME update', self.camera.name)
                    return

                temp = self.blink.get_camera_status(self.camera.name)
                if temp is None:
                    logging.warning('Camera %s status is None - skipping TIME update', self.camera.name)
                    return
                self.BLINK_setDriver('GV0', self.connection2isy(str(temp)))

                temp = self.blink.get_camera_arm_info(self.camera.name)
                self.BLINK_setDriver('ST', self.bool2isy(temp))

                temp = self.blink.get_camera_battery_info(self.camera.name)
                self.BLINK_setDriver('GV1', self.bat2isy(temp))

                cam_type = self.blink.get_camera_type_info(self.camera.name)
                temp = int(self.cameraType.get(cam_type, 99))
                self.BLINK_setDriver('GV3', temp)

                temp = self.blink.get_camera_motion_detected_info(self.camera.name)
                self.BLINK_setDriver('GV5', self.bool2isy(temp))

                # Note: CLITEMP is not defined for this node, omitted completely
                self.BLINK_setDriver('TIME', int(time.time()), 151)
            except Exception as e:
                logging.error('Error updating ISY drivers for camera %s: %s', self.camera.name, e)

    def ISYupdate(self, command=None):
        logging.info(' ISYupdate: {}'.format(self.camera.name))
        if not self.blink.refresh():
            logging.warning('Blink refresh failed for camera %s - skipping driver update', self.camera.name)
            return
        self.updateISYdrivers()

    def snap_pitcure(self, command=None):
        logging.info(' snap_pitcure: {}'.format(self.camera.name))
        self.blink.snap_picture(self.camera.name)

    def snap_video(self, command=None):
        logging.info(' snap_pitcure: {}'.format(self.camera.name))
        self.blink.snap_video(self.camera.name)

    def arm_camera(self, command):
        try:
            value = int(command.get('value'))
            arm_enable = (1 == int(command.get('value')))
            logging.info(' arm_cameras: {} - {}'.format(self.camera.name, arm_enable))
            temp = self.blink.set_camera_arm(self.camera.name, arm_enable)
            time.sleep(1)
            if arm_enable:
                self.node.reportCmd('DON')
            else:
                self.node.reportCmd('DOF')
            self.BLINK_setDriver('ST', value)
            self.blink.refresh()
            time.sleep(3)
            self.updateISYdrivers()
        except Exception as e:
            logging.debug('Exception arm_camera: {}'.format(e))

    def enable_email_picture(self, command):
        status = (1 == int(command.get('value')))
        logging.info(' enable_email_picture: {} - {}'.format(self.camera.name, status))
        self.pic_email_enabled = status

    def enable_email_video(self, command):
        status = (1 == int(command.get('value')))
        logging.info(' enable_email_video: {} - {}'.format(self.camera.name, status))
        self.pic_email_enabled = status

    commands = {
        'UPDATE': ISYupdate,
        'ARM': arm_camera,
        'SNAPPIC': snap_pitcure,
        'SNAPVIDEO': snap_video,
    }


        

