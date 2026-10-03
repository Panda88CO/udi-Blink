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
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', req_file, '--user'], env=env)
            user_site = site.getusersitepackages()
            if user_site and user_site not in sys.path and os.path.exists(user_site):
                sys.path.insert(0, user_site)
            import blinkpy
    except Exception:
        pass

from udiBlinkNetworkNode import blink_network_node
from BlinkSystem import blink_system
from udiBlinkLib import parse_enable_state, get_camera_param_info



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



 
VERSION = '0.6.23' 

class BlinkSetup:
    from udiBlinkLib import BLINK_setDriver, bat2isy, bool2isy, bat_V2isy, node_queue, wait_for_node_done, gen_uid
    def  __init__(self, polyglot, primary, address, name):
        self.poly = polyglot
        self.primary = primary
        self.address = address
        self.name = name
        
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
        self.poly.subscribe(self.poly.CONFIGDONE, self.validate_params)
        self.poly.subscribe(self.poly.DISCOVER, self.discover)

        self.auth_key_updated = False

        self.hb = 0
        self._heartbeat_threads = {}
        self.userParam = ['TEMP_UNIT', 'USERNAME','PASSWORD', 'AUTH_KEY', 'SYNC_UNITS' ]
        # logging.debug('BlinkSetup init')
        #logging.debug('self.address : ' + str(self.address))
        #logging.debug('self.name :' + str(self.name))   
        self.poly.ready()
        self.clear_notices()

        self.nodes_in_db = self.poly.getNodesFromDb()
        # logging.debug('BlinkSetup init DONE')
        self.nodeDefineDone = True
        self.start()

    def clear_notices(self):
        try:
            if hasattr(self.poly, 'Notices') and hasattr(self.poly.Notices, 'clear'):
                self.poly.Notices.clear()
            if hasattr(self, 'Notices') and hasattr(self.Notices, 'clear'):
                self.Notices.clear()
            logging.info('Cleared notices on startup')
        except Exception as e:
            logging.debug(f'Error clearing notices on startup: {e}')

    def remove_notice(self, key):
        if not key:
            return
        keys = [str(key)]
        if str(key).upper() != str(key):
            keys.append(str(key).upper())
        if str(key).lower() != str(key):
            keys.append(str(key).lower())

        for k in keys:
            for noticelist in [getattr(self.poly, 'Notices', None), getattr(self, 'Notices', None)]:
                if noticelist is None:
                    continue
                try:
                    if hasattr(noticelist, 'delete'):
                        noticelist.delete(k)
                    elif k in noticelist:
                        del noticelist[k]
                except Exception as e:
                    try:
                        if k in noticelist:
                            del noticelist[k]
                    except Exception:
                        pass

    def validate_params(self):
        # logging.debug('validate_params: {}'.format(self.Parameters.dump()))
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
        # logging.debug('prepare_login_data')
        login_data = {}
        login_data['username'] = self.userName
        login_data['password'] = self.password
        login_data['device_id'] = 'ISY_PG3x'
        login_data['reauth'] = True
        #logging.debug('custom data: {}'.format(self.customData))
        if 'unique_id' in self.customData.keys():
            # logging.debug('uid found: {}'.format(self.customData['unique_id']))
            if self.customData['unique_id'] is not None: 
                login_data['unique_id'] = self.customData['unique_id']
            else:
                login_data['unique_id'] = self.gen_uid(16, True)
                self.customData['unique_id'] = login_data['unique_id']
                # logging.debug('uid created: {}'.format(self.customData['unique_id']))              
        else:
            login_data['unique_id'] = self.gen_uid(16, True)
            self.customData['unique_id'] = login_data['unique_id']
            # logging.debug('uid created: {}'.format(self.customData['unique_id']))

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
            # logging.debug('prepare_login_data included stored auth tokens and hardware_id')

        #logging.debug('prepare_login_data {}'.format(login_data))
        return(login_data)


    def start (self):
        logging.info('Executing start - BlinkSetup')
        try:

            while not self.paramsProcessed or not self.nodeDefineDone:
                logging.info('Waiting for setup to complete param:{} nodes:{}'.format(self.paramsProcessed, self.nodeDefineDone ))
                time.sleep(2)
            #logging.setLevel(10)
            #logging.debug('syncUnits / syncString: {} - {}'.format(self.syncUnits, self.syncUnitString))
            #self.BLINK_setDriver('ST', 1)
            #time.sleep(5)
            # logging.debug('nodeDefineDone {}'.format(self.nodeDefineDone))
            # logging.debug('credentilas : {} {}'.format(self.userName, self.password))

            if self.userName == None or self.userName == '' or self.password==None or self.password=='':
                logging.error('username and password must be provided to start node server')
                self.poly.Notices['un'] = 'username and password must be provided to start node server'
                exit()
            else:
                # logging.debug('STARTING BLINK SYSTEM')
                saved_tokens = self.load_saved_tokens()
                attempt_with_tokens = (saved_tokens is not None and bool(saved_tokens.get('refresh_token')))

                if attempt_with_tokens:
                    logging.info('Found saved tokens. Attempting to start Blink with saved tokens...')
                    self.poly.Notices['TOKEN_INIT'] = 'Starting with stored tokens - this step will take a while...'
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
                    self.remove_notice('TOKEN_INIT')
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
                    self.remove_notice('TOKEN_INIT')
                    self.poly.Notices['LOGIN'] = 'Login Failed - Try again'
                    exit()

                if auth_needed:
                    self.remove_notice('TOKEN_INIT')
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

                for n in ['PIN', 'INIT', 'LOGIN', 'un', 'TOKEN_INIT', 'userName', 'password']:
                    self.remove_notice(n)
                #self.add_sync_nodes()
                self.add_network_nodes()
                self.check_camera_params()
                self._update_dynamic_profile()

        except Exception as e:
            logging.error('Blink Start Exception: {}'.format(e))
            self.remove_notice('TOKEN_INIT')
            #self.BLINK_setDriver('ST', 0)

    def add_network_nodes (self):
        logging.info('Adding Blink network nodes:')
        node_adr_list = [self.address]
        network_node_list = self.blink.get_network_list()
        self.network_names = []
        # logging.debug(f'Network node list: {network_node_list}')
        # logging.debug(f'Parameter list: {self.Parameters}')
        for indx, network in enumerate (network_node_list):
            name = network['name'].upper()
            net_val = self.Parameters.get(name) or self.Parameters.get(network['name'])
            state = parse_enable_state(net_val)
            if net_val is not None:
                if state == 'ENABLED':
                    self.remove_notice(name)
                    self.remove_notice(network['name'])
                    self.network_names.append(network['name'])
                    node_address = self.poly.getValidAddress(str(network['id']))
                    node_name = self.poly.getValidName('Blink_' + str(network['name']))
                    logging.info('Adding {} network'.format(node_name))
                    node_adr_list.append(node_address)
                    net_node = blink_network_node(self.poly, node_address, node_address, node_name, network['id'], self.blink, controller=self)
                    if not net_node:
                        logging.error('Failed to create network node for {} '.format(node_name))
                elif state == 'DISABLED':
                    self.remove_notice(name)
                    self.remove_notice(network['name'])
                    logging.info('Network {} is DISABLED in configuration'.format(name))
                else:
                    self.poly.Notices[name] = str(name) + ' network found - Set value to ENABLED or DISABLED in Custom Parameters and save'
            else:
                logging.warning('Network {} not in parameters - adding with default ENABLED value'.format(name))
                self.Parameters[name] = 'ENABLED'
                self.remove_notice(name)
                self.network_names.append(network['name'])
                node_address = self.poly.getValidAddress(str(network['id']))
                node_name = self.poly.getValidName('Blink_' + str(network['name']))
                logging.info('Adding {} network'.format(node_name))
                node_adr_list.append(node_address)
                net_node = blink_network_node(self.poly, node_address, node_address, node_name, network['id'], self.blink, controller=self)
                if not net_node:
                    logging.error('Failed to create network node for {} '.format(node_name))
        #logging.debug('email_info  : {}'.format(self.email_info))
        self.blink.set_email_info(self.email_info)
        # logging.debug('Parameters defined :{}'.format(self.Parameters))
        nodes_in_db = self.poly.getNodesFromDb()
        nodes = self.poly.getNodes()
        
        # logging.debug('Checking for nodes not used - node list {} - {} {}'.format(node_adr_list, len(nodes_in_db), nodes_in_db))

        for nde, node in enumerate(nodes_in_db):
            #node = self.nodes_in_db[nde]
            # logging.debug('Scanning db for extra nodes : {}'.format(node))
            if node['primaryNode'] not in node_adr_list:
                # logging.debug('Removing primary node : {} {}'.format(node['name'], node))
                self.poly.delNode(node['address'])

        self.connected = True
        self.remove_notice('TOKEN_INIT')

    def check_camera_params(self):
        """
        Check all cameras across enabled networks.
        Sets parameter default 'ENABLED/DISABLED' for any unconfigured cameras.
        Displays notice 'cameras' until ALL cameras have a selected value of either ENABLED or DISABLED.
        """
        if not getattr(self, 'connected', False) or not self.blink or not getattr(self.blink, 'cameras', None):
            return

        pending_cameras = []
        all_networks = self.blink.get_network_list()

        # Determine enabled networks
        enabled_network_ids = set()
        for net in all_networks:
            name = net.get('name', '')
            val = self.Parameters.get(name.upper()) or self.Parameters.get(name)
            if parse_enable_state(val) == 'ENABLED':
                enabled_network_ids.add(str(net.get('id')))

        # If no networks explicitly enabled yet, check all networks
        if not enabled_network_ids:
            enabled_network_ids = {str(net.get('id')) for net in all_networks}

        checked_cams = set()
        for net in all_networks:
            net_id = str(net.get('id'))
            if net_id not in enabled_network_ids:
                continue
            cams = self.blink.get_cameras_on_network(net.get('id'))
            for cam in cams:
                if cam.name in checked_cams:
                    continue
                checked_cams.add(cam.name)
                key, val, state = get_camera_param_info(cam.name, self.Parameters)
                if val is None:
                    logging.info(f"Adding camera parameter {key} with default 'ENABLED/DISABLED'")
                    self.Parameters[key] = 'ENABLED/DISABLED'
                    state = 'PENDING'

                if state == 'PENDING':
                    pending_cameras.append(key)

        if pending_cameras:
            msg = f"New camera(s) found: {', '.join(pending_cameras)}. Please set each parameter in Configuration to either ENABLED or DISABLED and save."
            logging.info(f"Camera notice: {msg}")
            self.poly.Notices['cameras'] = msg
        else:
            logging.info("All cameras have a selected value of either ENABLED or DISABLED. Clearing camera notice.")
            self.remove_notice('cameras')


    def stop(self):
        logging.info('Stop Called:')
        self.remove_notice('TOKEN_INIT')
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
        self.remove_notice('TOKEN_INIT')
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
                            if nodes[nde].id in ('BLINKNETWORK', 'blinknetwork') and hasattr(nodes[nde], 'set_connection_status'):
                                # logging.debug('Updating connection status for node {} to {}'.format(nde, success))
                                nodes[nde].set_connection_status(True if success else False)
                                if success:
                                    # logging.debug('Updating heartbeat for node {}'.format(nde))
                                    heartbeat_cb = getattr(nodes[nde], 'heartbeat', None)
                                    if nodes[nde].id in ('BLINKNETWORK', 'blinknetwork') and callable(heartbeat_cb):
                                        heartbeat_thread = self._heartbeat_threads.get(nde)
                                        if heartbeat_thread and heartbeat_thread.is_alive():
                                            # logging.debug('Heartbeat already running for node {}'.format(nde))
                                            pass
                                        else:
                                            # logging.debug('Starting heartbeat thread for node {}'.format(nde))
                                            heartbeat_thread = threading.Thread(
                                                target=self._run_heartbeat,
                                                args=(heartbeat_cb, nde),
                                                daemon=True,
                                                name='heartbeat-{}'.format(nde)
                                            )
                                            self._heartbeat_threads[nde] = heartbeat_thread
                                            heartbeat_thread.start()
                                    elif nodes[nde].id in ('BLINKNETWORK', 'blinknetwork'):
                                        logging.warning('Node {} is missing callable heartbeat'.format(nde))

                            if success:
                                # logging.debug('updating node {} data'.format(nde)) 
                                
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
        # logging.debug('handleData')
        try:
            self.customData.load(Data)
            # logging.debug('handleData load - {}'.format(self.customData))
        except Exception as e:
            logging.error ("Exceptions : {}".format(e))
    
    
    def handleParams (self, customParams ):
        # logging.debug('handleParams')
        try:
            self.Parameters.load(customParams)
            # logging.debug('handleParams load - {}'.format(customParams))
            if 'TEMP_UNIT' in customParams and customParams['TEMP_UNIT']:
                temp = customParams['TEMP_UNIT'].strip().upper()
                if temp and (temp[0] == 'C' or temp[0] == 'F'):
                    self.temp_unit = temp[0]
                    self.blink.set_temp_unit(self.temp_unit)
                    self.remove_notice('TEMP_UNIT')
                else:
                    self.poly.Notices['TEMP_UNIT'] = 'Invalid TEMP_UNIT parameter (must be C or F)'
            else:
                self.poly.Notices['TEMP_UNIT'] = 'Missing TEMP_UNIT parameter (C or F)'

            if 'USERNAME' in customParams and customParams['USERNAME'].strip():
                new_user = customParams['USERNAME'].strip()
                if self.userName is not None and self.userName != '' and self.userName != new_user:
                    logging.info('Username changed in parameters, clearing saved tokens')
                    self.clear_saved_tokens()
                self.userName = new_user
                self.remove_notice('userName')
            else:
                self.poly.Notices['userName'] = 'Missing USERNAME parameter'
                self.userName = ''
            
            if 'PASSWORD' in customParams and customParams['PASSWORD']:
                new_pass = customParams['PASSWORD']
                if self.password is not None and self.password != '' and self.password != new_pass:
                    logging.info('Password changed in parameters, clearing saved tokens')
                    self.clear_saved_tokens()
                self.password = new_pass
                self.remove_notice('password')
            else:
                self.poly.Notices['password'] = 'Missing PASSWORD parameter'
                self.password = ''

            if self.userName and self.password:
                self.remove_notice('un')
                self.remove_notice('LOGIN')

            if 'AUTH_KEY' in customParams:
                self.authKey = str(customParams['AUTH_KEY']).strip()
                if self.authKey:
                    self.remove_notice('PIN')
                    self.auth_key_updated = True
                else:
                    self.auth_key_updated = False
            else:
                self.authKey = ''
                self.auth_key_updated = False

            # Clear network notices if configured in parameters with explicit selection
            try:
                for key, val in list(customParams.items()):
                    if key not in ['TEMP_UNIT', 'USERNAME', 'PASSWORD', 'AUTH_KEY', 'EMAIL_ENABLED', 'SMTP', 'SMTP_PORT', 'SMTP_EMAIL', 'SMTP_PASSWORD', 'EMAIL_RECEPIENT']:
                        if parse_enable_state(val) in ('ENABLED', 'DISABLED'):
                            self.remove_notice(key)
                            self.remove_notice(key.upper())
            except Exception as e:
                logging.debug(f'Error clearing network notices: {e}')

            if 'EMAIL_ENABLED' in customParams and customParams['EMAIL_ENABLED']:
                self.email_en = customParams['EMAIL_ENABLED'].strip()
                if self.email_en.upper().startswith('T'):
                    self.email_en = True
                else:
                    self.email_en = False
                self.remove_notice('email_en')
            else:
                self.email_en = False
                self.poly.Notices['email_en'] = 'Missing EMAIL_ENABLED parameter (True/False)'
            self.email_info['email_en'] = self.email_en

            if self.email_en:
                if 'SMTP' in customParams and customParams['SMTP'].strip():
                    self.smtp = customParams['SMTP'].strip()
                    self.remove_notice('email_smtp')
                    self.remove_notice('email_smpt')
                else:
                    self.poly.Notices['email_smtp'] = 'Missing SMTP parameter'
                self.email_info['smtp'] = self.smtp

                if 'SMTP_PORT' in customParams and str(customParams['SMTP_PORT']).strip():
                    try:
                        self.smtp_port = int(customParams['SMTP_PORT'])
                    except (ValueError, TypeError):
                        self.smtp_port = 587
                    self.remove_notice('email_port')
                    self.remove_notice('email_smpt')
                else:
                    self.smtp_port = 587
                    self.remove_notice('email_port')
                    self.remove_notice('email_smpt')
                self.email_info['smtp_port'] = self.smtp_port

                if 'SMTP_EMAIL' in customParams and customParams['SMTP_EMAIL'].strip():
                    self.email_sender = customParams['SMTP_EMAIL'].strip()
                    self.remove_notice('email_sender')
                else:
                    self.poly.Notices['email_sender'] = 'Missing SMTP_EMAIL parameter'
                self.email_info['email_sender'] = self.email_sender

                if 'SMTP_PASSWORD' in customParams and customParams['SMTP_PASSWORD']:
                    self.email_password = customParams['SMTP_PASSWORD']
                    self.remove_notice('email_password')
                else:
                    self.poly.Notices['email_password'] = 'Missing SMTP_PASSWORD parameter'
                self.email_info['email_password'] = self.email_password

                if 'EMAIL_RECEPIENT' in customParams and customParams['EMAIL_RECEPIENT'].strip():
                    self.email_recepient = customParams['EMAIL_RECEPIENT'].strip()
                    self.remove_notice('email_recepient')
                else:
                    self.poly.Notices['email_recepient'] = 'Missing EMAIL_RECEPIENT parameter'
                self.email_info['email_recepient'] = self.email_recepient
            else:
                for email_key in ['email_smtp', 'email_smpt', 'email_port', 'email_sender', 'email_password', 'email_recepient']:
                    self.remove_notice(email_key)

            #logging.debug('email_info : {}'.format(self.email_info))
            self.paramsProcessed = True

            if getattr(self, 'connected', False):
                self.check_camera_params()
                try:
                    nodes = self.poly.getNodes()
                    for nde in list(nodes.keys()):
                        node = nodes[nde]
                        if hasattr(node, 'update_cameras'):
                            node.update_cameras()
                except Exception as e:
                    logging.debug(f'Error updating network node cameras in handleParams: {e}')

        except Exception as e:
            logging.debug('Error: {} {}'.format(e, customParams))

    def update(self, command = None):
        self._update_dynamic_profile()
        self.systemPoll(['longPoll'])

    def discover(self, *args, **kwargs):
        logging.info("Discover requested - refreshing profile")
        self._update_dynamic_profile()

    def _update_dynamic_profile(self):
        logging.info("Updating profile (dynamic & static)...")
        json_ok = False
        updater = getattr(self.poly, "updateJsonProfile", None)
        if callable(updater):
            try:
                payload = self._dynamic_profile_payload()
                updater(payload, {"waitResponse": True})
                logging.info("Dynamic JSON profile updated successfully via updateJsonProfile")
                json_ok = True
            except Exception as e:
                logging.warning(f"updateJsonProfile failed: {e}; falling back to updateProfile")
        
        try:
            if hasattr(self.poly, "updateProfile"):
                self.poly.updateProfile()
                logging.info("Static profile updated successfully via updateProfile")
        except Exception as e:
            if not json_ok:
                logging.error(f"updateProfile failed: {e}")

        self.remove_notice("profile")

    def _profile_editors(self):
        return [
            {
                "id": "ONLINE",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1,98,99",
                        "names": {
                            "0": "Offline",
                            "1": "Online",
                            "98": "No support",
                            "99": "Unknown",
                        },
                    }
                ],
            },
            {
                "id": "ARMED",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1,2,99",
                        "names": {
                            "0": "Disarmed",
                            "1": "Armed",
                            "2": "Individually Camera Assigned",
                            "99": "Unknown",
                        },
                    }
                ],
            },
            {
                "id": "DOARM",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1",
                        "names": {
                            "0": "Disarm",
                            "1": "Arm",
                        },
                    }
                ],
            },
            {
                "id": "DOMOTION",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1",
                        "names": {
                            "0": "Disabled",
                            "1": "Enabled",
                        },
                    }
                ],
            },
            {
                "id": "BATTERY",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1,2,10,99",
                        "names": {
                            "0": "OK",
                            "1": "Not OK - TBD",
                            "2": "TBD",
                            "10": "USB powered",
                            "99": "Unknown",
                        },
                    }
                ],
            },
            {
                "id": "CAMERATYPE",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1,2,3,4,5,6,7,8,9,10,11,99",
                        "names": {
                            "0": "Mini",
                            "1": "DoorBell",
                            "2": "Blink Outdoor",
                            "3": "XT-2",
                            "4": "Wired Flood Light",
                            "5": "Indoor/Outdoor gen3",
                            "6": "Outdoor v4",
                            "7": "Mini 2",
                            "8": "Indoor/Outdoor gen2",
                            "9": "Indoor v4",
                            "10": "Mini 2K+",
                            "11": "Outdoor2K+",
                            "99": "Unknown",
                        },
                    }
                ],
            },
            {
                "id": "MOTIONEN",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1,99",
                        "names": {
                            "0": "Disabled",
                            "1": "Enabled",
                            "99": "Unknown",
                        },
                    }
                ],
            },
            {
                "id": "MOTIONDETC",
                "ranges": [
                    {
                        "uom": "25",
                        "subset": "0,1,99",
                        "names": {
                            "0": "No Motion",
                            "1": "Motion Detected",
                            "99": "Unknown",
                        },
                    }
                ],
            },
            {
                "id": "TEMPF",
                "ranges": [
                    {
                        "uom": "17",
                        "min": -40,
                        "max": 221,
                        "prec": 1,
                    }
                ],
            },
            {
                "id": "TEMPC",
                "ranges": [
                    {
                        "uom": "4",
                        "min": -40,
                        "max": 105,
                        "prec": 1,
                    }
                ],
            },
            {
                "id": "UNIXTIME",
                "ranges": [
                    {
                        "uom": "151",
                        "min": 0,
                        "max": 9999999999,
                        "prec": 0,
                    }
                ],
            },
        ]

    def _profile_nodedefs(self):
        camera_cmds = {
            "sends": [],
            "accepts": [
                {"id": "UPDATE", "name": "Update Camera"},
                {
                    "id": "ARM",
                    "name": "Set Motion Detection",
                    "parameters": [
                        {"id": "", "editor": "DOMOTION", "init": "GV0"},
                    ],
                },
                {"id": "SNAPPIC", "name": "Take Picture"},
                {"id": "SNAPVIDEO", "name": "Take Video"},
            ],
        }

        return [
            {
                "id": "BLINKSYNC",
                "name": "Sync Unit",
                "icon": "GenericCtl",
                "properties": [
                    {"id": "ST", "editor": "ONLINE", "name": "Connected"},
                ],
                "cmds": {
                    "sends": [],
                    "accepts": [
                        {"id": "UPDATE", "name": "Update SyncUnit"},
                    ],
                },
                "links": {"ctl": [], "rsp": []},
            },
            {
                "id": "BLINKNETWORK",
                "name": "Network",
                "icon": "GenericCtl",
                "properties": [
                    {"id": "ST", "editor": "ONLINE", "name": "Connected"},
                    {"id": "GV0", "editor": "ARMED", "name": "Arm Status"},
                    {"id": "TIME", "editor": "UNIXTIME", "name": "Last Successful Update Time"},
                ],
                "cmds": {
                    "sends": [
                        {"id": "DON", "name": "On"},
                        {"id": "DOF", "name": "Off"},
                    ],
                    "accepts": [
                        {"id": "UPDATE", "name": "Update Network"},
                        {
                            "id": "ARMALL",
                            "name": "Set Arming",
                            "parameters": [
                                {"id": "", "editor": "DOARM", "init": "GV0"},
                            ],
                        },
                    ],
                },
                "links": {"ctl": [], "rsp": []},
            },
            {
                # Camera without temperature measurement - CLITEMP completely omitted
                "id": "BLINKCAMERA",
                "name": "Blink Camera",
                "icon": "MotionSensor",
                "properties": [
                    {"id": "ST", "editor": "ONLINE", "name": "Connected"},
                    {"id": "GV0", "editor": "MOTIONEN", "name": "Motion Detection Status"},
                    {"id": "GV1", "editor": "BATTERY", "name": "Battery Status"},
                    {"id": "GV3", "editor": "CAMERATYPE", "name": "CameraType"},
                    {"id": "GV5", "editor": "MOTIONDETC", "name": "Motion Detected"},
                    {"id": "TIME", "editor": "UNIXTIME", "name": "Last Update TIME"},
                ],
                "cmds": camera_cmds,
                "links": {"ctl": [], "rsp": []},
            },
            {
                # Camera with Celsius temperature measurement
                "id": "BLINKCAMERAC",
                "name": "Blink Camera",
                "icon": "MotionSensor",
                "properties": [
                    {"id": "ST", "editor": "ONLINE", "name": "Connected"},
                    {"id": "GV0", "editor": "MOTIONEN", "name": "Motion Detection Status"},
                    {"id": "GV1", "editor": "BATTERY", "name": "Battery Status"},
                    {"id": "GV3", "editor": "CAMERATYPE", "name": "CameraType"},
                    {"id": "GV5", "editor": "MOTIONDETC", "name": "Motion Detected"},
                    {"id": "CLITEMP", "editor": "TEMPC", "name": "Temperature"},
                    {"id": "TIME", "editor": "UNIXTIME", "name": "Last Update TIME"},
                ],
                "cmds": camera_cmds,
                "links": {"ctl": [], "rsp": []},
            },
            {
                # Camera with Fahrenheit temperature measurement
                "id": "BLINKCAMERAF",
                "name": "Blink Camera",
                "icon": "MotionSensor",
                "properties": [
                    {"id": "ST", "editor": "ONLINE", "name": "Connected"},
                    {"id": "GV0", "editor": "MOTIONEN", "name": "Motion Detection Status"},
                    {"id": "GV1", "editor": "BATTERY", "name": "Battery Status"},
                    {"id": "GV3", "editor": "CAMERATYPE", "name": "CameraType"},
                    {"id": "GV5", "editor": "MOTIONDETC", "name": "Motion Detected"},
                    {"id": "CLITEMP", "editor": "TEMPF", "name": "Temperature"},
                    {"id": "TIME", "editor": "UNIXTIME", "name": "Last Update TIME"},
                ],
                "cmds": camera_cmds,
                "links": {"ctl": [], "rsp": []},
            },
        ]

    def _dynamic_profile_payload(self):
        return {
            "delete": {
                "editors": ["*"],
                "nodedefs": ["*"],
                "linkdefs": ["*"],
            },
            "editors": self._profile_editors(),
            "nodedefs": self._profile_nodedefs(),
            "linkdefs": [],
        }

    def reportCmd(self, command, value=None):
        pass

    def heartbeat(self):
        # logging.debug('Controller heartbeat: {}'.format(self.hb))
        if self.hb == 0:
            self.hb = 1
        else:
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


