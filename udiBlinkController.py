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
import uuid
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
from udiBlinkLib import parse_enable_state



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



VERSION = '0.6.32' 
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blink_tokens.json') 

def _sync_version_file():
    """Ensure version.txt and profile version stay synchronized with VERSION in code"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 1. Sync root version.txt
        ver_file = os.path.join(base_dir, 'version.txt')
        cur_version = None
        if os.path.exists(ver_file):
            with open(ver_file, 'r') as f:
                cur_version = f.read().strip()
        if cur_version != VERSION:
            with open(ver_file, 'w') as f:
                f.write(VERSION + '\n')
            logging.info(f'Synchronized version.txt to VERSION {VERSION}')

        # 2. Sync profile/version.txt (only if profile directory exists)
        prof_dir = os.path.join(base_dir, 'profile')
        if os.path.isdir(prof_dir):
            prof_ver_file = os.path.join(prof_dir, 'version.txt')
            cur_prof_version = None
            if os.path.exists(prof_ver_file):
                with open(prof_ver_file, 'r') as f:
                    cur_prof_version = f.read().strip()
            if cur_prof_version != VERSION:
                with open(prof_ver_file, 'w') as f:
                    f.write(VERSION + '\n')
                logging.info(f'Synchronized profile/version.txt to VERSION {VERSION}')

        # 3. Sync server.json (version, profile_version, credits)
        server_json_file = os.path.join(base_dir, 'server.json')
        if os.path.exists(server_json_file):
            with open(server_json_file, 'r') as f:
                s_data = json.load(f)
            changed = False
            if s_data.get('version') != VERSION:
                s_data['version'] = VERSION
                changed = True
            if s_data.get('profile_version') != VERSION:
                s_data['profile_version'] = VERSION
                changed = True
            if s_data.get('credits') and isinstance(s_data['credits'], list) and len(s_data['credits']) > 0:
                if s_data['credits'][0].get('version') != VERSION:
                    s_data['credits'][0]['version'] = VERSION
                    changed = True
            if changed:
                with open(server_json_file, 'w') as f:
                    json.dump(s_data, f, indent=4)
                    f.write('\n')
                logging.info(f'Synchronized server.json to VERSION {VERSION}')

    except Exception as e:
        logging.debug(f'Could not sync version files: {e}')

_sync_version_file()

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

        self.paramsProcessed = False
        self.dataProcessed = False
        self.configDone = False
        self.auth_key_updated = False
        self.connected = False
        self._is_starting = False
        self._start_lock = threading.Lock()
        self.waiting_for_2fa = False

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
        threading.Thread(target=self.start, daemon=True, name='BlinkStart').start()

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

    def validate_params(self, *args, **kwargs):
        logging.info('Configuration validated from Polyglot (CONFIGDONE)')
        self.paramsProcessed = True    
        self.dataProcessed = True
        self.configDone = True    

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

        # If not in customData, try TOKEN_FILE and local file fallback
        if not tokens or not isinstance(tokens, dict) or not tokens.get('refresh_token'):
            for path in [TOKEN_FILE, 'blink_tokens.json']:
                if os.path.exists(path):
                    try:
                        with open(path, 'r') as f:
                            file_tokens = json.load(f)
                        if isinstance(file_tokens, dict) and file_tokens.get('refresh_token'):
                            tokens = file_tokens
                            logging.debug(f'Loaded auth_tokens from {path}')
                            try:
                                self.customData['auth_tokens'] = tokens
                                if tokens.get('hardware_id'):
                                    self.customData['hardware_id'] = tokens['hardware_id']
                            except Exception:
                                pass
                            break
                    except Exception as e:
                        logging.error(f'Error reading {path}: {e}')

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
            if auth_data.get('hardware_id'):
                self.customData['hardware_id'] = auth_data['hardware_id']
        except Exception as e:
            logging.error(f'Error storing auth_tokens in customData: {e}')
        try:
            with open(TOKEN_FILE, 'w') as f:
                json.dump(auth_data, f, indent=2)
            os.chmod(TOKEN_FILE, 0o600)
            logging.debug(f'Auth tokens saved to {TOKEN_FILE}')
        except Exception as e:
            logging.error(f'Failed to save {TOKEN_FILE}: {e}')

    def clear_saved_tokens(self):
        logging.info('Clearing stored Blink authentication tokens')
        try:
            self.customData['auth_tokens'] = None
        except Exception as e:
            logging.error(f'Error clearing auth_tokens from customData: {e}')
        for path in [TOKEN_FILE, 'blink_tokens.json']:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logging.error(f'Error removing {path}: {e}')

    def prepare_login_data(self, auth_tokens=None):
        login_data = {}
        login_data['username'] = self.userName
        login_data['password'] = self.password
        login_data['reauth'] = True

        # Resolve persistent hardware_id (must be a valid uppercase UUID for Blink OAuth v2)
        hardware_id = None
        if auth_tokens and isinstance(auth_tokens, dict) and auth_tokens.get('hardware_id'):
            hardware_id = auth_tokens.get('hardware_id')
        elif hasattr(self, 'customData') and 'hardware_id' in self.customData and self.customData['hardware_id']:
            hardware_id = self.customData['hardware_id']

        if hardware_id:
            try:
                hardware_id = str(uuid.UUID(str(hardware_id))).upper()
            except (ValueError, TypeError):
                hardware_id = None

        if not hardware_id:
            hardware_id = str(uuid.uuid4()).upper()
            try:
                self.customData['hardware_id'] = hardware_id
            except Exception:
                pass

        login_data['hardware_id'] = hardware_id
        # In Blink OAuth v2, device_id must match hardware_id (valid UUID)
        login_data['device_id'] = hardware_id

        # Maintain unique_id for backward compatibility
        if hasattr(self, 'customData') and 'unique_id' in self.customData and self.customData['unique_id'] is not None:
            login_data['unique_id'] = self.customData['unique_id']
        else:
            login_data['unique_id'] = hardware_id
            try:
                self.customData['unique_id'] = hardware_id
            except Exception:
                pass

        if auth_tokens and isinstance(auth_tokens, dict):
            for k in [
                'token',
                'refresh_token',
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

        return login_data


    def start (self):
        with self._start_lock:
            if self._is_starting:
                logging.info('Blink start/auth already in progress, ignoring duplicate start call')
                return
            if getattr(self, 'connected', False):
                logging.info('Already connected to Blink, ignoring duplicate start call')
                return
            self._is_starting = True

        logging.info('Executing start - BlinkSetup')
        try:
            wait_count = 0
            max_wait = 15  # wait up to 30 seconds (15 * 2s)
            while (not (self.paramsProcessed and self.dataProcessed) or not self.nodeDefineDone) and wait_count < max_wait:
                logging.info('Waiting for setup to complete param:{} data:{} nodes:{} (wait {}/{})'.format(
                    self.paramsProcessed, self.dataProcessed, self.nodeDefineDone, wait_count + 1, max_wait
                ))
                time.sleep(2)
                wait_count += 1
                if not self.paramsProcessed and len(self.Parameters) > 0:
                    logging.info('Parameters found in self.Parameters, processing now')
                    self.handleParams(dict(self.Parameters))
                if not self.dataProcessed and len(self.customData) > 0:
                    logging.info('Custom data found in self.customData, marking processed')
                    self.dataProcessed = True
                if self.paramsProcessed and self.dataProcessed and self.nodeDefineDone:
                    break

            self.paramsProcessed = True
            self.dataProcessed = True

            if not self.userName or not self.password:
                logging.warning('USERNAME and PASSWORD not provided - please configure in Polyglot custom parameters')
                self.poly.Notices['un'] = 'Username and Password must be provided in Custom Parameters to start node server'
                return
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
                max_retries = 3 if attempt_with_tokens else 1
                for attempt in range(max_retries):
                    try:
                        ok = self.blink.start()
                    except Exception as e:
                        logging.error(f'Exception during blink start (attempt {attempt + 1}/{max_retries}): {e}')
                        ok = False

                    auth_needed = self.blink.key_required
                    logging.debug(f'Auth step 1 (attempt {attempt + 1}/{max_retries}): ok={ok}, 2FA required={auth_needed}')
                    if ok or auth_needed:
                        break
                    if attempt < max_retries - 1:
                        logging.info(f'Blink start attempt {attempt + 1} failed, retrying in 5 seconds...')
                        time.sleep(5)

                # If starting with saved tokens failed and it's NOT a network error, and NOT waiting for 2FA:
                if attempt_with_tokens and not ok and not auth_needed:
                    if getattr(self.blink, 'is_network_error', False):
                        logging.warning(f'Blink start failed due to network error ({getattr(self.blink, "last_error", "Unknown")}). Keeping saved tokens and not restarting fresh.')
                        self.remove_notice('TOKEN_INIT')
                        self.poly.Notices['LOGIN'] = 'Blink connection failed (network error) - will retry on next poll'
                        return
                    else:
                        logging.warning('Starting with saved tokens failed (auth rejected). Clearing tokens and restarting fresh login...')
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
                    self.poly.Notices['LOGIN'] = 'Login Failed - Check USERNAME/PASSWORD and save to retry'
                    return

                if auth_needed:
                    self.remove_notice('TOKEN_INIT')
                    logging.info('Enter 2FA PIN (message) in AUTH_KEY field and save') 
                    self.poly.Notices['PIN'] = 'Enter 2FA PIN (message) in AUTH_KEY field and save'
                    self.waiting_for_2fa = True
                    pin_ok = False
                    while not pin_ok:
                        self.auth_key_updated = False
                        while not self.auth_key_updated:                      
                            logging.debug('Waiting for new pin')
                            time.sleep(3)
                        self.poly.Notices['INIT'] = 'Verifying 2FA PIN...'    
                        auth_res = self.blink.auth_key(str(self.authKey))
                        if auth_res is True or auth_res == 'ok':
                            self.remove_notice('PIN')
                            self.poly.Notices['INIT'] = 'Processing data - it may take a while'
                            try:
                                self.blink.finalize_auth()
                                pin_ok = True
                            except Exception as e:
                                logging.error(f'Error finalizing auth: {e}')
                                self.poly.Notices['PIN'] = 'Error finalizing auth - please re-enter PIN in AUTH_KEY and save'
                                self.remove_notice('INIT')
                        else:
                            logging.warning(f'2FA PIN verification failed: {auth_res}')
                            self.poly.Notices['PIN'] = '2FA PIN verification failed - enter correct PIN in AUTH_KEY and save'
                            self.remove_notice('INIT')
                    self.waiting_for_2fa = False
                    self.remove_notice('PIN')
                    if hasattr(self, 'Parameters') and 'AUTH_KEY' in self.Parameters:
                        try:
                            self.Parameters['AUTH_KEY'] = ''
                        except Exception:
                            pass

                # Save tokens now that startup/2FA and post-verify are complete
                current_auth = self.blink.get_auth_data()
                if current_auth and current_auth.get('refresh_token'):
                    self.save_saved_tokens(current_auth)

                for n in ['PIN', 'LOGIN', 'un', 'TOKEN_INIT', 'userName', 'password']:
                    self.remove_notice(n)
                self.poly.Notices['INIT'] = 'Processing data - it may take a while'

                #self.add_sync_nodes()
                self.add_network_nodes()
                self._update_dynamic_profile()
                self.remove_notice('INIT')

        except Exception as e:
            logging.error('Blink Start Exception: {}'.format(e), exc_info=True)
            self.remove_notice('TOKEN_INIT')
            self.remove_notice('INIT')
            #self.BLINK_setDriver('ST', 0)
        finally:
            self._is_starting = False
            self.waiting_for_2fa = False
            self.remove_notice('INIT')

    def add_network_nodes (self):
        logging.info('Adding Blink network nodes:')
        node_adr_list = [self.address]
        network_node_list = self.blink.get_network_list()
        self.network_names = []

        if not network_node_list:
            logging.warning('No networks found in Blink homescreen data - skipping node sync to prevent accidental removal')
            return

        # Remove leftover camera notices and clean up old CAM_ parameters if present
        self.remove_notice('cameras')
        if hasattr(self, 'Parameters') and self.Parameters:
            cam_keys = [k for k in list(self.Parameters.keys()) if k.startswith('CAM_')]
            for k in cam_keys:
                try:
                    if hasattr(self.Parameters, 'delete'):
                        self.Parameters.delete(k)
                    else:
                        del self.Parameters[k]
                except Exception as e:
                    logging.debug(f'Error deleting camera parameter {k}: {e}')

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
                    node_adr_list.append(node_address)
                    existing = self.poly.getNode(node_address)
                    if not existing:
                        logging.info('Adding {} network'.format(node_name))
                        net_node = blink_network_node(self.poly, node_address, node_address, node_name, network['id'], self.blink, controller=self)
                        if not net_node:
                            logging.error('Failed to create network node for {} '.format(node_name))
                        elif not getattr(net_node, '_started', False):
                            net_node.start()
                    else:
                        logging.info('Network {} already exists'.format(node_name))
                elif state == 'DISABLED':
                    self.remove_notice(name)
                    self.remove_notice(network['name'])
                    logging.info('Network {} is DISABLED in configuration'.format(name))
                else:
                    self.poly.Notices[name] = str(name) + ' network found - Set value to ENABLED or DISABLED in Custom Parameters and save'
            else:
                logging.info('Network {} not in parameters - setting default ENABLED/DISABLED'.format(name))
                self.Parameters[name] = 'ENABLED/DISABLED'
                self.poly.Notices[name] = str(name) + ' network found - Set value to ENABLED or DISABLED in Custom Parameters and save'

        self.blink.set_email_info(self.email_info)
        nodes_in_db = self.poly.getNodesFromDb()
        for nde, node in enumerate(nodes_in_db):
            if node['primaryNode'] not in node_adr_list:
                self.poly.delNode(node['address'])

        self.connected = True
        self.remove_notice('TOKEN_INIT')


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
                    else:
                        logging.warning('Blink System refresh failed - skipping driver updates')
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
        try:
            import logging as std_logging
            std_logging.getLogger('blinkpy').setLevel(level['level'])
        except Exception:
            pass

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
        self.dataProcessed = True
    
    
    def handleParams (self, customParams ):
        logging.info('Received custom parameters from Polyglot')
        try:
            if customParams is None:
                customParams = {}
            elif not isinstance(customParams, dict):
                try:
                    customParams = dict(customParams)
                except Exception:
                    customParams = {}

            self.Parameters.load(customParams)
            # logging.debug('handleParams load - {}'.format(customParams))
            if 'TEMP_UNIT' in customParams and customParams['TEMP_UNIT']:
                temp = str(customParams['TEMP_UNIT']).strip().upper()
                if temp and (temp[0] == 'C' or temp[0] == 'F'):
                    self.temp_unit = temp[0]
                    self.blink.set_temp_unit(self.temp_unit)
                    self.remove_notice('TEMP_UNIT')
                else:
                    self.poly.Notices['TEMP_UNIT'] = 'Invalid TEMP_UNIT parameter (must be C or F)'
            else:
                self.poly.Notices['TEMP_UNIT'] = 'Missing TEMP_UNIT parameter (C or F)'

            if 'USERNAME' in customParams and str(customParams['USERNAME']).strip():
                new_user = str(customParams['USERNAME']).strip()
                if self.userName is not None and self.userName != '' and self.userName != new_user:
                    logging.info('Username changed in parameters, clearing saved tokens')
                    self.clear_saved_tokens()
                    self.connected = False
                self.userName = new_user
                self.remove_notice('userName')
            else:
                self.poly.Notices['userName'] = 'Missing USERNAME parameter'
                self.userName = ''
            
            if 'PASSWORD' in customParams and customParams['PASSWORD']:
                new_pass = str(customParams['PASSWORD'])
                if self.password is not None and self.password != '' and self.password != new_pass:
                    logging.info('Password changed in parameters, clearing saved tokens')
                    self.clear_saved_tokens()
                    self.connected = False
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

            if 'EMAIL_ENABLED' in customParams and customParams['EMAIL_ENABLED'] is not None:
                val = str(customParams['EMAIL_ENABLED']).strip().upper()
                if val.startswith('T') or val == '1':
                    self.email_en = True
                else:
                    self.email_en = False
                self.remove_notice('email_en')
            else:
                self.email_en = False
                if hasattr(self, 'Parameters') and 'EMAIL_ENABLED' not in self.Parameters:
                    self.Parameters['EMAIL_ENABLED'] = 'False'
                self.remove_notice('email_en')
            self.email_info['email_en'] = self.email_en

            email_param_keys = ['SMTP', 'SMTP_PORT', 'SMTP_EMAIL', 'SMTP_PASSWORD', 'EMAIL_RECEPIENT']

            if self.email_en:
                default_email_values = {
                    'SMTP': 'SMTPServer',
                    'SMTP_PORT': '587',
                    'SMTP_EMAIL': 'serverlogin',
                    'SMTP_PASSWORD': 'server password',
                    'EMAIL_RECEPIENT': "receiver's email"
                }

                # Check for previously saved email credentials in customData
                saved_config = {}
                try:
                    if 'saved_email_config' in self.customData and isinstance(self.customData['saved_email_config'], dict):
                        saved_config = self.customData['saved_email_config']
                except Exception:
                    pass

                # Expose email parameters in self.Parameters if not already present
                if hasattr(self, 'Parameters'):
                    for k, default_val in default_email_values.items():
                        if k not in self.Parameters:
                            val_to_use = saved_config.get(k, default_val)
                            self.Parameters[k] = val_to_use

                smtp_val = customParams.get('SMTP') or (self.Parameters.get('SMTP') if hasattr(self, 'Parameters') else '')
                if smtp_val and str(smtp_val).strip() and str(smtp_val).strip() != 'SMTPServer':
                    self.smtp = str(smtp_val).strip()
                    self.remove_notice('email_smtp')
                    self.remove_notice('email_smpt')
                else:
                    self.smtp = None
                    self.poly.Notices['email_smtp'] = 'Configure SMTP parameter'
                self.email_info['smtp'] = self.smtp

                port_val = customParams.get('SMTP_PORT') or (self.Parameters.get('SMTP_PORT') if hasattr(self, 'Parameters') else '587')
                try:
                    self.smtp_port = int(str(port_val).strip())
                except (ValueError, TypeError):
                    self.smtp_port = 587
                self.remove_notice('email_port')
                self.remove_notice('email_smpt')
                self.email_info['smtp_port'] = self.smtp_port

                sender_val = customParams.get('SMTP_EMAIL') or (self.Parameters.get('SMTP_EMAIL') if hasattr(self, 'Parameters') else '')
                if sender_val and str(sender_val).strip() and str(sender_val).strip() != 'serverlogin':
                    self.email_sender = str(sender_val).strip()
                    self.remove_notice('email_sender')
                else:
                    self.email_sender = None
                    self.poly.Notices['email_sender'] = 'Configure SMTP_EMAIL parameter'
                self.email_info['email_sender'] = self.email_sender

                pass_val = customParams.get('SMTP_PASSWORD') or (self.Parameters.get('SMTP_PASSWORD') if hasattr(self, 'Parameters') else '')
                if pass_val and str(pass_val) and str(pass_val) != 'server password':
                    self.email_password = str(pass_val)
                    self.remove_notice('email_password')
                else:
                    self.email_password = None
                    self.poly.Notices['email_password'] = 'Configure SMTP_PASSWORD parameter'
                self.email_info['email_password'] = self.email_password

                recep_val = customParams.get('EMAIL_RECEPIENT') or (self.Parameters.get('EMAIL_RECEPIENT') if hasattr(self, 'Parameters') else '')
                if recep_val and str(recep_val).strip() and str(recep_val).strip() not in ("receiver's email", "receiver''''s email"):
                    self.email_recepient = str(recep_val).strip()
                    self.remove_notice('email_recepient')
                else:
                    self.email_recepient = None
                    self.poly.Notices['email_recepient'] = 'Configure EMAIL_RECEPIENT parameter'
                self.email_info['email_recepient'] = self.email_recepient
            else:
                # Email disabled: clean up notices
                for email_key in ['email_smtp', 'email_smpt', 'email_port', 'email_sender', 'email_password', 'email_recepient']:
                    self.remove_notice(email_key)

                # Save any user-entered values before deleting, so they can be restored if re-enabled
                saved_email = {}
                for k in email_param_keys:
                    val = customParams.get(k) or (self.Parameters.get(k) if hasattr(self, 'Parameters') else None)
                    if val is not None and str(val).strip() not in ('SMTPServer', '587', 'serverlogin', 'server password', "receiver's email", "receiver''''s email", ''):
                        saved_email[k] = str(val).strip()
                if saved_email:
                    try:
                        self.customData['saved_email_config'] = saved_email
                    except Exception:
                        pass

                # Remove the 5 email parameters from self.Parameters so they are not exposed in Polyglot UI
                if hasattr(self, 'Parameters') and self.Parameters:
                    for k in email_param_keys:
                        if k in self.Parameters:
                            try:
                                if hasattr(self.Parameters, 'delete'):
                                    self.Parameters.delete(k)
                                else:
                                    del self.Parameters[k]
                            except Exception as e:
                                logging.debug(f'Error deleting {k} from Parameters: {e}')

            if hasattr(self, 'blink') and self.blink:
                self.blink.set_email_info(self.email_info)

            if getattr(self, 'connected', False):
                self.add_network_nodes()
                try:
                    nodes = self.poly.getNodes()
                    for nde in list(nodes.keys()):
                        node = nodes[nde]
                        if hasattr(node, 'update_cameras'):
                            node.update_cameras()
                except Exception as e:
                    logging.debug(f'Error updating network node cameras in handleParams: {e}')
                self._update_dynamic_profile()
            elif not self._is_starting:
                if self.userName and self.password:
                    logging.info('Credentials available in handleParams, starting Blink connection')
                    threading.Thread(target=self.start, daemon=True, name='BlinkStart').start()
            else:
                logging.debug('Blink start/auth already in progress; updated credentials/parameters')

        except Exception as e:
            logging.error(f'Error in handleParams: {e}', exc_info=True)
        finally:
            self.paramsProcessed = True

    def update(self, command = None):
        self._update_dynamic_profile()
        self.systemPoll(['longPoll'])

    def discover(self, *args, **kwargs):
        logging.info("Discover requested - refreshing profile")
        self._update_dynamic_profile()

    def _update_dynamic_profile(self):
        profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'profile')
        if os.path.isdir(profile_dir):
            logging.info("Updating profile (dynamic & static)...")
        else:
            logging.info("Updating profile (dynamic)...")

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
        
        # Only update static profile if the directory exists
        if os.path.isdir(profile_dir):
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
                        "subset": "0,1,2,3,10,99",
                        "names": {
                            "0": "OK",
                            "1": "Not OK - TBD",
                            "2": "TBD",
                            "3": "External / Wired",
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
                        {"id": "", "editor": "DOMOTION", "init": "ST"},
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
                    {"id": "ST", "editor": "ARMED", "name": "Arm Status"},
                    {"id": "GV0", "editor": "ONLINE", "name": "Connected"},
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
                                {"id": "", "editor": "DOARM", "init": "ST"},
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
                    {"id": "ST", "editor": "MOTIONEN", "name": "Motion Detection Status"},
                    {"id": "GV0", "editor": "ONLINE", "name": "Connected"},
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
                    {"id": "ST", "editor": "MOTIONEN", "name": "Motion Detection Status"},
                    {"id": "GV0", "editor": "ONLINE", "name": "Connected"},
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
                    {"id": "ST", "editor": "MOTIONEN", "name": "Motion Detection Status"},
                    {"id": "GV0", "editor": "ONLINE", "name": "Connected"},
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


