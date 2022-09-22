#!/usr/bin/env python3
import os
import time

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
from  BlinkCameraNode import blink_camera



               
class blink_sync_module(udi_interface.Node):
    id = 'blinksync'
    
    '''
       drivers = [
            'GV0' = TempC
            'GV1' = Low Temp Alarm
            'GV2' = high Temp Alarm 
            'GV3' = Humidity
            'GV4' = Low Humidity Alarm
            'GV5' = High Humidity Alarm
            'GV6' = BatteryLevel
            'GV7' = BatteryAlarm
            'GV8' = Online
            ]

    ''' 
        
    def __init__(self, polyglot, primary, address, name, blink):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink SYNC INIT- {}'.format(name))
        self.blink = blink   
        self.name = name
        self.primary = primary
        self.address = address
        self.poly = polyglot
        #self.Parameters = Custom(polyglot, 'customparams')
        # subscribe to the events we want
        #polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
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
        self.node.setDriver('ST', 1, True, True)
    
    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()

        self.nodeDefineDone = False
        logging.debug('Start {} sync module Node'.format(self.name))  


    

        #self.heartbeat()


    def start(self):        
        logging.debug('Sync module Start {}'.format(self.name))        
        for name, camera in self.blink.cameras.items():
            if camera.attributes['sync_module'] == self.name:
                tempCamera = self.blink.cameras[name]
                #cameraName = self.poly.getValidName(str(name))
                cameraName = str(name)#.replace(' ','')
                #nodeAdr = self.poly.getValidAddress(str(name))
                nodeAdr = str(name).replace(' ','')
                logging.debug('Adding Camera {} {} {}'.format(self.address,nodeAdr, cameraName))
                #logging.debug('types : {} {} {} {}'.format(type(self.primary), type(nodeAdr), type(cameraName), type(tempCamera)))
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

    commands = { 'UPDATE'   : ISYupdate,
                 'QUERY'    : ISYupdate,
                 'ARM_ALL'  : arm_all_cameras
            

                }

    drivers= [ 
                {'driver': 'GV1', 'value':0, 'uom':25}, # on line 
                {'driver': 'GV2', 'value':0, 'uom':25} # Armed


        ] 

        

