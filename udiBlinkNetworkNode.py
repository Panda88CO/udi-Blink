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
from  udiBlinkSyncNode import blink_sync_node

               
class blink_network_node(udi_interface.Node):
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, bat_V2isy, node_queue, wait_for_node_done


    def __init__(self, polyglot, primary, address, name, network_id, blinkSys  ):
        super().__init__( polyglot, primary, address, name)   
        logging.debug('blink SYNC INIT- {}'.format(name))
        self.nodeDefineDone = False
        self.network_id = network_id
        self.name = name
        self.blink = blinkSys
        self.primary = primary
        self.address = address
        self.sync_node_camera_list = []
        self.n_queue = []  
        self.poly = polyglot
        self._camera_list = []
        self._sync_list = []
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




    def start(self):        
        logging.debug('Sync module Start {}'.format(self.name))
        time.sleep(2)
        while not self.nodeDefineDone or self.node == None or self.drivers == None:
            time.sleep(2)
            logging.info('Waiting for nodes to be created')

        '''
        if self.sync_unit == None: #no sync units used
            self.camera_list = self.blink.get_camera_list()
        else:
            self.camera_list = self.blink.get_sync_camera_list(self.sync_unit )
        '''
        self.camera_list = self.blink.get_cameras_on_network(self.network_id)

        logging.debug('Adding Cameras in list: {}'.format(self.camera_list))             
        for indx, camera in enumerate(self.camera_list):
            #camera_unit = self.blink.get_camera_unit(camera['name'])
            logging.debug('{} cameras found in network {}'.format(len(self.camera_list), self.network_id))
            nodeName = self.poly.getValidName(str(camera.name))
            #cameraName = str(name)#.replace(' ','')
            nodeAdr = self.poly.getValidAddress(str(camera.camera_id))
            #nodeAdr = str(name).replace(' ','')[:14]
            logging.info('Adding Camera {} {} {}'.format(self.address,nodeAdr, nodeName))
            blink_camera_node(self.poly, self.primary, nodeAdr, nodeName, camera, self.blink)
            self._camera_list.append(nodeAdr)
            
        self.sync_list = self.blink.get_sync_modules_on_network(self.network_id)
        logging.debug('Sync list : {}'.format(self.sync_list))
        for indx, sync in enumerate(self.sync_list):
            logging.debug('Sync: {}'.format(sync))
            nodeName = self.poly.getValidName(str(sync.name))
            nodeAdr = self.poly.getValidAddress(str(sync.sync_id))
            logging.info('Adding Camera {} {} {}'.format(self.address, nodeAdr, nodeName))
            blink_sync_node(self.poly, self.primary, nodeAdr, nodeName, sync, self.blink)
            self._sync_list.append(nodeAdr)
        self.nodeDefineDone = True
        self.BLINK_setDriver('GV0', self.bool2isy(self.blink.get_network_arm_state(self.network_id)))
        #tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        #self.BLINK_setDriver('GV2', self.bool2isy(tmp))
        logging.debug('_camera_list {}'.format(self._camera_list))
        logging.debug('_sync_list {}'.format(self._sync_list))        

        nodes_in_db = self.poly.getNodesFromDb()
        nodes = self.poly.getNodes()
        
        #logging.debug('Checking for nodes not used - node list {} - {} {}'.format(node_adr_list, len(nodes_in_db), nodes_in_db))

        for nde, node in enumerate(nodes_in_db):
            #node = self.nodes_in_db[nde]
            logging.debug('Scanning db for extra nodes : {}'.format(node))
            if node['primaryNode'] == self.primary:                
                logging.debug('Checking network nodes: {} {}'.format(node['name'], node))
                if node['address'] not in self._camera_list and node['address'] not in self._sync_list and node['address'] != self.primary:
                    self.poly.delNode(node['address'])

    def stop(self):
        logging.info('stop {} - Cleaning up'.format(self.name))


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

    def updateISYdrivers(self):
        if self.nodeDefineDone:
            logging.info('Network updateISYdrivers - {}'.format(self.network_id))
            self.BLINK_setDriver('GV0', self.bool2isy(self.blink.get_network_arm_state(self.network_id)))

                         
        #tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        #self.BLINK_setDriver('GV2', self.bool2isy(tmp))

  
    def ISYupdate(self, command=None):
        logging.info('Sync ISYupdate')
        self.blink.refresh()
        
        self.updateISYdrivers()

        
    # NEEDS UPDATE
    def arm_all_cameras (self, command):
        arm_enable = (1 == int(command.get('value')) )
        logging.info('Sync arm_all_cameras:{} - {}'.format(self.network_id, arm_enable ))
        
        #if self.sync_unit != None:
        #    self.BLINK_setDriver('GV2', self.bool2isy(arm_enable))
        #    self.blink.set_sync_arm(self.sync_unit.name,  arm_enable )
        #    if arm_enable:
        #        self.node.reportCmd('DON')
        #    else:
        #        self.node.reportCmd('DOF')
        #    #self.updateISYdrivers()
        #else:

        self.blink.set_network_arm_state(self.network_id, arm_enable)
        time.sleep(1)
        self.BLINK_setDriver('GV0', self.bool2isy(self.blink.get_network_arm_state(self.network_id)))
        #    camera_list = self.blink.get_camera_list()
        #    for camera in camera_list:
        #        self.blink.set_camera_arm(camera, arm_enable)
        logging.debug('_camera_list {}'.format(self._camera_list))
        time.sleep(3)
        self.blink.refresh()
        self.updateISYdrivers()
        nodes = self.poly.getNodes()
        for nde in self._camera_list:
            logging.debug('updating node {} data'.format(nde))    
            nodes[nde].updateISYdrivers()


    id = 'blinknetwork'

    commands = { 'UPDATE'   : ISYupdate,

                 'ARMALL'   : arm_all_cameras
            

                }

    drivers= [ 
                {'driver': 'GV0', 'value':0, 'uom':25} # Armed
        ] 

        

