#!/usr/bin/env python3
"""
Polyglot TEST v3 node server 


MIT License
"""
import time
try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)

def BLINK_setDriver(self, key, value, Unit=None):
    logging.debug('BLINK_setDriver : {} {} {}'.format(key, value, Unit))
    if value == None:
        logging.debug('None value passed = seting 99, UOM 25')
        self.node.setDriver(key, 99, True, True, 25)
    else:
        if Unit:
            self.node.setDriver(key, value, True, True, Unit)
        else:
            self.node.setDriver(key, value)

def node_queue(self, data):
    self.n_queue.append(data['address'])

def wait_for_node_done(self):
    while len(self.n_queue) == 0:
        time.sleep(0.1)
    self.n_queue.pop()

def connection2isy(self, connection):
    if connection == 'online':
        state = 1
    elif connection == 'offline':
        state = 0
    elif connection == 'done': # Not sure how to detect state for older cameras
        state = 98
    else:
        logging.error('Unknown status returned : {}'.format(state))
        state = None
    return(state)


def bat2isy(self, bat_status):
    if 'ok'  == bat_status:
        return (0)
    elif 'No Battery' == bat_status:
        return(10)
    else:
        return(None)

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
