#!/usr/bin/env python3
import os
import time
import re
import BlinkSystem

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
from  udiBlinkCameraNode import blink_camera_node


               
class blink_sync_node(udi_interface.Node):
    #import udiFunctions 
    def __init__(self, polyglot, primary, address, name, sync_unit, blinkSys  ):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink SYNC INIT- {}'.format(name))
        self.nodeDefineDone = False
        self.sync_unit = sync_unit
        self.name = name
        self.blink = blinkSys
        self.primary = primary
        self.address = address
        self.poly = polyglot
        #self.Parameters = Custom(polyglot, 'customparams')
        # subscribe to the events we want
        #polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        #polyglot.subscribe(polyglot.POLL, self.poll)
        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        self.n_queue = []        

        # start processing events and create add our controller node
        polyglot.ready()
        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        logging.debug('Start {} sync module Node'.format(self.name))  
        self.nodeDefineDone = True


    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()


    def bool2isy(self, val):
        if val:
            return(1)
        else:
            return(0)



    def getValidName(self, name):
        name = bytes(name, 'utf-8').decode('utf-8','ignore')
        return re.sub(r"[^A-Za-z0-9_ ]", "", name)

    # remove all illegal characters from node address
    def getValidAddress(self, name):
        name = bytes(name, 'utf-8').decode('utf-8','ignore')
        return re.sub(r"[^A-Za-z0-9_]", "", name.lower()[:14])
    
        #self.heartbeat()


    def start(self):        
        logging.debug('Sync module Start {}'.format(self.name))
        while not self.nodeDefineDone:
            time.sleep(2)
            logging.info('Waiting for nodes to be created')

        if self.sync_unit == None: #no sync units used
            camera_list = self.blink.get_camera_list()
        else:
            camera_list = self.blink.get_sync_camera_list(self.sync_unit )

        logging.debug('Adding Cameras in list: {}'.format(camera_list))             
        for camera_name in camera_list:
            camera_unit = self.blink.get_camera_unit(camera_name)

            nodeName = self.getValidName(str(camera_name))
            #cameraName = str(name)#.replace(' ','')
            nodeAdr = self.getValidAddress(str(camera_name))
            #nodeAdr = str(name).replace(' ','')[:14]
            logging.debug('Adding Camera {} {} {}'.format(self.address,nodeAdr, nodeName))
            blink_camera_node(self.poly, self.primary, nodeAdr, nodeName, camera_unit, self.blink)
        self.nodeDefineDone = True
        self.node.setDriver('GV1', self.bool2isy(self.blink.get_sync_online(self.sync_unit.name)), True, True)
        tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        self.node.setDriver('GV2', self.bool2isy(tmp['armed']), True, True)

    def stop(self):
        logging.debug('stop - Cleaning up')




    def updateISYdrivers(self):
        logging.debug('Sync updateISYdrivers - {}'.format(self.sync_unit.name))
        self.node.setDriver('GV1', self.bool2isy(self.blink.get_sync_online(self.sync_unit.name)), True, True)
        tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        self.node.setDriver('GV2', self.bool2isy(tmp['armed']))

    def ISYupdate(self):
        logging.debug('Sync ISYupdate')
        self.updateISYdrivers('all')
        

    def arm_all_cameras (self, arm_enable):
        logging.debug('Sync arm_all_cameras')
        self.blink.set_sync_arm(self.sync_unit.name,  arm_enable )
        self.updateISYdrivers()

    id = 'blinksync'

    commands = { 'UPDATE'   : ISYupdate,
                 'QUERY'    : ISYupdate,
                 'ARM_ALL'  : arm_all_cameras
            

                }

    drivers= [ 
                {'driver': 'ST', 'value':0, 'uom':25},
                {'driver': 'GV1', 'value':0, 'uom':25}, # on line 
                {'driver': 'GV2', 'value':0, 'uom':25} # Armed


        ] 

        

