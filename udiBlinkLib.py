#!/usr/bin/env python3
"""
Polyglot TEST v3 node server 


MIT License
"""
import time
import secrets
import re
try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)

def BLINK_setDriver(self, key, value, Unit=None):
    # logging.debug('BLINK_setDriver : {} {} {}'.format(key, value, Unit))
    target = getattr(self, 'node', None) or self
    if value == None:
        # logging.debug('None value passed = seting 99, UOM 25')
        target.setDriver(key, 99, True, False, 25)
    else:
        if Unit:
            target.setDriver(key, value, True, False, Unit)
        else:
            target.setDriver(key, value, True, False)

def node_queue(self, data):
    if data and data.get('address') == self.address:
        self.n_queue.append(data['address'])

def wait_for_node_done(self):
    start_t = time.time()
    while self.address not in self.n_queue:
        if time.time() - start_t > 15:
            logging.warning('Timeout waiting for node {} to be added'.format(self.address))
            break
        time.sleep(0.05)
    if self.address in self.n_queue:
        self.n_queue.remove(self.address)

def connection2isy(self, connection):
    if connection == 'online':
        state = 1
    elif connection == 'offline':
        state = 0
    elif connection == 'done': # Not sure how to detect state for older cameras
        state = 98
    else:
        logging.error('Unknown status returned : {}'.format(connection))
        state = None
    return(state)


def bat2isy(self, bat_status):
    if bat_status is None:
        return None
    if isinstance(bat_status, (int, float)):
        if bat_status in (2, 3):
            return 0
        elif bat_status in (0, 1):
            return 1
        elif bat_status == 10:
            return 10
        return None
    s = str(bat_status).strip().lower()
    if s == 'ok':
        return 0
    elif s in ('low', 'warning', 'bad'):
        return 1
    elif 'no battery' in s or 'usb powered' in s or s == 'none':
        return 10
    else:
        return None

def bat_V2isy (self, bat_status):
    if isinstance(bat_status, int):
        return (bat_status)
    elif 'No Battery' == bat_status:
        return(98)
    else:
        return(None)

def bool2isy(self, val):
    if val == True:
        return(1)
    elif val == False:
        return(0)
    else:
        return(None)

def gen_uid(self, size, uid_format=False):
    """Create a random sring."""
    if uid_format:
        token = f"Blink_{secrets.token_hex(4)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(6)}"
    else:
        token = secrets.token_hex(size)
    return token

def parse_enable_state(val):
    if val is None:
        return 'PENDING'
    v = str(val).strip().upper()
    if not v or v in ('ENABLED/DISABLED', 'ENABLE/DISABLE', 'ENABLED / DISABLED', 'ENABLE / DISABLE', 'PENDING', 'NONE', 'DEFAULT'):
        return 'PENDING'
    if v in ('ENABLED', 'ENABLE', 'TRUE', '1', 'YES', 'ON') or (v.startswith('E') and 'DISABLE' not in v):
        return 'ENABLED'
    if v in ('DISABLED', 'DISABLE', 'FALSE', '0', 'NO', 'OFF') or (v.startswith('D') and 'ENABLE' not in v):
        return 'DISABLED'
    return 'PENDING'
