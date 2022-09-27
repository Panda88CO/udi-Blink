#!/usr/bin/env python3

from udiBlinkSyncNode import blink_sync_node
from BlinkSystem import blink_system
import sys
import time 
import re
import os

try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    if (os.path.exists('./debug1.log')):
        os.remove('./debug1.log')
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

#from os import truncate



 

class BlinkSetup (udi_interface.Node):
    #import udiFunctions
    def  __init__(self, polyglot, primary, address, name):
        super().__init__( polyglot, primary, address, name)  
        
        logging.setLevel(10)
        self.blink = blink_system()
        self.nodeDefineDone = False
        self.handleParamsDone = False
        self.paramsProcessed = False
        self.poly = polyglot
        self.handleParamsDone = False
        self.address = address
        self.name = name
        self.n_queue = []
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handleParams)
        self.poly.subscribe(self.poly.POLL, self.systemPoll)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
        self.poly.subscribe(self.poly.CONFIGDONE, self.validate_params)
 
        self.hb = 0
        self.userParam = ['TEMP_UNIT', 'USERNAME','PASSWORD', 'AUTH_KEY', 'SYNC_UNITS' ]
        self.Parameters = Custom(self.poly, 'customparams')
        self.Notices = Custom(self.poly, 'notices')
        logging.debug('BlinkSetup init')
        logging.debug('self.address : ' + str(self.address))
        logging.debug('self.name :' + str(self.name))   
        self.poly.ready()
        self.poly.addNode(self)
        self.wait_for_node_done()

        self.node = self.poly.getNode(self.address)
        logging.debug('node: {}'.format(self.node))
        #self.node.setDriver('ST', 1, True, True)
        logging.debug('BlinkSetup init DONE')
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
    

    def validate_params(self):
        logging.debug('validate_params: {}'.format(self.Parameters.dump()))
        self.paramsProcessed = True    

    def strip_syncUnitStringtoList(self, syncString):
        tmp = re.sub(r"[^A-Za-z0-9_,]", "", syncString)
        #logging.debug(tmp)
        tmp = tmp.split(',')
        #logging.debug(tmp)
        unitList = []
        for syncunit in tmp:
            unitList.append(syncunit.upper())
        return(unitList)

    def start (self):
        logging.info('Executing start - BlinkSetup')
        logging.setLevel(10)
        while not self.paramsProcessed or not self.nodeDefineDone:
            logging.debug('Waiting for setup to complete')
            time.sleep(2)
        self.poly.updateProfile()
        self.syncUnits = self.strip_syncUnitStringtoList(self.syncUnitString)
        #logging.debug('syncUnits / syncString: {} - {}'.format(self.syncUnits, self.syncUnitString))

        self.node.setDriver('ST', 1, True, True)
        #time.sleep(5)
        logging.debug('nodeDefineDone {}'.format(self.nodeDefineDone))
        if self.userName == None or self.userName == '' or self.password==None or self.password=='':
            logging.error('username and password must be provided to start node server')
            self.poly.Notices['un'] = 'username and password must be provided to start node server'
            exit() 
        else:
            success = self.blink.blink_auth(self.userName,self.password, self.authKey )
            if 'AuthKey' == success:
                logging.error('AuthKey required - please add to config')
                self.poly.Notices['ak'] = 'username and password must be provided to start node server'
            elif 'no login' == success:
                logging.error('Login Failed')
                self.poly.Notices['un'] = 'please check username and password - do not seem to work '   
            else:
                logging.info('Accessing Blink completed ')

            self.add_sync_nodes()


        #self.poly.updateProfile()



    def add_sync_nodes (self):
        logging.debug('Adding sync units: {}'.format(self.syncUnits ))
        if self.syncUnits!= None :
            if not 'NONE' in self.syncUnits:
                for sync_name in self.syncUnits:                    
                    sync_unit = self.blink.get_sync_unit(sync_name)
                    address = self.getValidAddress(str(sync_name))
                        #address = str(sync).replace(' ','')[:14]
                    name = 'Blink_' + str(sync_name)
                    nodename = self.getValidName(str(name))
                    #name = str(sync).replace(' ','')
                    #nodename = 'BlinkSync ' + str(sync)
                    logging.info('Adding sync unit {} as {} , {}'.format(sync_unit, address, nodename))
                    if not blink_sync_node(self.poly, address, address, nodename, sync_unit, self.blink ):
                        logging.error('Failed to create Sync_node {}'.format(sync_name))
            elif self.syncUnits != [] or 'NONE' in self.syncUnits:
                logging.info('No sync specified - create dummy node {} for all cameras '.format('nosync')) 
                if not blink_sync_node(self.poly, 'nosync', 'nosync', 'Blink Cameras', None, self.blink ):
                    logging.error('Failed to create dummy node {}'.format('nosync')) 
        self.poly.updateProfile()


    def stop(self):
        logging.info('Stop Called:')

        if 'self.node' in locals():
            self.node.setDriver('ST', 0, True, True)
            #nodes = self.poly.getNodes()
            #for node in nodes:
            #    if node != 'setup':   # but not the controller node
            #        nodes[node].setDriver('ST', 0, True, True)
            time.sleep(2)

        self.poly.stop()
        exit()
 

    def heartbeat(self):
        logging.debug('heartbeat: ' + str(self.hb))
        
        if self.hb == 0:
            self.reportCmd('DON',2)
            self.hb = 1
        else:
            self.reportCmd('DOF',2)
            self.hb = 0

    def checkNodes(self):
        logging.info('Updating Nodes')


    def systemPoll (self, polltype):
        if self.nodeDefineDone:
            logging.debug('System Poll executing: {}'.format(polltype))

            if 'longPoll' in polltype:
                #Keep token current
                #self.node.setDriver('GV0', self.temp_unit, True, True)
                try:

                    nodes = self.poly.getNodes()
                    for nde in nodes:
                        if nde != 'setup':   # but not the controller node
                            pass
                            #nodes[nde].checkOnline()
                except Exception as e:
                    logging.debug('Exeption occcured : {}'.format(e))
   
                
            if 'shortPoll' in polltype:
                self.heartbeat()
                nodes = self.poly.getNodes()
                for nde in nodes:
                    if nde != 'setup':   # but not the controller node
                        pass
                        #nodes[nde].checkDataUpdate()
    


    def handleLevelChange(self, level):
        logging.info('New log level: {}'.format(level))
        logging.setLevel(level['level'])

    def convert_temp_unit(self, unitS):
        if unitS == '':
            self.temp_unit = 0
        elif unitS[0] == 'C' or unitS[0] == 'c':
            self.temp_unit = 0
        elif unitS[0] == 'F' or unitS[0] == 'f':
            self.temp_unit = 1
        elif unitS[0] == 'k' or unitS[0] == 'k':
            self.temp_unit = 2
        else:
            logging.error('Unknown unit string (first char must be K,C,F: {}'.format(unitS))



    def handleParams (self, userParam ):
        logging.debug('handleParams')
        
        self.Parameters.load(userParam)
        logging.debug('handleParams load - {}'.format(userParam))
        self.poly.Notices.clear()

        try:
            if 'TEMP_UNIT' in userParam:
                self.temp_unit = self.convert_temp_unit(userParam['TEMP_UNIT'])
            else:
                self.temp_unit = 0

            if 'USERNAME' in userParam:
                self.userName = userParam['USERNAME']
            else:
                self.poly.Notices['userName'] = 'Missing USERNAME parameter'
                self.userName = ''


            if 'PASSWORD' in userParam:
                self.password = userParam['PASSWORD']
            else:
                self.poly.Notices['password'] = 'Missing PASSWORD parameter'
                self.password = ''

            if 'AUTH_KEY' in userParam:
                self.authKey = userParam['AUTH_KEY']
            else:
                self.poly.Notices['auth_key'] = 'Missing AUTH_KEY parameter'
                self.authKey = ''

            if 'SYNC_UNITS' in userParam:
                self.syncUnitString = userParam['SYNC_UNITS']

            else:
                self.poly.Notices['sync_units'] = 'Missing SYNC_UNITS parameter - Add NONE if no sync units'
                self.syncUnitString = ''

            self.handleParamsDone = True


        except Exception as e:
            logging.debug('Error: {} {}'.format(e, userParam))

    def update(self, command = 0):
        pass
   
    '''
    def set_t_unit(self, command ):
        logging.info('set_t_unit ')
        unit = int(command.get('value'))
        if unit >= 1 and unit <= 3:
            self.temp_unit = unit
            #self.node.setDriver('GV0', self.temp_unit, True, True)
    '''

    id = 'controller'
    commands = {
                'UPDATE': update,
                }

    


    drivers = [
            {'driver': 'ST', 'value':1, 'uom':25}, # node
            {'driver': 'GV0', 'value':0, 'uom':25}, # On-line 
           ]

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start('0.1.1')
        BlinkSetup(polyglot, 'controller', 'controller', 'BlinkSetup')

        # Just sit and wait for events
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        

