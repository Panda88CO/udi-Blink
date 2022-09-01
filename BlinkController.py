#!/usr/bin/env python3
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
import sys
import time 

from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth
from BlinkSyncNode import blink_sync_module




class BlinkSetup (udi_interface.Node):
    def  __init__(self, polyglot, primary, address, name):
        super().__init__( polyglot, primary, address, name)  
        
        #logging.setLevel(30)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handleParams)
        self.poly.subscribe(self.poly.POLL, self.systemPoll)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
        self.n_queue = []

        self.Parameters = Custom(self.poly, 'customparams')
        self.Notices = Custom(self.poly, 'notices')
        logging.debug('BlinkSetup init')
        logging.debug('self.address : ' + str(self.address))
        logging.debug('self.name :' + str(self.name))   
        self.poly.updateProfile()
        self.poly.ready()
        self.poly.addNode(self)
        self.wait_for_node_done()

        self.node = self.poly.getNode(self.address)
        self.node.setDriver('ST', 1, True, True)
        logging.debug('BlinkSetup init DONE')
        self.nodeDefineDone = True


    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()




    def start (self):
        logging.info('Executing start - BlinkSetup')
        #logging.setLevel(30)
        while not self.nodeDefineDone:
            time.sleep(1)
            logging.debug ('waiting for inital node to get created')
       
        if self.userName == None or self.userName == '' or self.password==None or self.password=='':
            logging.error('username and password must be provided to start node server')
            exit() 

        self.blink = Blink()
        # Can set no_prompt when initializing auth handler
        auth = Auth({"username":self.userName, "password":self.password}, no_prompt=True)
        self.blink.auth = auth
        self.blink.start()
        if self.blink.key_required:
            if self.authkey == None or self.authKey == '':
                logging.error('AuthKey required - please add to config')
            else:
                auth.send_auth_key(self.blink, self.authKey)
        self.blink.setup_post_verify()
        self.blink.refresh()

        if self.syncUnits!= None and self.syncUnits != '':
            self.syncUnitList = []
            temp = self.syncUnits.upper()
            for sync in self.blink.sync:
                if temp.find(sync.upper()) >= 0:
                    self.syncUnitList.append(sync)


        self.addNodes(self.deviceList)

        #self.poly.updateProfile()



    def addNodes (self, deviceList):
        for syncUnit in self.blink.sync:
            if syncUnit in self.syncUnitList:
                logging.info('Adding sync unit {}'.format(syncUnit))
                if len(syncUnit) >=14:
                    nodeName = syncUnit[0:14]
                else:
                    nodeName = syncUnit
                self.blink_sync_module(self.poly, nodeName, nodeName, syncUnit, self.blink)

        self.poly.updateProfile()


    def stop(self):
        logging.info('Stop Called:')
        #self.yoAccess.writeTtsFile() #save current TTS messages
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
        self.deviceList = self.yoAccess.getDeviceList()
        nodes = self.poly.getNodes()
        for dev in range(0,len(self.deviceList)):
            devList = []
            name = self.deviceList[dev]['deviceId'][-14:]
            if name not in nodes:
                #device was likely off line during inital instellation or added afterwards
                devList.append(self.deviceList[dev])
                self.addNodes(devList)


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
    


    def handleLevelChange(self, level):
        logging.info('New log level: {}'.format(level))
        logging.setLevel(level['level'])



    def handleParams (self, userParam ):
        logging.debug('handleParams')
        supportParams = ['TEMP_UNIT', 'USERNAME','PASSWORD', 'AUTH_KEY']
        self.Parameters.load(userParam)

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
                self.syncUnits = userParam['SYNC_UNITS']
            else:
                self.poly.Notices['sync_units'] = 'Missing SYNC_UNITS parameter'
                self.syncUnits = ''


            self.handleParamsDone = True


        except Exception as e:
            logging.debug('Error: {} {}'.format(e, userParam))

    '''
    def set_t_unit(self, command ):
        logging.info('set_t_unit ')
        unit = int(command.get('value'))
        if unit >= 1 and unit <= 3:
            self.temp_unit = unit
            #self.node.setDriver('GV0', self.temp_unit, True, True)
    '''

    id = 'setup'
    #commands = {
    #            'TEMPUNIT': set_t_unit,
    #            }

    drivers = [
            {'driver': 'ST', 'value':1, 'uom':25},
          # {'driver': 'GV0', 'value':0, 'uom':25},
           ]

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start('0.1.0')
        BlinkSetup(polyglot, 'setup', 'setup', 'BlinkSetup')

        # Just sit and wait for events
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        

