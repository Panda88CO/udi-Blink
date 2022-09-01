#!/usr/bin/env python3
import os
import time

try:
    import udi_interface
    logging = udi_interface.logging
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



               
class blink_sync_module(udi_interface.Node):

    def __init__(self, polyglot, primary, address, name, blink):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink INIT- {}'.format(name))
        self.blink = blink   
        self.name = name
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
        for name, camera in self.blink.cameras.items():
            if camera.attributes['sync_module'] == self.name:
                cameraName = name
                nodeName = camera.attributes['camera_id']
                self.blink_camera(self.poly, nodeName, nodeName, cameraName, self.blink
        self.nodeDefineDone = True


    def stop(self):
        logging.debug('stop - Cleaning up')

    
def systemPoll (self, polltype):
        if self.nodeDefineDone:
            logging.debug('System Poll executing: {}'.format(polltype))

            if 'longPoll' in polltype:
                #Keep token current
                #self.node.setDriver('GV0', self.temp_unit, True, True)
                try:
                    if not self.yoAccess.refresh_token(): #refresh failed
                        while not self.yoAccess.request_new_token():
                                time.sleep(60)
                    #logging.info('Updating device status')
                    nodes = self.poly.getNodes()
                    for nde in nodes:
                        if nde != 'setup':   # but not the controller node
                            nodes[nde].checkOnline()
                except Exception as e:
                    logging.debug('Exeption occcured : {}'.format(e))
   
                
            if 'shortPoll' in polltype:
                self.heartbeat()
                nodes = self.poly.getNodes()
                for nde in nodes:
                    if nde != 'setup':   # but not the controller node
                        nodes[nde].checkDataUpdate()



    def updateISYdrivers(self, level):
        logging.debug('Node updateISYdrivers')
        params = []
        if level == 'all':
            params = self.ISYparams
            if params:
                for key in params:
                    info = params[key]
                    if info != {}:
                        value = self.TPW.getISYvalue(key, self.id)
                        #logging.debug('Update ISY drivers :' + str(key)+ ' ' + info['systemVar']+ ' value:' + str(value) )
                        self.setDriver(key, int(value), report = True, force = True)      
        elif level == 'critical':
            params = self.ISYcriticalParams
            if params:
                for key in params:
                    value = self.TPW.getISYvalue(key, self.id)
                    #logging.debug('Update ISY drivers :' + str(key)+ ' value: ' + str(value) )
                    self.setDriver(key, int(value), report = True, force = True)        

        else:
           logging.debug('Wrong parameter passed: ' + str(level))
        logging.debug('updateISYdrivers - setupnode DONE')



    def arm_all_cameras (self):
        pass

    commands = { 'UPDATE': ISYupdate
                ,'ARM_ALL' : arm_all_cameras
            

                }

    if PG_CLOUD_ONLY:
        drivers= [{'driver': 'GV1', 'value':0, 'uom':51}
                 ,{'driver': 'GV2', 'value':0, 'uom':25}
                 ,{'driver': 'GV3', 'value':0, 'uom':25}
                 ,{'driver': 'GV4', 'value':0, 'uom':25}
                 ,{'driver': 'GV5', 'value':0, 'uom':58}
                 ,{'driver': 'GV6', 'value':0, 'uom':58}
                 ,{'driver': 'GV7', 'value':0, 'uom':58}
                 ,{'driver': 'GV8', 'value':0, 'uom':58}
                 ,{'driver': 'GV9', 'value':0, 'uom':58}
                 ,{'driver': 'GV10', 'value':0, 'uom':58}
                 ,{'driver': 'GV11', 'value':0, 'uom':58}
                 ,{'driver': 'GV12', 'value':0, 'uom':58}

        ] 

        
