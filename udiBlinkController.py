#!/usr/bin/env python3

import sys
import os

# Set environment variables for pure-Python fallback (critical on FreeBSD / Polisy / eisy without C compiler/headers)
os.environ['AIOHTTP_NO_EXTENSIONS'] = '1'
os.environ['FROZENLIST_NO_EXTENSIONS'] = '1'
os.environ['MULTIDICT_NO_EXTENSIONS'] = '1'
os.environ['YARL_NO_EXTENSIONS'] = '1'

import time 
import re
import threading
import json
import subprocess
import site

# Ensure user site-packages are added to sys.path
try:
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path and os.path.exists(user_site):
        sys.path.insert(0, user_site)
except Exception:
    pass

# Ensure blinkpy is available, or attempt auto-install if missing on clean install
try:
    import blinkpy
except ImportError:
    try:
        req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt')
        if os.path.exists(req_file):
            env = os.environ.copy()
            env['AIOHTTP_NO_EXTENSIONS'] = '1'
            env['FROZENLIST_NO_EXTENSIONS'] = '1'
            env['MULTIDICT_NO_EXTENSIONS'] = '1'
            env['YARL_NO_EXTENSIONS'] = '1'
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'aiohttp', '--no-binary=aiohttp', '--user'], env=env)
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', req_file, '--user'], env=env)
            user_site = site.getusersitepackages()
            if user_site and user_site not in sys.path and os.path.exists(user_site):
                sys.path.insert(0, user_site)
            import blinkpy
    except Exception:
        pass

from udiBlinkNetworkNode import blink_network_node
from BlinkSystem import blink_system


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



 
VERSION = '0.6.20' 

