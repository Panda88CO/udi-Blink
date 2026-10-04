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
from  udiBlinkCameraNode import blink_camera_node, blink_camera_no_temp_node
from  udiBlinkSyncNode import blink_sync_node
from  udiBlinkLib import parse_enable_state


               
class blink_network_node(udi_interface.Node):
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, bat_V2isy, node_queue, wait_for_node_done
    _started = False


    def __init__(self, polyglot, primary, address, name, network_id, blinkSys, controller=None):
        super().__init__( polyglot, primary, address, name)   
        self._started = False
        # logging.debug('New Blink Network INIT- {}'.format(name))
        self.nodeDefineDone = False
        self.networkNodeReady = False
        self.network_id = network_id
        self.name = name
        self.blink = blinkSys
        self.primary = primary
        self.address = address

        self.sync_node_camera_list = []
        self.n_queue = []  
        self.poly = polyglot
        self.controller = controller or self.poly.getNode(primary) or getattr(self.poly, 'controller', None)
        self.Parameters = getattr(self.controller, 'Parameters', None) or Custom(polyglot, 'customparams')
        self._camera_list = []
        self._sync_list = []
        self.hb = 0
        # subscribe to the events we want
        #polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        #polyglot.subscribe(polyglot.POLL, self.poll)
        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

             

        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        logging.info('Start {} network Node'.format(self.name))  
        self.nodeDefineDone = True




    def start(self):        
        if getattr(self, '_started', False):
            return
        self._started = True
        while not self.nodeDefineDone:
            time.sleep(0.1)
        if getattr(self, 'node', None) is None:
            self.node = self.poly.getNode(self.address) or self

 
        self.camera_list = self.blink.get_cameras_on_network(self.network_id)
        camera_ids = {str(camera.camera_id) for camera in self.camera_list}

        db_nodes = {}
        try:
            for n in self.poly.getNodesFromDb():
                if isinstance(n, dict) and 'address' in n:
                    db_nodes[n['address']] = n.get('nodeDefId')
        except Exception as e:
            logging.debug(f'Error getting db nodes: {e}')

        for indx, camera in enumerate(self.camera_list):
            # logging.debug('{} cameras found in network {}'.format(len(self.camera_list), self.network_id))
            nodeName = self.poly.getValidName(str(camera.name))
            nodeAdr = self.poly.getValidAddress(str(camera.camera_id))

            supports_temp = hasattr(self.blink, 'camera_supports_temperature') and self.blink.camera_supports_temperature(camera.name)
            temp_unit = getattr(self.blink, 'temp_unit', 'C')
            target_def = 'BLINKCAMERAF' if (supports_temp and temp_unit == 'F') else ('BLINKCAMERAC' if supports_temp else 'BLINKCAMERA')

            existing = self.poly.getNode(nodeAdr)
            existing_def = getattr(existing, 'id', None) or db_nodes.get(nodeAdr)
            if existing_def and existing_def != target_def:
                logging.info(f"Camera node {nodeAdr} ({nodeName}) has nodeDefId '{existing_def}', but target is '{target_def}'. Deleting old node from IoX to reload updated nodeDef...")
                self.poly.delNode(nodeAdr)
                existing = None
                db_nodes.pop(nodeAdr, None)
                time.sleep(0.5)

            if not existing:
                if not supports_temp:
                    logging.info('Adding Camera {} {} {} (no temperature - BLINKCAMERA)'.format(self.address, nodeAdr, nodeName))
                    blink_camera_no_temp_node(self.poly, self.primary, nodeAdr, nodeName, camera, self.blink)
                else:
                    logging.info('Adding Camera {} {} {} (with temperature - {})'.format(self.address, nodeAdr, nodeName, target_def))
                    blink_camera_node(self.poly, self.primary, nodeAdr, nodeName, camera, self.blink)
            self._camera_list.append(nodeAdr)
            
        self.sync_list = self.blink.get_sync_modules_on_network(self.network_id)
        # logging.debug('Sync list : {}'.format(self.sync_list))
        for indx, sync in enumerate(self.sync_list):
            if str(sync.sync_id) in camera_ids:
                logging.info('Skipping SYNC unit {} on network {} because sync_id matches a camera_id'.format(sync.name, self.network_id))
                continue
            # logging.debug('Sync: {}'.format(sync.name))
            nodeName = self.poly.getValidName(str(sync.name))
            nodeAdr = self.poly.getValidAddress(str(sync.sync_id))
            if nodeAdr in self._camera_list:
                logging.info('Skipping SYNC unit {} on network {} because normalized address {} collides with a camera address'.format(sync.name, self.network_id, nodeAdr))
                continue
            logging.info('Adding SYNC unit  {} {} {}'.format(self.address, nodeAdr, nodeName))
            blink_sync_node(self.poly, self.primary, nodeAdr, nodeName, sync, self.blink)
            self._sync_list.append(nodeAdr)
        self.nodeDefineDone = True
        self.set_connection_status(True)
        self.updateISYdrivers()
        #tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        #self.BLINK_setDriver('GV2', self.bool2isy(tmp))
        #logging.debug('_camera_list {}'.format(self._camera_list))
        #logging.debug('_sync_list {}'.format(self._sync_list))        

        nodes_in_db = self.poly.getNodesFromDb()
        nodes = self.poly.getNodes()
        
        #logging.debug('Checking for nodes not used - node list {} - {} {}'.format(node_adr_list, len(nodes_in_db), nodes_in_db))

        for nde, node in enumerate(nodes_in_db):
            #node = self.nodes_in_db[nde]
            # logging.debug('Scanning db for extra nodes : {}'.format(node))
            if node['primaryNode'] == self.primary:                
                # logging.debug('Checking network nodes: {} {}'.format(node['name'], node))
                if node['address'] not in self._camera_list and node['address'] not in self._sync_list and node['address'] != self.primary:
                    self.poly.delNode(node['address'])

    def update_cameras(self):
        """Ensure all cameras on this network exist as nodes"""
        if not getattr(self, '_started', False) or not self.nodeDefineDone:
            return

        db_nodes = {}
        try:
            for n in self.poly.getNodesFromDb():
                if isinstance(n, dict) and 'address' in n:
                    db_nodes[n['address']] = n.get('nodeDefId')
        except Exception as e:
            logging.debug(f'Error getting db nodes: {e}')

        self.camera_list = self.blink.get_cameras_on_network(self.network_id)
        current_cam_nodes = list(self._camera_list)
        new_cam_nodes = []
        changed = False

        for camera in self.camera_list:
            nodeName = self.poly.getValidName(str(camera.name))
            nodeAdr = self.poly.getValidAddress(str(camera.camera_id))
            new_cam_nodes.append(nodeAdr)

            supports_temp = hasattr(self.blink, 'camera_supports_temperature') and self.blink.camera_supports_temperature(camera.name)
            temp_unit = getattr(self.blink, 'temp_unit', 'C')
            target_def = 'BLINKCAMERAF' if (supports_temp and temp_unit == 'F') else ('BLINKCAMERAC' if supports_temp else 'BLINKCAMERA')

            existing = self.poly.getNode(nodeAdr)
            existing_def = getattr(existing, 'id', None) or db_nodes.get(nodeAdr)

            if existing_def and existing_def != target_def:
                logging.info(f"Camera node {nodeAdr} ({nodeName}) has nodeDefId '{existing_def}', but target is '{target_def}'. Deleting old node from IoX to reload updated nodeDef...")
                self.poly.delNode(nodeAdr)
                existing = None
                db_nodes.pop(nodeAdr, None)
                changed = True
                time.sleep(0.5)

            if not existing or nodeAdr not in current_cam_nodes:
                if not supports_temp:
                    logging.info('Adding Camera {} {} {} (no temperature - BLINKCAMERA)'.format(self.address, nodeAdr, nodeName))
                    blink_camera_no_temp_node(self.poly, self.primary, nodeAdr, nodeName, camera, self.blink)
                else:
                    logging.info('Adding Camera {} {} {} (with temperature - {})'.format(self.address, nodeAdr, nodeName, target_def))
                    blink_camera_node(self.poly, self.primary, nodeAdr, nodeName, camera, self.blink)
                changed = True

        self._camera_list = new_cam_nodes
        if changed and hasattr(self.controller, '_update_dynamic_profile'):
            self.controller._update_dynamic_profile()

    def stop(self):
        logging.info('stop {} - Cleaning up'.format(self.name))

    
    def set_connection_status(self, connected):
        logging.info('set_connection_status {} - {}'.format(self.name, connected))
        self.setDriver('GV0', 1 if connected else 0)

    def updateISYdrivers(self):
        if self.nodeDefineDone:
            logging.info('Network updateISYdrivers - {}'.format(self.network_id))
            try:
                arm_val = self.blink.get_network_arm_state(self.network_id)
                if arm_val is None or arm_val == 99:
                    logging.warning('Network %s: Could not retrieve valid arm state (%s) - skipping TIME update', self.network_id, arm_val)
                    if arm_val == 99:
                        self.BLINK_setDriver('ST', 99)
                    return

                if arm_val == 2:
                    logging.info('Network %s: No sync unit, cameras only. Setting ST to 2 (Individually camera assigned).', self.network_id)
                    self.BLINK_setDriver('ST', 2)
                elif arm_val is True:
                    self.BLINK_setDriver('ST', 1)
                elif arm_val is False:
                    self.BLINK_setDriver('ST', 0)

                # Verify network is present in Blink system data
                network_found = False
                for net in self.blink.get_network_list():
                    if str(net.get('id', '')) == str(self.network_id):
                        network_found = True
                        break
                if not network_found and not any(str(getattr(s, 'network_id', '')) == str(self.network_id) for s in self.blink.sync.values()):
                    logging.warning('Network %s not found in Blink system data - skipping TIME update', self.network_id)
                    self.BLINK_setDriver('GV0', 0)
                    return

                self.BLINK_setDriver('GV0', 1)

                # Timestamp reflects the last successful network data refresh without errors
                self.BLINK_setDriver('TIME', int(time.time()), 151)
            except Exception as e:
                logging.error('Error updating ISY drivers for network %s: %s', self.network_id, e)

                         
        #tmp = self.blink.get_sync_arm_info(self.sync_unit.name)
        #self.BLINK_setDriver('GV2', self.bool2isy(tmp))

  
    def heartbeat(self):
        # logging.debug('heartbeat')        
        self.reportCmd('DON',2)
        time.sleep(5)
        self.reportCmd('DOF',2)


    def ISYupdate(self, command=None):
        logging.info('Network ISYupdate')
        if not self.blink.refresh():
            logging.warning('Blink refresh failed for network %s - skipping driver update', self.network_id)
            return
        self.updateISYdrivers()

        
    # NEEDS UPDATE
    def arm_all_cameras (self, command):
        arm_enable = (1 == int(command.get('value')) )
        logging.info('Network arm_all_cameras:{} - {}'.format(self.network_id, arm_enable ))
        
        #if self.sync_unit != None:
        #    self.BLINK_setDriver('GV2', self.bool2isy(arm_enable))
        #    self.blink.set_sync_arm(self.sync_unit.name,  arm_enable )
        #    if arm_enable:
        #        self.node.reportCmd('DON')
        #    else:
        #        self.node.reportCmd('DOF')
        #    #self.updateISYdrivers()
        #else:

        success = self.blink.set_network_arm_state(self.network_id, arm_enable)
        # logging.debug('set_network_arm_state returned: {}'.format(success))
        time.sleep(1)
        ok = self.blink.get_network_arm_state(self.network_id)
        # logging.debug('get_network_arm_state returned (Armed): {}'.format(ok))
        self.BLINK_setDriver('ST', self.bool2isy(ok))
        #    camera_list = self.blink.get_camera_list()
        #    for camera in camera_list:
        #        self.blink.set_camera_arm(camera, arm_enable)
        # logging.debug('_camera_list {}'.format(self._camera_list))
        time.sleep(3)
        if not self.blink.refresh():
            logging.warning('Blink refresh failed after arm_all_cameras for network %s - skipping driver update', self.network_id)
            return
        self.updateISYdrivers()
        nodes = self.poly.getNodes()
        for nde in self._camera_list:
            # logging.debug('updating node {} data'.format(nde))    
            if nde in nodes and hasattr(nodes[nde], 'updateISYdrivers'):
                nodes[nde].updateISYdrivers()


    id = 'BLINKNETWORK'

    commands = { 'UPDATE'   : ISYupdate,
                 'ARMALL'   : arm_all_cameras
            

                }

    drivers= [ 
            {'driver': 'ST', 'value': 0, 'uom': 25}, # Armed (ARMED)
            {'driver': 'GV0', 'value': 1, 'uom': 25}, # Connected (ONLINE)
            {'driver': 'TIME', 'value': 0, 'uom': 151}
        ]
 

        

