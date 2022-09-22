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



               
class blink_camera(udi_interface.Node):
    id = 'blinkcamera'
    def __init__(self, polyglot, primary, address, name, camera):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink INIT- {}'.format(name))
        self.camera = camera
        self.name = name
        self.poly = polyglot
      
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
       

        self.nodeDefineDone = True


    def stop(self):
        logging.debug('stop - Cleaning up')

    


    def updateISYdrivers(self, level):
        logging.debug('Node updateISYdrivers')
     
    
    def ISYupdate (self):
        pass 
    
    def snap_pitcure (self):
        pass

    def email_picture (self):
        pass

    def arm_camera (self):
        pass

    commands = { 'UPDATE': ISYupdate,
                 'ARM' : arm_camera,
                 'SNAP_PIC' : snap_pitcure,
                 'QUERY' : ISYupdate,
                #,'EMAIL_PIC' : email_picture,
                }


    drivers= [  {'driver': 'ST', 'value':0, 'uom':25},
                {'driver': 'GV0', 'value':0, 'uom':51},
                {'driver': 'GV1', 'value':0, 'uom':25}, # On line
                {'driver': 'GV2', 'value':0, 'uom':25}, # Battery
                {'driver': 'GV3', 'value':0, 'uom':25}, # Camera Type 
                {'driver': 'GV4', 'value':0, 'uom':25}, # Motion Detection Enabled
                {'driver': 'GV5', 'value':0, 'uom':58}, # Motion Detected
                {'driver': 'GV6', 'value':0, 'uom':58}, # Temp
                {'driver': 'GV7', 'value':0, 'uom':58}, # Recording
                {'driver': 'GV8', 'value':0, 'uom':58}, # TBD
                 ] 

        

