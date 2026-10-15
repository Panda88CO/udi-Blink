#!/usr/bin/env python3
"""
Polyglot TEST v3 node server 


MIT License
"""
import time
import secrets
import re
import os
import xml.etree.ElementTree as ET
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
    if isinstance(bat_status, bool):
        return 3 if bat_status else None
    if isinstance(bat_status, (int, float)):
        if bat_status in (2, 3):
            return 0
        elif bat_status in (0, 1):
            return 1
        elif bat_status == 10:
            return 10
        return None
    s = str(bat_status).strip().lower()
    if s in ('ok', 'good', 'full', 'normal'):
        return 0
    elif s in ('low', 'warning', 'bad', 'replace'):
        return 1
    elif s in ('wired', 'external', 'ac', 'line', 'doorbell', 'external_power', 'wired_power', 'hardwired', 'transformer'):
        return 3
    elif 'no battery' in s or 'usb powered' in s or 'usb' in s:
        return 10
    elif s in ('unknown', 'none', ''):
        return 99
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

def get_dynamic_profile_nodedefs():
    """
    Return the dynamic JSON nodedefs structure.
    Used for updateJsonProfile and as a fallback when no profile/ directory exists.
    """
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

_profile_driver_names = None

def get_profile_driver_names():
    """
    Extract the mapping of (nodeDefId, driver_id) -> display name.
    1. First tries profile/nodedef/nodedefs.xml and profile/nls/en_us.txt (static profile).
    2. If no static profile directory exists, falls back to dynamic JSON profile definitions.
    Cached after the first load.
    """
    global _profile_driver_names
    if _profile_driver_names is not None:
        return _profile_driver_names

    _profile_driver_names = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    xml_path = os.path.join(base_dir, 'profile', 'nodedef', 'nodedefs.xml')
    nls_path = os.path.join(base_dir, 'profile', 'nls', 'en_us.txt')

    # 1. Try static profile files if they exist
    if os.path.exists(xml_path) and os.path.exists(nls_path):
        try:
            st_labels = {}
            with open(nls_path, 'r', encoding='utf-8') as f:
                for line in f:
                    m = re.match(r'^ST-([\w\-]+)-([\w\-]+)-NAME\s*=\s*(.+)', line.strip())
                    if m:
                        nls, driver, label = m.groups()
                        st_labels[(nls, driver)] = label.strip()

            tree = ET.parse(xml_path)
            root = tree.getroot()
            for node_def in root.findall('.//nodeDef'):
                node_id = node_def.get('id')
                nls = node_def.get('nls')
                if not node_id or not nls:
                    continue
                for st in node_def.findall('.//st'):
                    driver_id = st.get('id')
                    if driver_id and (nls, driver_id) in st_labels:
                        _profile_driver_names[(node_id, driver_id)] = st_labels[(nls, driver_id)]
        except Exception as e:
            logging.warning(f'Could not load driver names from static profile: {e}')

    # 2. If static files did not yield names (e.g. pure dynamic profile mode), extract from dynamic nodedefs
    if not _profile_driver_names:
        for nd in get_dynamic_profile_nodedefs():
            node_id = nd.get('id')
            for prop in nd.get('properties', []):
                driver_id = prop.get('id')
                name = prop.get('name')
                if node_id and driver_id and name:
                    _profile_driver_names[(node_id, driver_id)] = name

    return _profile_driver_names

def apply_profile_driver_names(node, node_id=None):
    """
    Populate or update 'name' in each driver dictionary of a node instance
    using definitions extracted from static or dynamic profiles.
    """
    target_id = node_id or getattr(node, 'id', None)
    if not target_id or not hasattr(node, 'drivers') or not node.drivers:
        return
    names = get_profile_driver_names()
    for d in node.drivers:
        driver_id = d.get('driver')
        if driver_id and (target_id, driver_id) in names:
            d['name'] = names[(target_id, driver_id)]

