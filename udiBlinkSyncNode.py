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
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, bat_V2isy, node_queue, wait_for_node_done


    def __init__(self, polyglot, primary, address, name, sync_unit, blinkSys  ):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink SYNC INIT- {}'.format(name))
        self.nodeDefineDone = False
        self.sync_unit = sync_unit
        self.name = name
        self.blink = blinkSys
        self.primary = primary
        self.address = address
        self.sync_node_camera_list = []
        self.n_queue = []  
        self.poly = polyglot
        #self.Parameters = Custom(polyglot, 'customparams')
        # subscribe to the events we want
        #polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        #polyglot.subscribe(polyglot.POLL, self.poll)
        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

             

        # start processing events and create add our controller node
        polyglot.ready()
        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        logging.info('Start {} sync module Node'.format(self.name))  
        time.sleep(1)
        self.nodeDefineDone = True




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
        time.sleep(2)
        while not self.nodeDefineDone or self.node == None or self.drivers == None:
            time.sleep(2)
            logging.info('Waiting for nodes to be created')

        if self.sync_unit == None: #no sync units used
            self.camera_list = self.blink.get_camera_list()
        else:
            self.camera_list = self.blink.get_sync_camera_list(self.sync_unit )

        logging.debug('Adding Cameras in list: {}'.format(self.camera_list))             
        for camera_name in self.camera_list:
            camera_unit = self.blink.get_camera_unit(camera_name)

            nodeName = self.getValidName(str(camera_name))
            #cameraName = str(name)#.replace(' ','')
            nodeAdr = self.getValidAddress(str(camera_name))
            #nodeAdr = str(name).replace(' ','')[:14]
            logging.info('Adding Camera {} {} {}'.format(self.address,nodeAdr, nodeName))
            blink_camera_node(self.poly, self.primary, nodeAdr, nodeName, camera_unit, self.blink)
            self.sync_node_camera_list.append(nodeAdr)
            

        self.nodeDefineDone = True
        self.BLINK_setDriver('GV1', self.bool2isy(self.blink.get_sync_online(self.sync_unit.name)))
        tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        self.BLINK_setDriver('GV2', self.bool2isy(tmp))

    def stop(self):
        logging.info('stop {} - Cleaning up'.format(self.name))


    def updateISYdrivers(self):
        logging.info('Sync updateISYdrivers - {}'.format(self.sync_unit.name))

        self.BLINK_setDriver('GV1', self.bool2isy(self.blink.get_sync_online(self.sync_unit.name)))
        tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        self.BLINK_setDriver('GV2', self.bool2isy(tmp))

  
    def ISYupdate(self, command=None):
        logging.info('Sync ISYupdate')
        self.blink.refresh_data()
        
        self.updateISYdrivers()

        

    def arm_all_cameras (self, command):
        arm_enable = (1 == int(command.get('value')) )
        logging.info('Sync arm_all_cameras:{} - {}'.format(self.sync_unit.name, arm_enable ))
        if self.sync_unit != None:
            self.BLINK_setDriver('GV2', self.bool2isy(arm_enable))
            self.blink.set_sync_arm(self.sync_unit.name,  arm_enable )
            if arm_enable:
                self.node.reportCmd('DON')
            else:
                self.node.reportCmd('DOF')
            #self.updateISYdrivers()
        else:
            camera_list = self.blink.get_camera_list()
            for camera in camera_list:
                self.blink.set_camera_arm(self, camera, arm_enable)

        time.sleep(3)
        self.blink.refresh_data()
        self.updateISYdrivers()
        nodes = self.poly.getNodes()
        for nde in self.sync_node_camera_list:
            logging.debug('updating node {} data'.format(nde))    
            nodes[nde].updateISYdrivers()
    id = 'blinksync'

    commands = { 'UPDATE'   : ISYupdate,
                 'QUERY'    : ISYupdate,
                 'ARMALL'   : arm_all_cameras
            

                }

    drivers= [ 
                {'driver': 'ST', 'value':0, 'uom':25},
                {'driver': 'GV1', 'value':0, 'uom':25}, # on line 
                {'driver': 'GV2', 'value':0, 'uom':25} # Armed


        ] 

        

