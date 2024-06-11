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
  
        self.n_queue = []  
        self.poly = polyglot
        #self.Parameters = Custom(polyglot, 'customparams')
        # subscribe to the events we want
        #polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.POLL, self.poll)
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

        self.sync_unit
        self.nodeDefineDone = True
        self.BLINK_setDriver('ST', self.bool2isy(self.blink.get_sync_online(self.sync_unit.name)))


    def stop(self):
        logging.info('stop {} - Cleaning up'.format(self.name))


    def updateISYdrivers(self):
        
        if self.nodeDefineDone:
            logging.info('Sync updateISYdrivers - {}'.format(self.sync_unit.name))
            self.BLINK_setDriver('GV1', self.bool2isy(self.blink.get_sync_online(self.sync_unit.name)))


  
    def ISYupdate(self, command=None):
        logging.info('Sync ISYupdate')
        self.blink.refresh()        
        self.updateISYdrivers()


    def poll(self, polltype):
        if self.nodeDefineDone:
            logging.info('System Poll executing: {}'.format(polltype))

            if 'longPoll' in polltype:
                #Keep token current
                #self.node.setDriver('GV0', self.temp_unit, True, True)
                try:
                    self.updateISYdriver()
                except Exception as e:
                    logging.debug('Exeption occcured : {}'.format(e))
   
                
            if 'shortPoll' in polltype:
                logging.info('Currently no function for shortPoll')
        else:
            logging.info('System Poll - Waiting for all nodes to be added')        


    id = 'blinksync'

    commands = { 'UPDATE'   : ISYupdate,

                # 'ARMALL'   : arm_all_cameras
            

                }

    drivers= [ 
                {'driver': 'ST', 'value':0, 'uom':25}, # on line 
                #{'driver': 'GV1', 'value':0, 'uom':25},



        ] 

        

