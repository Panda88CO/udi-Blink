#!/usr/bin/env python3


from udiBlinkNetworkNode import blink_network_node
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



 
VERSION = '0.4.3'

class BlinkSetup (udi_interface.Node):
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, bat_V2isy, node_queue, wait_for_node_done

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
        self.userName = None
        self.password = None
        self.authKey = None
        self.sync_nodes_added = False
        self.email_info = { 'smtp':None,
                            'smtp_port':587,
                            'email_sender':None,
                            'email_password':None,
                            'email_recepient':None,
                            'email_en': False
        }
        self.Parameters = Custom(polyglot, 'customParams')      
        self.Notices = Custom(polyglot, 'notices')
        self.n_queue = []

        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handleParams)
        self.poly.subscribe(self.poly.POLL, self.systemPoll)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
        self.poly.subscribe(self.poly.CONFIGDONE, self.validate_params)

        self.auth_key_updated = False

        self.hb = 0
        self.userParam = ['TEMP_UNIT', 'USERNAME','PASSWORD', 'AUTH_KEY', 'SYNC_UNITS' ]
        self.Parameters = Custom(self.poly, 'customparams')
        self.Notices = Custom(self.poly, 'notices')
        logging.debug('BlinkSetup init')
        #logging.debug('self.address : ' + str(self.address))
        #logging.debug('self.name :' + str(self.name))   
        self.poly.ready()
        self.poly.addNode(self, conn_status='ST')
        self.wait_for_node_done()

        self.node = self.poly.getNode(self.address)
        #logging.debug('node: {}'.format(self.node))
        self.nodes_in_db = self.poly.getNodesFromDb()
        logging.debug('BlinkSetup init DONE')
        self.nodeDefineDone = True


    

    def validate_params(self):
        logging.debug('validate_params: {}'.format(self.Parameters.dump()))
        self.paramsProcessed = True    

    def strip_StringtoList(self, syncString):
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
        try:

            self.poly.updateProfile()
            while not self.paramsProcessed or not self.nodeDefineDone:
                logging.info('Waiting for setup to complete param:{} nodes:{}'.format(self.paramsProcessed, self.nodeDefineDone ))
                time.sleep(2)
            logging.setLevel(10)
            #logging.debug('syncUnits / syncString: {} - {}'.format(self.syncUnits, self.syncUnitString))
            self.BLINK_setDriver('ST', 1)
            #time.sleep(5)


            logging.debug('nodeDefineDone {}'.format(self.nodeDefineDone))
            if self.userName == None or self.userName == '' or self.password==None or self.password=='':
                logging.error('username and password must be provided to start node server')
                self.poly.Notices['un'] = 'username and password must be provided to start node server'
                exit()
            else:
                self.auth_key_updated = False
                auth_ok = self.blink.auth1(self.userName,self.password )
                logging.debug('Auth setp 1: auth finished {}'.format(auth_ok))
                if not auth_ok:
                    logging.info('Enter 2FA PIN (message) in AUTH_KEY field and save') 
                    self.poly.Notices['PIN'] = 'Enter 2FA PIN (message) in AUTH_KEY field and save'
                    self.auth_key_updated = False
                    while not self.auth_key_updated:                      
                        logging.debug('Waiting for new pin')
                        time.sleep(5)
                self.blink.auth_key(str(self.authKey))       
                self.blink.finalize_auth()

                '''
                if 'AuthKey' == success:
                    logging.error('AuthKey required - please add to config')
                    self.poly.Notices['ak'] = 'username and password must be provided to start node server'
                elif 'no login' == success:
                    logging.error('Login Failed')
                    self.poly.Notices['un'] = 'please check username and password - do not seem to work '   
                else:
                    logging.info('Accessing Blink completed ')
                '''
                #self.add_sync_nodes()
                self.add_network_nodes()
        except Exception as e:
            logging.error('Blink Start Exception: {}'.format(e))
            self.BLINK_setDriver('ST', 0)

    def add_network_nodes (self):
        logging.info('Adding Blink network nodes:')
        node_adr_list = [self.id]

        network_node_list = self.blink.get_network_list()
        self.network_names = []
        for indx, network in enumerate (network_node_list):
            name = network['name'].upper()
            if name in self.Parameters:
                if self.Parameters[name].upper() == "ENABLED":
                    logging.debug('Adding network {}'.format(name)) 
                    self.network_names.append(network['name'])
                    node_address = self.poly.getValidAddress(str(network['id']))
                    node_name = self.poly.getValidName('Blink_'+str(network['name']))
                    logging.info('Adding {} network'.format(node_name))
                    node_adr_list.append(node_address)
                    if not blink_network_node(self.poly, node_address, node_address, node_name, network['id'], self.blink ):
                        logging.error('Failed to create network node for {} '.format(node_name))
            else:
                self.Parameters[name] = 'ENABLED'
                self.poly.Notices[name] = 'New Network detected '+str(name)+' - please select ENABLED or DISABLED - then restart'         

        while not self.paramsProcessed:
            time.sleep(5)
            logging.info('waitng to process all parameters')
        #logging.debug('email_info  : {}'.format(self.email_info))
        self.blink.set_email_info(self.email_info)
        self.poly.updateProfile()
        
        logging.debug('Checking for nodes not used - node list {} - {} {}'.format(node_adr_list, len(self.nodes_in_db), self.nodes_in_db))
        for nde, node in enumerate(self.nodes_in_db):
            #node = self.nodes_in_db[nde]
            logging.debug('Scanning db for extra nodes : {}'.format(node))
            if node['primaryNode'] not in node_adr_list:
                logging.debug('Removing primary node : {} {}'.format(node['name'], node))
                self.poly.delNode(node['address'])
            elif node['address'] not in node_adr_list:
                logging.debug('Removing sub node : {} {}'.format(node['name'], node))
                self.poly.delNode(node['address'])




    '''
    def add_sync_nodes (self):
        logging.info('Adding sync units: {}'.format(self.syncUnits ))
        self.sync_node_list = []
        if self.syncUnits != None :
            if not ('NONE'  in self.syncUnits or '' in self.syncUnits ):
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
            elif self.syncUnits != [] or 'NONE' in self.syncUnits or '' in self.syncUnits  :
                logging.info('No sync specified - create dummy node {} for all cameras '.format('nosync')) 
                if not blink_sync_node(self.poly, 'nosync', 'nosync', 'Blink Cameras', None, self.blink ):
                    logging.error('Failed to create dummy node {}'.format('nosync')) 
        self.sync_nodes_added = True
        while not self.paramsProcessed:
            time.sleep(5)
            logging.info('waitng to process all parameters')
        #logging.debug('email_info  : {}'.format(self.email_info))
        self.blink.set_email_info(self.email_info)
        self.poly.updateProfile()
    '''

    def stop(self):
        logging.info('Stop Called:')

        if 'self.node' in locals():
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
        if self.nodeDefineDone and self.sync_nodes_added:
            logging.info('System Poll executing: {}'.format(polltype))

            if 'longPoll' in polltype:
                #Keep token current
                #self.node.setDriver('GV0', self.temp_unit, True, True)
                try:
                    self.blink.refresh_data()
                    nodes = self.poly.getNodes()
                    for nde in nodes:
                        if nde != 'setup':   # but not the setup node
                            logging.debug('updating node {} data'.format(nde))                            
                            nodes[nde].updateISYdrivers()
                         
                except Exception as e:
                    logging.debug('Exeption occcured : {}'.format(e))
   
                
            if 'shortPoll' in polltype:
                self.heartbeat()
        else:
            logging.info('System Poll - Waiting for all nodes to be added')
  


    def handleLevelChange(self, level):
        logging.info('New log level: {}'.format(level))
        logging.setLevel(level['level'])

    def convert_temp_unit(self, unitS):
        if unitS == '':
            self.temp_unit = 0
        elif unitS[0] == 'C' or unitS[0] == 'c':
            self.temp_unit = 'C'
        elif unitS[0] == 'F' or unitS[0] == 'f':
            self.temp_unit = 'F'
        elif unitS[0] == 'k' or unitS[0] == 'k':
            self.temp_unit = 'K'
        else:
            logging.error('Unknown unit string (first char must be C,F,K: {}'.format(unitS))
        self.blink.set_temp_unit(self.temp_unit)


    def handleParams (self, customParams ):
        logging.debug('handleParams')
        try:
            self.Parameters.load(customParams)
            logging.debug('handleParams load - {}'.format(customParams))
            self.poly.Notices.clear()
            if 'TEMP_UNIT' in customParams:
                temp = customParams['TEMP_UNIT'].upper()
                if '' == temp or None == temp:
                    self.poly.Notices['TEMP_UNIT'] = 'Missing temp unit (C,F,K)'                    
                else:
                    if temp[0] == 'C':
                        self.blink.set_temp_unit('C') 
                    elif temp[0] == 'F' :
                        self.blink.set_temp_unit('F') 
                    elif temp[0] == 'K' :
                        self.blink.set_temp_unit('K') 
                    if 'TEMP_UNIT' in self.poly.Notices:
                            self.poly.Notices.delete('TEMP_UNIT')

            if 'USERNAME' in customParams:
                self.userName = customParams['USERNAME']
            else:
                self.poly.Notices['userName'] = 'Missing USERNAME parameter'
                self.userName = ''
            
            if 'PASSWORD' in customParams:
                self.password = customParams['PASSWORD']
            else:
                self.poly.Notices['password'] = 'Missing PASSWORD parameter'
                self.password = ''

            if 'AUTH_KEY' in customParams:
                self.authKey = customParams['AUTH_KEY']
                self.auth_key_updated = True
            else:
                self.poly.Notices['auth_key'] = 'Missing AUTH_KEY parameter'
                self.authKey = ''

            #if 'NETWORKS_UNITS' in customParams:
            #    self.syncUnitString = customParams['NETWORKS_UNITS']
            #    self.networkUnits = self.strip_syncUnitStringtoList(self.networkUnitString)
            #else:
            #    self.poly.Notices['networks'] = 'Specify desired NETWORK_UNITS'
            #    self.syncUnitString = ''

            if 'EMAIL_ENABLED' in customParams:
                self.email_en = customParams['EMAIL_ENABLED']
                if self.email_en.upper()[0] == 'T':
                    self.email_en = True
                else:
                    self.email_en = False
            else:
                self.poly.Notices['email_en'] = 'Missing EMAIL_ENABLED parameter (True/False)'
            self.email_info['email_en'] = self.email_en

            if self.email_en:
                if 'SMTP' in customParams:
                    self.smtp = customParams['SMTP']
                else:
                    self.poly.Notices['email_smpt'] = 'Missing EMAIL_SMPT parameter'
                self.email_info['smtp'] = self.smtp

                if 'SMTP_PORT' in customParams:
                    self.smtp_port = customParams['SMTP_PORT']
                else:
                    self.poly.Notices['email_smpt'] = 'Missing EMAIL_SMPT parameter'
                    self.smtp_port = 587
                    self.email_info['smtp_port'] = self.smtp_port

                if 'SMTP_EMAIL' in customParams:
                    self.email_sender = customParams['SMTP_EMAIL']
                else:
                    self.poly.Notices['email_sender'] = 'Missing EMAIL_SERVER parameter'
                self.email_info['email_sender'] = self.email_sender

                if 'SMTP_PASSWORD' in customParams:
                    self.email_password = customParams['SMTP_PASSWORD']
                else:
                    self.poly.Notices['email_password'] = 'Missing EMAIL_PASSWORD parameter'
                self.email_info['email_password'] = self.email_password

                if 'EMAIL_RECEPIENT' in customParams:
                    self.email_recepient = customParams['EMAIL_RECEPIENT']
                else:
                    self.poly.Notices['email_recepient'] = 'Missing EMAIL_RECEPIENT parameter'
                self.email_info['email_recepient'] = self.email_recepient

            #logging.debug('email_info : {}'.format(self.email_info))
            self.paramsProcessed = True


        except Exception as e:
            logging.debug('Error: {} {}'.format(e, customParams))

    def update(self, command = None):
        self.systemPoll(['longPoll'])
   
    '''
    def set_t_unit(self, command ):
        logging.info('set_t_unit ')
        unit = int(command.get('value'))
        if unit >= 1 and unit <= 3:
            self.temp_unit = unit
            #self.node.setDriver('GV0', self.temp_unit, True, True)
    '''

    id = 'setup'
    commands = {
                'UPDATE': update,
                }

    


    drivers = [
            {'driver': 'ST', 'value':1, 'uom':25}, # node
           ]

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        BlinkSetup(polyglot, 'setup', 'setup', 'BlinkSetup')

        # Just sit and wait for events
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        

