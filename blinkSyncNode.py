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
from  udiBlinkCameraNode import blink_camera



               
class blink_sync_module(udi_interface.Node):
   

        
    def __init__(self, polyglot, primary, address, name, sync_unit  ):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink SYNC INIT- {}'.format(name))
        self.nodeDefineDone = False
        self.sync_unit = sync_unit
        self.name = name
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

        self.node.setDriver('ST', 1, True, True)   
        logging.debug('Adding Cameras')
        for camera_unit in self.sync_unit.camera_list:
            camera_name  = camera_unit['name']
            tempCamera = self.sync_unit.cameras[camera_name]
            logging.debug('camera loop {}'.format(camera_name))
       ####  NEED to investigate further 
            tempCamera = camera_name
            cameraName = self.getValidName(str(camera_name))
            #cameraName = str(name)#.replace(' ','')
            nodeAdr = self.getValidAddress(str(camera_name))
            #nodeAdr = str(name).replace(' ','')[:14]
            logging.debug('Adding Camera {} {} {}'.format(self.address,nodeAdr, cameraName))
            blink_camera(self.poly, self.primary, nodeAdr, cameraName, tempCamera)
        self.nodeDefineDone = True


    def stop(self):
        logging.debug('stop - Cleaning up')

    
    def systemPoll (self, polltype):
        if self.nodeDefineDone:
            logging.debug('System Poll executing: {}'.format(polltype))

            if 'longPoll' in polltype:
                #Keep token current
                #self.node.setDriver('GV0', self.temp_unit, True, True)
                logging.debug('long poll')            
   
                
            if 'shortPoll' in polltype:
                self.heartbeat()
                logging.debug('short poll')    
                nodes = self.poly.getNodes()
                for nde in nodes:
                    if nde != 'setup':   # but not the controller node
                        pass
                        #nodes[nde].checkDataUpdate()



    def updateISYdrivers(self, level):
        logging.debug('Node updateISYdrivers')

        logging.debug('updateISYdrivers - setupnode DONE')

    def ISYupdate(self):
        pass

    def arm_all_cameras (self):
        pass

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

        