class BlinkSetup (udi_interface.Node):
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, bat_V2isy, node_queue, wait_for_node_done, gen_uid
    id = 'setup'
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 25}]
    def  __init__(self, polyglot, primary, address, name):
        super().__init__( polyglot, primary, address, name)  
        
        #logging.setLevel(10)
        
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
        self.temp_unit = 'C'
        self.sync_nodes_added = False
        self.email_info = { 'smtp':None,
                            'smtp_port':587,
                            'email_sender':None,
                            'email_password':None,
                            'email_recepient':None,
                            'email_en': False
        }
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.customData = Custom(polyglot, 'customdata')
        #self.customData.load()
        #self.n_queue = []

        self.poly.subscribe(self.poly.STOP, self.stop)
        #self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.handleParams)
        self.poly.subscribe(self.poly.CUSTOMDATA, self.handleData)
        self.poly.subscribe(self.poly.POLL, self.systemPoll)
        #self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)
        self.poly.subscribe(self.poly.CONFIGDONE, self.validate_params)

        self.auth_key_updated = False

        self.hb = 0
        self._heartbeat_threads = {}
        self.userParam = ['TEMP_UNIT', 'USERNAME','PASSWORD', 'AUTH_KEY', 'SYNC_UNITS' ]
        logging.debug('BlinkSetup init')
        #logging.debug('self.address : ' + str(self.address))
        #logging.debug('self.name :' + str(self.name))   
        self.poly.ready()
        #self.poly.addNode(self, conn_status='ST')
        #self.wait_for_node_done()

        #self.node = self.poly.getNode(self.address)
        #logging.debug('node: {}'.format(self.node))
        self.nodes_in_db = self.poly.getNodesFromDb()
        logging.debug('BlinkSetup init DONE')
        self.nodeDefineDone = True
        self.start()

    

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


    def load_saved_tokens(self):
        tokens = None
        # Try customData first
        try:
            if 'auth_tokens' in self.customData and self.customData['auth_tokens']:
                tokens = self.customData['auth_tokens']
                logging.debug('Found auth_tokens in customData')
        except Exception as e:
            logging.debug(f'Could not load auth_tokens from customData: {e}')

        # If not in customData, try local file
        if not tokens or not isinstance(tokens, dict) or not tokens.get('refresh_token'):
            if os.path.exists('blink_tokens.json'):
                try:
                    with open('blink_tokens.json', 'r') as f:
                        file_tokens = json.load(f)
                    if isinstance(file_tokens, dict) and file_tokens.get('refresh_token'):
                        tokens = file_tokens
                        logging.debug('Loaded auth_tokens from blink_tokens.json')
                        try:
                            self.customData['auth_tokens'] = tokens
                        except Exception:
                            pass
                except Exception as e:
                    logging.error(f'Error reading blink_tokens.json: {e}')

        if tokens and isinstance(tokens, dict):
            # Check if username matches current username
            token_user = tokens.get('username')
            if token_user and self.userName and token_user.lower() != self.userName.lower():
                logging.warning(f'Stored tokens belong to {token_user}, but configured username is {self.userName}. Clearing tokens.')
                self.clear_saved_tokens()
                return None
            return tokens
        return None

    def save_saved_tokens(self, auth_data):
        if not auth_data or not isinstance(auth_data, dict):
            return
        if not auth_data.get('refresh_token'):
            return
        logging.info('Saving updated Blink authentication tokens...')
        if not auth_data.get('username') and self.userName:
            auth_data['username'] = self.userName
        try:
            self.customData['auth_tokens'] = auth_data
        except Exception as e:
            logging.error(f'Error storing auth_tokens in customData: {e}')
        try:
            with open('blink_tokens.json', 'w') as f:
                json.dump(auth_data, f, indent=2)
            os.chmod('blink_tokens.json', 0o600)
            logging.debug('Auth tokens saved to blink_tokens.json')
        except Exception as e:
            logging.error(f'Failed to save blink_tokens.json: {e}')

    def clear_saved_tokens(self):
        logging.info('Clearing stored Blink authentication tokens')
        try:
            self.customData['auth_tokens'] = None
        except Exception as e:
            logging.error(f'Error clearing auth_tokens from customData: {e}')
        try:
            if os.path.exists('blink_tokens.json'):
                os.remove('blink_tokens.json')
        except Exception as e:
            logging.error(f'Error removing blink_tokens.json: {e}')

    def prepare_login_data(self, auth_tokens=None):
        logging.debug('prepare_login_data')
        login_data = {}
        login_data['username'] = self.userName
        login_data['password'] = self.password
        login_data['device_id'] = 'ISY_PG3x'
        login_data['reauth'] = True
        #logging.debug('custom data: {}'.format(self.customData))
        if 'unique_id' in self.customData.keys():
            logging.debug('uid found: {}'.format(self.customData['unique_id']))
            if self.customData['unique_id'] is not None: 
                login_data['unique_id'] = self.customData['unique_id']
            else:
                login_data['unique_id'] = self.gen_uid(16, True)
                self.customData['unique_id'] = login_data['unique_id']
                logging.debug('uid created: {}'.format(self.customData['unique_id']))              
        else:
            login_data['unique_id'] = self.gen_uid(16, True)
            self.customData['unique_id'] = login_data['unique_id']
            logging.debug('uid created: {}'.format(self.customData['unique_id']))

        if auth_tokens and isinstance(auth_tokens, dict):
            for k in [
                'token',
                'refresh_token',
                'hardware_id',
                'client_id',
                'account_id',
                'user_id',
                'region_id',
                'host',
                'expires_in',
                'expiration_date',
            ]:
                if k in auth_tokens and auth_tokens[k] is not None:
                    login_data[k] = auth_tokens[k]
            logging.debug('prepare_login_data included stored auth tokens and hardware_id')

        #logging.debug('prepare_login_data {}'.format(login_data))
        return(login_data)


    def start (self):
        logging.info('Executing start - BlinkSetup')
        try:

            self.poly.updateProfile()
            while not self.paramsProcessed or not self.nodeDefineDone:
                logging.info('Waiting for setup to complete param:{} nodes:{}'.format(self.paramsProcessed, self.nodeDefineDone ))
                time.sleep(2)
            #logging.setLevel(10)
            #logging.debug('syncUnits / syncString: {} - {}'.format(self.syncUnits, self.syncUnitString))
            #self.BLINK_setDriver('ST', 1)
            #time.sleep(5)
            logging.debug('nodeDefineDone {}'.format(self.nodeDefineDone))
            logging.debug('credentilas : {} {}'.format(self.userName, self.password))

            if self.userName == None or self.userName == '' or self.password==None or self.password=='':
                logging.error('username and password must be provided to start node server')
                self.poly.Notices['un'] = 'username and password must be provided to start node server'
                exit()
            else:
                logging.debug('STARTING BLINK SYSTEM')
                saved_tokens = self.load_saved_tokens()
                attempt_with_tokens = (saved_tokens is not None and bool(saved_tokens.get('refresh_token')))

                if attempt_with_tokens:
                    logging.info('Found saved tokens. Attempting to start Blink with saved tokens...')
                    login_data = self.prepare_login_data(saved_tokens)
                else:
                    logging.info('No saved tokens found. Starting fresh Blink login...')
                    login_data = self.prepare_login_data()

                self.blink.set_token_refresh_callback(self.save_saved_tokens)
                self.blink.start_blink(login_data, True)
                self.blink.set_temp_unit(self.temp_unit) 

                ok = False
                try:
                    ok = self.blink.start()
                except Exception as e:
                    logging.error(f'Exception during blink start: {e}')
                    ok = False

                auth_needed = self.blink.key_required
                logging.debug(f'Auth step 1: ok={ok}, 2FA required={auth_needed}')

                # If starting with saved tokens failed (not ok and not waiting for 2FA),
                # clear tokens and start over from scratch!
                if attempt_with_tokens and not ok and not auth_needed:
                    logging.warning('Starting with saved tokens failed. Clearing tokens and restarting fresh login...')
                    self.clear_saved_tokens()
                    try:
                        self.blink.stop()
                    except Exception as e:
                        logging.debug(f'Error stopping blink: {e}')

                    self.blink = blink_system()
                    self.blink.set_token_refresh_callback(self.save_saved_tokens)
                    login_data = self.prepare_login_data()
                    self.blink.start_blink(login_data, True)
                    self.blink.set_temp_unit(self.temp_unit)
                    try:
                        ok = self.blink.start()
                    except Exception as e:
                        logging.error(f'Exception during fresh blink start: {e}')
                        ok = False
                    auth_needed = self.blink.key_required
                    logging.debug(f'Fresh start: ok={ok}, 2FA required={auth_needed}')

                if not ok and not auth_needed:
                    self.customData['unique_id'] = None
                    self.clear_saved_tokens()
                    self.poly.Notices['LOGIN'] = 'Login Failed - Try again'
                    exit()

                if auth_needed:
                    logging.info('Enter 2FA PIN (message) in AUTH_KEY field and save') 
                    self.poly.Notices['PIN'] = 'Enter 2FA PIN (message) in AUTH_KEY field and save'
                    self.auth_key_updated = False
                    while not self.auth_key_updated:                      
                        logging.debug('Waiting for new pin')
                        time.sleep(3)
                    self.poly.Notices['INIT'] = 'System Initializing - it may take a little while'    
                    self.blink.auth_key(str(self.authKey))

                self.blink.finalize_auth()

                # Save tokens now that startup/2FA and post-verify are complete
                current_auth = self.blink.get_auth_data()
                if current_auth and current_auth.get('refresh_token'):
                    self.save_saved_tokens(current_auth)

                self.poly.Notices.clear()
                #self.add_sync_nodes()
                self.add_network_nodes()

        except Exception as e:
            logging.error('Blink Start Exception: {}'.format(e))
            #self.BLINK_setDriver('ST', 0)

    def add_network_nodes (self):
        logging.info('Adding Blink network nodes:')
        node_adr_list = [self.address]
        network_node_list = self.blink.get_network_list()
        self.network_names = []
        logging.debug(f'Network node list: {network_node_list}')
        logging.debug(f'Parameter list: {self.Parameters}')
        for indx, network in enumerate (network_node_list):
            name = network['name'].upper()
            logging.debug('Processing network {} : {}'.format(name, network))
            if name in self.Parameters:
                if self.Parameters[name][0].upper() == "E":
                    logging.debug('Adding network {}'.format(name)) 
                    self.network_names.append(network['name'])
                    node_address = self.poly.getValidAddress(str(network['id']))
                    node_name = self.poly.getValidName('Blink_'+str(network['name']))
                    logging.info('Adding {} network'.format(node_name))
                    node_adr_list.append(node_address)
                    if not blink_network_node(self.poly, node_address, node_address, node_name, network['id'], self.blink ):
                        logging.error('Failed to create network node for {} '.format(node_name))
            else:
                logging.warning('Network {} not in parameters - adding with default ENABLED value'.format(name))
                self.Parameters[name] = 'ENABLED'
                self.poly.Notices[name] = str(name) + 'network found - Add as custom Parameter with value ENABLED or DISABLED - then restart'         
        logging.debug(f'Parameter list after loop: {self.Parameters}')
        while not self.paramsProcessed:
            time.sleep(5)
            logging.info('waitng to process all parameters')
        #logging.debug('email_info  : {}'.format(self.email_info))
        self.blink.set_email_info(self.email_info)
        self.poly.updateProfile()
        logging.debug('Parameters defined :{}'.format(self.Parameters))
        nodes_in_db = self.poly.getNodesFromDb()
        nodes = self.poly.getNodes()
        
        logging.debug('Checking for nodes not used - node list {} - {} {}'.format(node_adr_list, len(nodes_in_db), nodes_in_db))

        for nde, node in enumerate(nodes_in_db):
            #node = self.nodes_in_db[nde]
            logging.debug('Scanning db for extra nodes : {}'.format(node))
            if node['primaryNode'] not in node_adr_list:
                logging.debug('Removing primary node : {} {}'.format(node['name'], node))
                self.poly.delNode(node['address'])

        self.connected = True

    def stop(self):
        logging.info('Stop Called:')
        self.blink.stop()
        #should I reset the unique_id when logging out - self.customData['unique_id'] = None
        #if 'self.node' in locals():
        #    time.sleep(2)
        
        self.poly.stop()
        exit()
 


    def checkNodes(self):
        logging.info('Updating Nodes')

    def _run_heartbeat(self, heartbeat_cb, node_key):
        try:
            heartbeat_cb()
        except Exception as e:
            logging.error('Heartbeat thread failed for node {}: {}'.format(node_key, e))


    def systemPoll (self, polltype):
        if self.nodeDefineDone:

            if 'longPoll' in polltype:
                logging.info('System Poll executing: {}'.format(polltype))
                #Keep token current
                #self.node.setDriver('GV0', self.temp_unit, True, True)
                try:
                    success = self.blink.refresh()
                    if success:
                        current_auth = self.blink.get_auth_data()
                        if current_auth and current_auth.get('refresh_token'):
                            self.save_saved_tokens(current_auth)
                    nodes = self.poly.getNodes()
                    for nde in nodes:
                        if nde != 'setup':   # but not the setup node
                            if nodes[nde].id == 'blinknetwork' and hasattr(nodes[nde], 'set_connection_status'):
                                logging.debug('Updating connection status for node {} to {}'.format(nde, success))
                                nodes[nde].set_connection_status(True if success else False)
                                if success:
                                    logging.debug('Updating heartbeat for node {}'.format(nde))
                                    heartbeat_cb = getattr(nodes[nde], 'heartbeat', None)
                                    if nodes[nde].id == 'blinknetwork' and callable(heartbeat_cb):
                                        heartbeat_thread = self._heartbeat_threads.get(nde)
                                        if heartbeat_thread and heartbeat_thread.is_alive():
                                            logging.debug('Heartbeat already running for node {}'.format(nde))
                                        else:
                                            logging.debug('Starting heartbeat thread for node {}'.format(nde))
                                            heartbeat_thread = threading.Thread(
                                                target=self._run_heartbeat,
                                                args=(heartbeat_cb, nde),
                                                daemon=True,
                                                name='heartbeat-{}'.format(nde)
                                            )
                                            self._heartbeat_threads[nde] = heartbeat_thread
                                            heartbeat_thread.start()
                                    elif nodes[nde].id == 'blinknetwork':
                                        logging.warning('Node {} is missing callable heartbeat'.format(nde))

                            if success:
                                logging.debug('updating node {} data'.format(nde)) 
                                
                                if nodes[nde].nodeDefineDone and hasattr(nodes[nde], 'updateISYdrivers'):                         
                                    nodes[nde].updateISYdrivers()
                            else:
                                logging.warning('Blink System refresh failed - skipping update drivers for node {}'.format(nde))
                         
                except Exception as e:
                    logging.error('Exception occcured : {}'.format(e))
   
                
            if 'shortPoll' in polltype:
                #if self.connected:
                #    self.heartbeat()
                #else:
                #    logging.warning('System Apperas offline - stopping heartbeat')
                pass
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
        else:
            logging.error('Unknown unit string (first char must be C or F {}'.format(unitS))
        self.blink.set_temp_unit(self.temp_unit)

    def handleData (self, Data ):
        logging.debug('handleData')
        try:
            self.customData.load(Data)
            logging.debug('handleData load - {}'.format(self.customData))
    
            self.poly.Notices.clear()
        except Exception as e:
            logging.error ("Exceptions : {}".format(e))
    
    
    def handleParams (self, customParams ):
        logging.debug('handleParams')
        try:
            self.Parameters.load(customParams)
            logging.debug('handleParams load - {}'.format(customParams))
            self.poly.Notices.clear()
            if 'TEMP_UNIT' in customParams:
                temp = customParams['TEMP_UNIT'].upper()
                if '' == temp or None == temp:
                    self.poly.Notices['TEMP_UNIT'] = 'Missing temp unit (C or F)'                    
                else:
                    if temp[0] == 'C' or temp[0] == 'F':
                        self.temp_unit = temp[0]

            
                if 'TEMP_UNIT' in self.poly.Notices:
                        self.poly.Notices.delete('TEMP_UNIT')

            if 'USERNAME' in customParams:
                new_user = customParams['USERNAME']
                if self.userName is not None and self.userName != '' and self.userName != new_user:
                    logging.info('Username changed in parameters, clearing saved tokens')
                    self.clear_saved_tokens()
                self.userName = new_user
            else:
                self.poly.Notices['userName'] = 'Missing USERNAME parameter'
                self.userName = ''
            
            if 'PASSWORD' in customParams:
                new_pass = customParams['PASSWORD']
                if self.password is not None and self.password != '' and self.password != new_pass:
                    logging.info('Password changed in parameters, clearing saved tokens')
                    self.clear_saved_tokens()
                self.password = new_pass
            else:
                self.poly.Notices['password'] = 'Missing PASSWORD parameter'
                self.password = ''

            if 'AUTH_KEY' in customParams:
                self.authKey = customParams['AUTH_KEY']
                self.auth_key_updated = True
            else:
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

    def heartbeat(self):
        logging.debug('Controller heartbeat: {}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd('DON', 2)
            self.hb = 1
        else:
            self.reportCmd('DOF', 2)
            self.hb = 0
   
    '''
    def set_t_unit(self, command ):
        logging.info('set_t_unit ')
        unit = int(command.get('value'))
        if unit >= 1 and unit <= 3:
            self.temp_unit = unit
            #self.node.setDriver('GV0', self.temp_unit, True, True)
    '''

    #id = 'setup'
    #commands = {
    #            'UPDATE': update,
    #            }

    


    #drivers = [
    #        {'driver': 'ST', 'value':1, 'uom':25}, # node
    #       ]

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        network_interface_ok = False
        while not network_interface_ok:
            try:
                polyglot.getNetworkInterface()
                network_interface_ok = True
            except:
                logging.error('No network connection detected - check if network is down')
                network_interface_ok = False
                time.sleep(15)
        
        BlinkSetup(polyglot, 'setup', 'setup', 'BlinkSetup')

        # Just sit and wait for events
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


