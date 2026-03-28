#!/usr/bin/env python3
try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    import sys
    logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[
        logging.FileHandler("debug1.log"),
        logging.StreamHandler(sys.stdout) ]
    )

import asyncio
import threading
import time
import re
import os
import smtplib
import ssl
import datetime
from functools import wraps
from concurrent.futures import Future

# Import the new async blinkpy
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth, BlinkTwoFARequiredError
from blinkpy.helpers.constants import (
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_REFRESH,
)

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def async_to_sync(func):
    """Decorator to convert async methods to sync for thread-safe access"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._loop and self._loop.is_running():
            coro = func(self, *args, **kwargs)
            try:
                future = asyncio.run_coroutine_threadsafe(coro, self._loop)
                return future.result(timeout=30)
            except Exception as e:
                logging.error(f"Error executing async method {func.__name__}: {e}")
                return None
        return None
    return wrapper

class blink_system:
    def __init__(self,
        login_data=None,
        no_prompt=True,
        refresh_rate=DEFAULT_REFRESH,
        motion_interval=DEFAULT_MOTION_INTERVAL,
        no_owls=False,
        event_loop=None
    ):
        logging.info('Initializing Blink system wrapper')
        self.login_data = login_data
        self.temp_unit = 'C'
        self.email_en = False
        
        # Asyncio components
        self._loop = event_loop
        self._thread = None
        self._blink = None
        self._refresh_rate = refresh_rate
        self._motion_interval = motion_interval
        self._no_owls = no_owls
        
        # Email config
        self.smtp = None
        self.smtp_port = 587
        self.email_sender = None
        self.email_password = None
        self.email_recepient = None
        self._key_required = False

    def _start_event_loop(self):
        """Start the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        
        # Cleanup
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.close()

    def _ensure_event_loop(self):
        """Ensure the event loop is running"""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._start_event_loop, daemon=True, name="BlinkAsyncLoop")
            self._thread.start()
            time.sleep(0.5) # Wait for loop to start

    def _stop_event_loop(self):
        """Stop the event loop and cleanup"""
        if self._loop and self._loop.is_running():
            async def cleanup():
                if hasattr(self, '_session') and self._session:
                    if not self._session.closed:
                        logging.info("Closing aiohttp session")
                        await self._session.close()
                        # Wait for closure
                        while not self._session.closed:
                            await asyncio.sleep(0.1)
            
            future = asyncio.run_coroutine_threadsafe(cleanup(), self._loop)
            try:
                future.result(timeout=5)
            except Exception as e:
                logging.error(f"Cleanup error: {e}")

            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)

    @async_to_sync
    async def _create_blink_instance(self):
        """Create Blink instance and session in the event loop"""
        import aiohttp
        connector = aiohttp.TCPConnector(force_close=True)
        self._session = aiohttp.ClientSession(connector=connector)
        self._blink = Blink(
            session=self._session,
            refresh_rate=self._refresh_rate,
            motion_interval=self._motion_interval,
            no_owls=self._no_owls
        )
        # Auth will be set up in _setup_auth
        return True

    @async_to_sync
    async def _setup_auth(self, login_data, no_prompt):
        if not self._blink: return False
        
        auth_data = {
            "username": login_data.get("username"),
            "password": login_data.get("password"),
        }
        
        # Create Auth with data and session
        self._blink.auth = Auth(auth_data, no_prompt=no_prompt, session=self._session)
        
        if "device_id" in login_data:
            self._blink.auth.device_id = login_data["device_id"]
        if "unique_id" in login_data:
            self._blink.auth.unique_id = login_data["unique_id"]
        return True

    def start_blink(self, login_data, no_prompt):
        """Initialize Blink system"""
        logging.info('Starting Blink system (Async Wrapper)')
        self.login_data = login_data
        self._ensure_event_loop()
        
        # Create instance
        self._create_blink_instance()
        
        # Setup auth
        if login_data:
            self._setup_auth(login_data, no_prompt)

    @async_to_sync
    async def start(self):
        """Start Blink (login/refresh)"""
        self._key_required = False
        try:
            await self._blink.start()
            return True
        except BlinkTwoFARequiredError:
            logging.info("Two-Factor Authentication required")
            self._key_required = True
            return True
        except Exception as e:
            logging.error(f"Start error: {e}")
            return False

    @property
    def auth(self):
        return self._blink.auth if self._blink else None

    @property
    def key_required(self):
        return self._key_required
        
    @property
    def cameras(self):
        return self._blink.cameras if self._blink else {}

    @property
    def sync(self):
        return self._blink.sync if self._blink else {}
        
    @property
    def networks(self):
        return self._blink.networks if self._blink else []
        
    @property
    def homescreen(self):
        return self._blink.homescreen if self._blink else {}

    @async_to_sync
    async def auth_key(self, authenKey=None):
        logging.info(f'Submitting auth key {authenKey}')
        if not authenKey:
            return f'AuthKey Empty: {authenKey}'
        
        result = await self._blink.send_2fa_code(authenKey)
        logging.debug(f'Auth key result: {result}')
        return result

    @async_to_sync
    async def finalize_auth(self):
        logging.debug('finalize_auth')
        await self._blink.setup_post_verify()
        await asyncio.sleep(2)
        await self._blink.refresh()
        return 'ok'

    @async_to_sync
    async def logout(self):
        logging.info('logout')
        try:
            if self._blink and self._blink.auth:
                await self._blink.auth.logout(self._blink)
        finally:
            self._stop_event_loop()

    def set_temp_unit(self, temp_unit):
        self.temp_unit = temp_unit

    def get_temp_unit(self):
        return self.temp_unit

    @async_to_sync
    async def refresh(self):
        if self._blink:
            await self._blink.refresh()
            self._debug_camera_data()
            return True
        return False
    
    def _debug_camera_data(self):
        """Log debug buffer with all camera data after refresh"""
        if not self._blink or not self.cameras:
            logging.debug('No cameras available after refresh')
            return
        
        debug_buffer = ['=== Camera Data After Refresh ===']
        for camera_name, camera in self.cameras.items():
            camera_id = getattr(camera, 'camera_id', 'N/A')
            sync = getattr(camera, 'sync', None)
            sync_id = getattr(sync, 'sync_id', None) if sync else getattr(camera, 'network_id', 'N/A')
            is_own_sync = sync and str(getattr(sync, 'sync_id', '')) == str(camera_id)
            debug_buffer.append(f'Camera: {camera_name}')
            debug_buffer.append(f'  ID: {camera_id}')
            #debug_buffer.append(f'  Name: {getattr(camera, "name", "N/A")}')
            debug_buffer.append(f'  Type: {getattr(camera, "product_type", "N/A")}')
            #debug_buffer.append(f'  Enabled: {getattr(camera, "enabled", "N/A")}')
            debug_buffer.append(f'  Armed: {getattr(camera, "arm", "N/A")}')
            debug_buffer.append(f'  Online: {getattr(camera, "online", "N/A")}')
            #debug_buffer.append(f'  Battery: {getattr(camera, "battery_level", getattr(camera, "battery", "N/A"))}')
            #debug_buffer.append(f'  Battery Voltage: {getattr(camera, "battery_voltage", "N/A")}')
            #debug_buffer.append(f'  Status: {getattr(camera, "status", "N/A")}')
            #debug_buffer.append(f'  Thumbnail: {getattr(camera, "thumbnail", "N/A")}')
            debug_buffer.append(f'  Sync ID: {sync_id} {"(camera is its own sync module)" if is_own_sync else ""}')
            debug_buffer.append(f'  Network ID (via sync): {getattr(sync, "network_id", "N/A") if sync else getattr(camera, "network_id", "N/A")}')
        
        logging.debug('\n'.join(debug_buffer))
        
    def refresh_sys(self):
        return self.refresh()

    def get_network_list(self):
        # In new blinkpy, networks is a list of dicts or objects?
        # Old code returned self.homescreen['networks']
        return self.homescreen.get('networks', [])

    def get_sync_unit(self, sync_unit_name):
        for sync_name, sync_obj in self.sync.items():
            tmp = re.sub(r"[^A-Za-z0-9_,]", "", sync_name)
            if tmp.upper() == sync_unit_name:
                 return sync_obj
        return False

    def get_camera_list(self):
        if not self._blink: return []
        return list(self.cameras.keys())

    def get_sync_camera_list(self, sync_unit):
        if not sync_unit: return []
        # sync_unit.cameras is a dict of cameras in blinkpy
        cameras = getattr(sync_unit, 'cameras', {})
        return list(cameras)

    def get_sync_arm_info(self, sync_name):
        if sync_name in self.sync:
            return getattr(self.sync[sync_name], 'arm', None)
        return None

    @async_to_sync
    async def set_sync_arm(self, sync_name, armed=True):
        if sync_name in self.sync:
            await self.sync[sync_name].async_arm(armed)
            return True
        return False

    def get_sync_online(self, sync_name):
        if sync_name not in self.sync:
            return None

        sync_obj = self.sync[sync_name]
        logging.debug(
            "get_sync_online raw values for %s: status=%r enabled=%r attributes=%r",
            sync_name,
            getattr(sync_obj, 'status', None),
            getattr(sync_obj, 'enabled', None),
            getattr(sync_obj, 'attributes', None),
        )

        # Prefer raw status fields and avoid sync.online, which can emit
        # "Unknown sync module status" with some blinkpy payloads.
        for attr in ('status', 'enabled'):
            value = self._normalize_online_value(getattr(sync_obj, attr, None))
            if value is not None:
                return value

        attrs = getattr(sync_obj, 'attributes', None)
        if isinstance(attrs, dict):
            for key in ('status', 'online', 'enabled'):
                value = self._normalize_online_value(attrs.get(key))
                if value is not None:
                    return value

        return None

    def get_cameras_on_network(self, network_id):
        camera_list = []
        for name, camera in self.cameras.items():
            sync = getattr(camera, 'sync', None)
            cam_network_id = getattr(camera, 'network_id', None)
            cam_attrs = getattr(camera, 'attributes', None)
            if isinstance(cam_attrs, dict) and cam_network_id is None:
                cam_network_id = cam_attrs.get('network_id')

            sync_network_id = getattr(sync, 'network_id', None) if sync else None
            if sync and str(getattr(sync, 'network_id', '')) == str(network_id):
                camera_list.append(camera)
            elif cam_network_id is not None and str(cam_network_id) == str(network_id):
                # Some camera-only networks still expose a sync object that does not map
                # correctly, so prefer an explicit camera-level network_id match.
                if sync and str(sync_network_id) != str(network_id):
                    logging.debug(
                        'Camera %s sync.network_id (%s) mismatches target network_id (%s); '
                        'using camera.network_id instead',
                        name, sync_network_id, network_id
                    )
                camera_list.append(camera)
            elif not sync or not getattr(sync, 'network_id', None):
                # Camera may be its own sync module — check network_id directly on the camera
                if cam_network_id and str(cam_network_id) == str(network_id):
                    logging.debug('Camera {} has no sync reference; using camera.network_id directly'.format(name))
                    camera_list.append(camera)
        return camera_list

    def get_sync_modules_on_network(self, network_id):
        sync_list = []
        logging.debug('Finding sync modules for network_id: {}'.format(network_id))
        logging.debug('Available sync modules: {} {}'.format(list(self.sync.keys()), list(self.sync.items())))
        for name, sync in self.sync.items():
            if str(getattr(sync, 'network_id', '')) == str(network_id):
                sync_list.append(sync)
        return sync_list

    def get_network_arm_state(self, network_id):
        matched_camera_backed_sync = False

        # Try to find sync module for this network and return its arm state
        for name, sync_module in self.sync.items():
            if str(getattr(sync_module, 'network_id', '')) == str(network_id):
                if self._is_camera_backed_sync(sync_module, network_id):
                    matched_camera_backed_sync = True
                    logging.debug(
                        'get_network_arm_state: sync %s on network %s is camera-backed; '
                        'using camera-derived arm state',
                        getattr(sync_module, 'name', name), network_id
                    )
                    break

                value = self._normalize_arm_value(getattr(sync_module, 'arm', None))
                if value is not None:
                    logging.debug('get_network_arm_state: found sync module arm value %r for network %s', value, network_id)
                    return value

        if matched_camera_backed_sync:
            camera_value = self._derive_network_arm_from_cameras(network_id)
            if camera_value is not None:
                logging.debug('get_network_arm_state: derived camera-backed arm value %r for network %s', camera_value, network_id)
                return camera_value

        # Fallback to homescreen if sync module not found (legacy)
        networks = self.homescreen.get('networks', [])
        for network in networks:
            if str(network.get('id', '')) == str(network_id):
                arm = self._normalize_arm_value(network.get('armed'))
                if arm is not None:
                    logging.debug('get_network_arm_state: found homescreen arm value %r for network %s', arm, network_id)
                    return arm

        # No sync unit: check if there are cameras on this network
        cameras_on_network = self.get_cameras_on_network(network_id)
        if cameras_on_network:
            logging.info('get_network_arm_state: No sync unit found for network %s, but cameras exist. Returning 2 (Individually camera assigned).', network_id)
            return 2
        else:
            logging.info('get_network_arm_state: No sync unit and no cameras found for network %s. Returning None.', network_id)
            return None

    def _derive_network_arm_from_cameras(self, network_id):
        """Derive network arm state using cameras in the network."""
        cameras_on_network = self.get_cameras_on_network(network_id)
        if not cameras_on_network:
            return None

        arm_states = []
        for camera in cameras_on_network:
            # Default to disarmed unless all conditions are met
            is_armed = False
            is_motion_enabled = False
            is_motion_active = True  # Assume true if not present

            # Check direct camera attributes
            attrs = getattr(camera, 'attributes', None)
            if attrs and isinstance(attrs, dict):
                # Check for armed/arm/enabled
                for key in ('armed', 'arm', 'enabled'):
                    val = self._normalize_arm_value(attrs.get(key))
                    if val is not None:
                        is_armed = val
                        break
                # Check for motion_enabled
                motion_val = self._normalize_arm_value(attrs.get('motion_enabled'))
                if motion_val is not None:
                    is_motion_enabled = motion_val
                # Check for motion_active (if present)
                if 'motion_active' in attrs:
                    is_motion_active = self._normalize_arm_value(attrs.get('motion_active'))
            else:
                # Fallback to direct camera properties
                is_armed = self._normalize_arm_value(getattr(camera, 'arm', None))
                if is_armed is None:
                    is_armed = self._normalize_arm_value(getattr(camera, 'enabled', None))
                is_motion_enabled = self._normalize_arm_value(getattr(camera, 'motion_enabled', None))
                if hasattr(camera, 'motion_active'):
                    is_motion_active = self._normalize_arm_value(getattr(camera, 'motion_active', None))

            # Treat as disarmed if motion_enabled is True but not active
            if is_motion_enabled and not is_motion_active:
                is_armed = False

            # Only consider camera armed if both armed and motion_enabled are True and motion_active is True
            camera_fully_armed = bool(is_armed and is_motion_enabled and is_motion_active)
            arm_states.append(camera_fully_armed)

        if arm_states:
            logging.debug(
                'get_network_arm_state: deriving arm state from %d cameras on network %s: %s',
                len(arm_states), network_id, arm_states
            )
            return all(arm_states)

        logging.debug(
            'get_network_arm_state: no usable arm values found for %d cameras on network %s',
            len(cameras_on_network), network_id
        )
        return None

    def _is_camera_backed_sync(self, sync_module, network_id):
        """True if a sync entry represents a camera-backed/standalone network."""
        sync_id = getattr(sync_module, 'sync_id', None)
        if sync_id is None:
            sync_id = getattr(sync_module, 'id', None)
        attrs = getattr(sync_module, 'attributes', None)
        if sync_id is None and isinstance(attrs, dict):
            sync_id = attrs.get('id')

        if sync_id is None:
            return False

        for camera in self.get_cameras_on_network(network_id):
            cam_id = getattr(camera, 'camera_id', None)
            if cam_id is None:
                cam_attrs = getattr(camera, 'attributes', None)
                if isinstance(cam_attrs, dict):
                    cam_id = cam_attrs.get('id')
            if cam_id is not None and str(cam_id) == str(sync_id):
                return True
        return False

    def _normalize_arm_value(self, value):
        """Normalize mixed arm/disarm payloads to bool/None."""
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ('armed', 'arm', 'on', 'true', '1', 'enabled', 'yes'):
                return True
            if normalized in ('disarmed', 'disarm', 'off', 'false', '0', 'disabled', 'no'):
                return False

        return None

    @async_to_sync
    async def set_network_arm_state(self, network_id, arm):

        if not self._blink:
            return False

        # Find the sync module for this network
        for name, sync_module in self.sync.items():
            if str(getattr(sync_module, 'network_id', '')) == str(network_id):
                if self._is_camera_backed_sync(sync_module, network_id):
                    logging.debug(
                        'set_network_arm_state: sync %s on network %s is camera-backed; '
                        'arming cameras directly',
                        getattr(sync_module, 'name', name), network_id
                    )
                    break
                await sync_module.async_arm(arm)
                await self._blink.refresh()
                return True

        # No sync unit: set motion detection on all cameras, but do not change arm state
        cameras_on_network = self.get_cameras_on_network(network_id)
        if cameras_on_network:
            logging.debug(
                'set_network_arm_state: no sync unit, setting motion detection for %d cameras in network %s to %s',
                len(cameras_on_network), network_id, arm
            )
            success_count = 0
            for camera in cameras_on_network:
                try:
                    # Only set motion detection, not arm state
                    if hasattr(camera, 'async_set_motion_detect'):
                        await camera.async_set_motion_detect(arm)
                    else:
                        # Fallback: use async_arm if that's the only way
                        await camera.async_arm(arm)
                    success_count += 1
                except Exception as e:
                    logging.error('set_network_arm_state: failed to set motion detect for camera %s: %s',
                                  getattr(camera, 'name', '?'), e)
            await self._blink.refresh()
            return success_count > 0

        return False

    def get_camera_data(self, camera_name):
        if camera_name in self.cameras:
            return getattr(self.cameras[camera_name], 'attributes', {})
        return {}

    def get_camera_battery_info(self, camera_name):
        if camera_name in self.cameras:
            camera = self.cameras[camera_name]
            val = getattr(camera, 'battery_level', getattr(camera, 'battery', None))
            return val if val is not None else 'No Battery'
        return None

    def get_camera_battery_voltage_info(self, camera_name):
        if camera_name in self.cameras:
            val = getattr(self.cameras[camera_name], 'battery_voltage', None)
            return val if val is not None else 'No Battery'
        return None

    def get_camera_arm_info(self, camera_name):
        if camera_name in self.cameras:
            return getattr(self.cameras[camera_name], 'arm', None)
        return None

    @async_to_sync
    async def set_camera_arm(self, camera_name, armed=True):
        if camera_name in self.cameras:
            # self.cameras[camera_name].arm = armed # Property is read-only
            await self.cameras[camera_name].async_arm(armed)
            return True
        return False

    def get_camera_type_info(self, camera_name):
        if camera_name not in self.cameras: return 'default'
        temp = getattr(self.cameras[camera_name], 'product_type', 'default')
        logging.debug('get_camera_type_info: {} {}'.format(camera_name, temp))
        if temp in ['owl']  : return 'mini'
        elif temp in ['catalina']: return 'gen2'
        elif temp in ['lotus', 'galapagos']: return 'doorbell'
        elif temp in ['xt2']: return 'XT-2'
        elif temp in ['clownfish']: return 'gen3'
        elif temp in ['sedona']: return 'outdoor4'                
        elif temp in ['hawk']: return 'mini2'
        elif temp in ['pigeon']: return 'wiredFloodLight'   
        elif temp in ['trogon']: return 'floodlight'    
        elif temp in ['chickadee']: return 'mini2K+'     
        else: return 'default'

    def get_camera_motion_enabled_info(self, camera_name):
        if camera_name in self.cameras:
            # motion_enabled is removed in 0.24.1, use arm
            return getattr(self.cameras[camera_name], 'arm', None)
        return None

    @async_to_sync
    async def set_camera_motion_detect(self, camera_name, enabled=True):
        if camera_name in self.cameras:
            # async_set_motion_detect is deprecated/removed, use async_arm
            return await self.cameras[camera_name].async_arm(enabled)
        return False

    def get_camera_motion_detected_info(self, camera_name):

        if camera_name in self.cameras:
            # Use getattr to be safe, or check attributes dict
            logging.debug('get_camera_motion_detected_info: {} {}'.format(camera_name, getattr(self.cameras[camera_name], 'motion_detected', None)))    
            return getattr(self.cameras[camera_name], 'motion_detected', None)
        return None

    def get_camera_temperatureC_info(self, camera_name):
        if camera_name in self.cameras:
            return getattr(self.cameras[camera_name], 'temperature_c', 
                   getattr(self.cameras[camera_name], 'temperature', None))
        return None

    def get_camera_recording_info(self, camera_name):
        return 0

    def get_camera_status(self, camera_name):
        if camera_name in self.cameras:
            camera = self.cameras[camera_name]

            # Camera-level data is usually the most reliable source.
            online = self._normalize_online_value(getattr(camera, 'online', None))
            if online is not None:
                return 'online' if online else 'offline'

            status = self._normalize_online_value(getattr(camera, 'status', None))
            if status is not None:
                return 'online' if status else 'offline'

            # Fallback to associated sync module status.
            sync = getattr(camera, 'sync', None)
            if sync:
                sync_name = getattr(sync, 'name', None)
                if sync_name:
                    sync_online = self.get_sync_online(sync_name)
                else:
                    sync_online = self._normalize_online_value(getattr(sync, 'status', None))
                if sync_online is not None:
                    return 'online' if sync_online else 'offline'

            return 'online'  # Default assumption
        return None

    def _normalize_online_value(self, value):
        """Normalize mixed online/offline payloads to bool/None."""
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ('online', 'on', 'true', '1', 'connected', 'ok'):
                return True
            if normalized in ('offline', 'off', 'false', '0', 'disconnected', 'unavailable'):
                return False

        return None

    @async_to_sync
    async def snap_picture(self, camera_name):
        if camera_name not in self.cameras: return False
        camera = self.cameras[camera_name]
        try:
            await camera.snap_picture()
            await asyncio.sleep(1)
            dinfo = datetime.datetime.now()
            photo_string = camera_name + dinfo.strftime("_%m_%d_%Y-%H_%M_%S") + '.jpg'
            
            await self._blink.refresh()
            # Logic to wait for thumbnail update...
            # Simplified for now, can be expanded
            await camera.image_to_file('./'+photo_string)
            if self.email_en:
                self.send_email(photo_string, camera_name)
            if os.path.exists(photo_string):
                os.remove(photo_string)
            return True
        except Exception as e:
            logging.error(f"snap_picture error: {e}")
            return False

    @async_to_sync
    async def snap_video(self, camera_name):
        if camera_name not in self.cameras: return False
        camera = self.cameras[camera_name]
        try:
            await camera.record()
            # Logic to wait for video...
            return True
        except Exception as e:
            logging.error(f"snap_video error: {e}")
            return False

    def get_camera_unit(self, camera_name):
        return self.cameras.get(camera_name)

    def set_email_info(self, email_info):
        self.email_en = email_info['email_en']
        self.smtp = email_info['smtp']
        self.smtp_port = email_info['smtp_port']
        self.email_sender = email_info['email_sender']
        self.email_password = email_info['email_password']
        self.email_recepient = email_info['email_recepient']

    def send_email(self, mediaFileName, camera_name):
        # ...existing email logic...
        try:
            logging.debug('send_email: {} {}'.format(mediaFileName,camera_name ))
            subject = 'Captured Media File from {}'.format(camera_name)
            message = MIMEMultipart()
            message['From'] = self.email_sender
            message['To'] = self.email_recepient
            message['Subject'] = subject
            msg_content = MIMEText('File from camera attached', 'plain', 'utf-8')
            message.attach(msg_content)

            with open('./'+mediaFileName, 'rb') as f:
                if mediaFileName.__contains__('jpg'):
                    mime = MIMEBase('image', 'jpg', filename=mediaFileName)
                else:
                    mime = MIMEBase('video/mp4', 'mp4', filename=mediaFileName)
                mime.add_header('Content-Disposition', 'attachment', filename=mediaFileName)
                mime.add_header('X-Attachment-Id', '0')
                mime.add_header('Content-ID', '<0>')
                mime.set_payload(f.read())
                encoders.encode_base64(mime)
                message.attach(mime)    
                context = ssl.create_default_context()
        
            with smtplib.SMTP(self.smtp , self.smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(self.email_sender, self.email_password )
                smtp.sendmail(self.email_sender, self.email_recepient, message.as_string())
                smtp.quit()
                logging.info('Email sent')

        except Exception as e:
            logging.error('Exception send_email: ' + str(e))







