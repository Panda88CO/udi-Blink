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
import json
import smtplib
import ssl
import datetime
from functools import wraps
import concurrent.futures
from concurrent.futures import Future

# Import the new async blinkpy
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth, BlinkTwoFARequiredError
from blinkpy.helpers.constants import (
    DEFAULT_MOTION_INTERVAL,
    DEFAULT_REFRESH,
)

try:
    from blinkpy.sync_module import BlinkSyncModule
    async def _safe_update_local_storage_manifest(self):
        """Skip local storage manifest updates since udi-Blink does not manage USB video clips."""
        return True
    BlinkSyncModule.update_local_storage_manifest = _safe_update_local_storage_manifest
except Exception as e:
    logging.debug(f"Could not patch BlinkSyncModule.update_local_storage_manifest: {e}")

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def async_to_sync(timeout_or_func=60):
    """Decorator to convert async methods to sync for thread-safe access with configurable timeout"""
    def decorator(func, timeout=60):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self._loop and self._loop.is_running():
                coro = func(self, *args, **kwargs)
                future = None
                try:
                    future = asyncio.run_coroutine_threadsafe(coro, self._loop)
                    return future.result(timeout=timeout)
                except (concurrent.futures.CancelledError, asyncio.CancelledError):
                    logging.info(f"Async method {func.__name__} was cancelled")
                    return None
                except (concurrent.futures.TimeoutError, TimeoutError):
                    if future:
                        try:
                            future.cancel()
                        except Exception:
                            pass
                    logging.warning(f"Async method {func.__name__} timed out after {timeout}s - cancelling task")
                    return None
                except RuntimeError as e:
                    logging.warning(f"Async method {func.__name__} could not execute (loop inactive): {e}")
                    return None
                except Exception as e:
                    err_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                    logging.error(f"Error executing async method {func.__name__}: {err_msg}")
                    return None
            return None
        return wrapper

    if callable(timeout_or_func):
        # Used as @async_to_sync without arguments
        return decorator(timeout_or_func, timeout=60)
    else:
        # Used as @async_to_sync(timeout=90) or @async_to_sync(90)
        return lambda func: decorator(func, timeout=timeout_or_func)

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
        self._token_refresh_callback = None

    def set_token_refresh_callback(self, callback):
        """Set callback to be called when tokens are refreshed"""
        self._token_refresh_callback = callback

    def _handle_token_refresh(self):
        """Called by blinkpy Auth when tokens are refreshed during queries"""
        logging.info("Blink tokens were refreshed by background query")
        if self._token_refresh_callback:
            try:
                auth_data = self.get_auth_data()
                if auth_data:
                    self._token_refresh_callback(auth_data)
            except Exception as e:
                logging.error(f"Error executing token refresh callback: {e}")

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
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)
        self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
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
        for key in [
            "token",
            "refresh_token",
            "hardware_id",
            "client_id",
            "account_id",
            "user_id",
            "region_id",
            "host",
            "expires_in",
            "expiration_date",
        ]:
            if key in login_data and login_data[key] is not None:
                auth_data[key] = login_data[key]

        # Create Auth with data, session, and callback
        self._blink.auth = Auth(
            auth_data,
            no_prompt=no_prompt,
            session=self._session,
            callback=self._handle_token_refresh,
        )
        
        if "device_id" in login_data:
            self._blink.auth.device_id = login_data["device_id"]
        if "hardware_id" in login_data:
            self._blink.auth.hardware_id = login_data["hardware_id"]
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

    @async_to_sync(120)
    async def start(self):
        """Start Blink (login/refresh)"""
        self._key_required = False
        self._last_error = None
        try:
            await self._blink.start()
            self._log_api_return_structure("start")
            return True
        except BlinkTwoFARequiredError:
            logging.info("Two-Factor Authentication required")
            self._key_required = True
            return True
        except (asyncio.CancelledError, concurrent.futures.CancelledError):
            logging.info("Blink start was cancelled")
            self._last_error = "Cancelled"
            return False
        except Exception as e:
            logging.error(f"Start error: {e}")
            self._last_error = e
            return False

    @property
    def last_error(self):
        return getattr(self, '_last_error', None)

    @property
    def is_network_error(self):
        err = getattr(self, '_last_error', None)
        if not err:
            return False
        err_str = str(err).lower()
        err_type = type(err).__name__.lower()
        network_keywords = ['connect', 'timeout', 'dns', 'network', 'unreachable', 'connection reset', 'refused', 'oserror', 'clienterror']
        return any(k in err_str or k in err_type for k in network_keywords)

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

    @async_to_sync(120)
    async def finalize_auth(self):
        logging.debug('finalize_auth')
        if not getattr(self._blink, 'available', False):
            await self._blink.setup_post_verify()
            await asyncio.sleep(1)
        await self._blink.refresh()
        self._log_api_return_structure("finalize_auth")
        return 'ok'

    def stop(self):
        """Stop event loop and session without invalidating Blink server session"""
        logging.info('Stopping Blink system event loop')
        self._stop_event_loop()

    def get_auth_data(self):
        """Retrieve current auth attributes from blink instance (synchronous, thread-safe)"""
        if self._blink and self._blink.auth:
            try:
                attrs = dict(self._blink.auth.login_attributes)
                username = attrs.get("username")
                if not username and self.login_data:
                    username = self.login_data.get("username")
                hardware_id = getattr(self._blink.auth, "hardware_id", None) or attrs.get("hardware_id")
                device_id = getattr(self._blink.auth, "device_id", None) or hardware_id
                return {
                    "username": username,
                    "token": attrs.get("token"),
                    "refresh_token": attrs.get("refresh_token"),
                    "hardware_id": hardware_id,
                    "device_id": device_id,
                    "client_id": attrs.get("client_id"),
                    "account_id": attrs.get("account_id"),
                    "user_id": attrs.get("user_id"),
                    "region_id": attrs.get("region_id"),
                    "host": attrs.get("host"),
                    "expires_in": attrs.get("expires_in"),
                    "expiration_date": attrs.get("expiration_date"),
                }
            except Exception as e:
                logging.error(f"Error getting auth data: {e}")
        return None

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

    def get_device_homescreen_data(self, camera_name):
        """Retrieve raw homescreen dictionary for a camera or doorbell by name or id."""
        if not self._blink or not hasattr(self._blink, 'homescreen') or not isinstance(self._blink.homescreen, dict):
            return {}
        cam = self.cameras.get(camera_name) if hasattr(self, 'cameras') and self.cameras else None
        cam_id = str(getattr(cam, 'camera_id', '')) if cam else ''
        hs = self._blink.homescreen
        for category in ('doorbells', 'cameras', 'owls', 'devices'):
            items = hs.get(category, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        if item.get('name') == camera_name:
                            return item
                        if cam_id and str(item.get('id', '')) == cam_id:
                            return item
        return {}

    def _log_api_return_structure(self, context="API"):
        """Log full return structure from Blink API calls nicely formatted to debug log."""
        try:
            if hasattr(logging, 'isEnabledFor') and not logging.isEnabledFor(10):
                return
            if not self._blink:
                logging.debug("Blink API [%s]: No blink instance available", context)
                return

            logging.debug("=================== BEGIN BLINK API DATA DUMP [%s] ===================", context)

            # 1. Homescreen
            hs = getattr(self._blink, 'homescreen', None)
            if hs and isinstance(hs, dict):
                logging.debug("--- HOMESCREEN SUMMARY --- Keys: %s", list(hs.keys()))
                for section in ('networks', 'doorbells', 'owls', 'cameras', 'sync_modules', 'device_status'):
                    data = hs.get(section)
                    if data:
                        logging.debug("--- HOMESCREEN [%s] (%d items) ---\n%s",
                                      section.upper(), len(data) if isinstance(data, list) else 1,
                                      json.dumps(data, indent=2, default=str))
                other_keys = [k for k in hs.keys() if k not in ('networks', 'doorbells', 'owls', 'cameras', 'sync_modules', 'device_status', 'media')]
                if other_keys:
                    other_data = {k: hs[k] for k in other_keys}
                    logging.debug("--- HOMESCREEN OTHER DATA ---\n%s", json.dumps(other_data, indent=2, default=str))
            else:
                logging.debug("--- HOMESCREEN: %s ---", hs)

            # 2. Networks
            nets = getattr(self._blink, 'networks', None)
            if nets:
                logging.debug("--- BLINK NETWORKS ---\n%s", json.dumps(nets, indent=2, default=str))

            # 3. Sync modules
            if self.sync:
                logging.debug("--- SYNC MODULES (%d) ---", len(self.sync))
                for s_name, s_obj in self.sync.items():
                    s_attrs = getattr(s_obj, 'attributes', {})
                    s_summary = getattr(s_obj, 'summary', {})
                    s_net_info = getattr(s_obj, 'network_info', {})
                    logging.debug("Sync Module '%s':\n  attributes: %s\n  summary: %s\n  network_info: %s",
                                  s_name,
                                  json.dumps(s_attrs, indent=2, default=str),
                                  json.dumps(s_summary, indent=2, default=str),
                                  json.dumps(s_net_info, indent=2, default=str))

            # 4. Cameras
            if self.cameras:
                logging.debug("--- CAMERAS (%d) ---", len(self.cameras))
                for c_name, c_obj in self.cameras.items():
                    c_props = {
                        "name": getattr(c_obj, 'name', None),
                        "camera_id": getattr(c_obj, 'camera_id', None),
                        "network_id": getattr(c_obj, 'network_id', None),
                        "product_type": getattr(c_obj, 'product_type', None),
                        "camera_type": getattr(c_obj, 'camera_type', None),
                        "status": getattr(c_obj, 'status', None),
                        "online": getattr(c_obj, 'online', None),
                        "temperature": getattr(c_obj, 'temperature', None),
                        "temperature_c": getattr(c_obj, 'temperature_c', None),
                        "temperature_calibrated": getattr(c_obj, 'temperature_calibrated', None),
                        "battery": getattr(c_obj, 'battery', None),
                        "battery_state": getattr(c_obj, 'battery_state', None),
                        "battery_level": getattr(c_obj, 'battery_level', None),
                        "battery_voltage": getattr(c_obj, 'battery_voltage', None),
                        "battery_check_time": getattr(c_obj, 'battery_check_time', None),
                        "arm": getattr(c_obj, 'arm', None),
                        "motion_enabled": getattr(c_obj, 'motion_enabled', None),
                        "motion_detected": getattr(c_obj, 'motion_detected', None),
                        "wifi_strength": getattr(c_obj, 'wifi_strength', None),
                        "sync_signal_strength": getattr(c_obj, 'sync_signal_strength', None),
                        "last_record": getattr(c_obj, 'last_record', None),
                    }
                    c_vars = {k: v for k, v in vars(c_obj).items() if k not in ('sync', '_session', '_loop') and not callable(v)}
                    hs_entry = self.get_device_homescreen_data(c_name)
                    logging.debug("Camera '%s':\n  PROPERTIES:\n%s\n  INSTANCE VARS:\n%s\n  HOMESCREEN RAW:\n%s",
                                  c_name,
                                  json.dumps(c_props, indent=2, default=str),
                                  json.dumps(c_vars, indent=2, default=str),
                                  json.dumps(hs_entry, indent=2, default=str))

            logging.debug("=================== END BLINK API DATA DUMP [%s] ===================", context)
        except Exception as e:
            logging.error("Error logging Blink API return structure: %s", e)

    @async_to_sync(120)
    async def refresh(self):
        if self._blink:
            try:
                await self._blink.refresh()
                self._log_api_return_structure("refresh")
                return True
            except (asyncio.CancelledError, concurrent.futures.CancelledError):
                logging.info("Blink refresh was cancelled")
                return False
            except Exception as e:
                logging.error(f"Error during refresh: {e}")
                return False
        return False
    
    def _debug_camera_data(self):
        """Log debug buffer with all camera data after refresh"""
        self._log_api_return_structure("debug_camera_data")
        
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
        # logging.debug(
        #     "get_sync_online raw values for %s: status=%r enabled=%r attributes=%r",
        #     sync_name,
        #     getattr(sync_obj, 'status', None),
        #     getattr(sync_obj, 'enabled', None),
        #     getattr(sync_obj, 'attributes', None),
        # )

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

            # Detect if sync is not a real sync unit (e.g., camera is its own sync)
            is_fake_sync = False
            if sync is not None:
                sync_id = getattr(sync, 'sync_id', None)
                camera_id = getattr(camera, 'camera_id', None)
                if sync is camera or (sync_id is not None and camera_id is not None and str(sync_id) == str(camera_id)):
                    is_fake_sync = True

            sync_network_id = getattr(sync, 'network_id', None) if sync else None
            if sync and not is_fake_sync and str(getattr(sync, 'network_id', '')) == str(network_id):
                camera_list.append(camera)
            elif cam_network_id is not None and str(cam_network_id) == str(network_id):
                # Some camera-only networks still expose a sync object that does not map
                # correctly, so prefer an explicit camera-level network_id match.
                if sync and not is_fake_sync and str(sync_network_id) != str(network_id):
                    # logging.debug(
                    #     'Camera %s sync.network_id (%s) mismatches target network_id (%s); '
                    #     'using camera.network_id instead',
                    #     name, sync_network_id, network_id
                    # )
                    pass
                camera_list.append(camera)
            elif not sync or is_fake_sync or not getattr(sync, 'network_id', None):
                # Camera may be its own sync module or have no sync — check network_id directly on the camera
                if cam_network_id and str(cam_network_id) == str(network_id):
                    # logging.debug('Camera {} has no real sync reference; using camera.network_id directly'.format(name))
                    camera_list.append(camera)
        return camera_list

    def get_sync_modules_on_network(self, network_id):
        sync_list = []
        # logging.debug('Finding sync modules for network_id: {}'.format(network_id))
        # logging.debug('Available sync modules: {} {}'.format(list(self.sync.keys()), list(self.sync.items())))
        # Collect all camera IDs for this network
        camera_ids = set()
        for name, camera in self.cameras.items():
            cam_network_id = getattr(camera, 'network_id', None)
            cam_attrs = getattr(camera, 'attributes', None)
            if isinstance(cam_attrs, dict) and cam_network_id is None:
                cam_network_id = cam_attrs.get('network_id')
            if cam_network_id is not None and str(cam_network_id) == str(network_id):
                camera_id = getattr(camera, 'camera_id', None)
                if camera_id is not None:
                    camera_ids.add(str(camera_id))

        for name, sync in self.sync.items():
            sync_id = getattr(sync, 'sync_id', None)
            if str(getattr(sync, 'network_id', '')) == str(network_id):
                # Skip fake sync units (where sync_id matches a camera_id)
                if sync_id is not None and str(sync_id) in camera_ids:
                    # logging.debug('Skipping fake sync unit %s (sync_id %s matches a camera_id) for network %s', name, sync_id, network_id)
                    continue
                sync_list.append(sync)
        return sync_list

    def get_network_arm_state(self, network_id):
        matched_camera_backed_sync = False
        only_camera_backed_sync = True
        found_sync = False

        # Try to find sync module for this network and return its arm state
        for name, sync_module in self.sync.items():
            if str(getattr(sync_module, 'network_id', '')) == str(network_id):
                found_sync = True
                if self._is_camera_backed_sync(sync_module, network_id):
                    matched_camera_backed_sync = True
                    # logging.debug(
                    #     'get_network_arm_state: sync %s on network %s is camera-backed; '
                    #     'will check if all syncs are camera-backed',
                    #     getattr(sync_module, 'name', name), network_id
                    # )
                else:
                    only_camera_backed_sync = False
                    value = self._normalize_arm_value(getattr(sync_module, 'arm', None))
                    if value is not None:
                        # logging.debug('get_network_arm_state: found sync module arm value %r for network %s', value, network_id)
                        return value

        # If all syncs for this network are camera-backed, treat as camera-only and return 2
        if found_sync and matched_camera_backed_sync and only_camera_backed_sync:
            logging.info('get_network_arm_state: All syncs for network %s are camera-backed. Returning 2 (Individually camera assigned).', network_id)
            return 2

        if matched_camera_backed_sync:
            camera_value = self._derive_network_arm_from_cameras(network_id)
            if camera_value is not None:
                # logging.debug('get_network_arm_state: derived camera-backed arm value %r for network %s', camera_value, network_id)
                return camera_value

        # Fallback to homescreen if sync module not found (legacy)
        networks = self.homescreen.get('networks', [])
        for network in networks:
            if str(network.get('id', '')) == str(network_id):
                arm = self._normalize_arm_value(network.get('armed'))
                if arm is not None:
                    # logging.debug('get_network_arm_state: found homescreen arm value %r for network %s', arm, network_id)
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
            # logging.debug(
            #     'get_network_arm_state: deriving arm state from %d cameras on network %s: %s',
            #     len(arm_states), network_id, arm_states
            # )
            return all(arm_states)

        # logging.debug(
        #     'get_network_arm_state: no usable arm values found for %d cameras on network %s',
        #     len(cameras_on_network), network_id
        # )
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
                    # logging.debug(
                    #     'set_network_arm_state: sync %s on network %s is camera-backed; '
                    #     'arming cameras directly',
                    #     getattr(sync_module, 'name', name), network_id
                    # )
                    break
                await sync_module.async_arm(arm)
                await self._blink.refresh()
                return True

        # No sync unit: set motion detection on all cameras, but do not change arm state
        cameras_on_network = self.get_cameras_on_network(network_id)
        if cameras_on_network:
            # logging.debug(
            #     'set_network_arm_state: no sync unit, setting motion detection for %d cameras in network %s to %s',
            #     len(cameras_on_network), network_id, arm
            # )
            success_count = 0
            import asyncio
            for camera in cameras_on_network:
                try:
                    # Only set motion detection, not arm state
                    if hasattr(camera, 'async_set_motion_detect'):
                        await camera.async_set_motion_detect(arm)
                    else:
                        # Fallback: use async_arm if that's the only way
                        await camera.async_arm(arm)
                    success_count += 1
                    await asyncio.sleep(0.5)  # Throttle requests to avoid API/camera overload
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
            val = getattr(camera, 'battery', None)
            if val is None or str(val).lower() in ('none', 'unknown', ''):
                val = getattr(camera, 'battery_state', None)
            if val is None or str(val).lower() in ('none', 'unknown', ''):
                val = getattr(camera, 'battery_level', None)
            if val is None or str(val).lower() in ('none', 'unknown', ''):
                attrs = getattr(camera, 'attributes', {})
                if isinstance(attrs, dict):
                    val = attrs.get('battery') or attrs.get('battery_state') or attrs.get('battery_level')

            # Check homescreen device data (especially for doorbells and powered cameras)
            hs_data = self.get_device_homescreen_data(camera_name)
            if hs_data and isinstance(hs_data, dict):
                # Check for explicit power status fields (wired/external power)
                for pkey in ('power', 'power_source', 'ac_power', 'wired', 'wired_power', 'external_power', 'line_power', 'chime_power'):
                    pval = hs_data.get(pkey)
                    if pval is True or (isinstance(pval, (int, float)) and pval > 0) or (isinstance(pval, str) and pval.lower() in ('wired', 'external', 'ac', 'line', 'true', '1')):
                        logging.debug("get_camera_battery_info: '%s' detected wired/external power via hs_data['%s']=%s", camera_name, pkey, pval)
                        return 'wired'
                
                # If still no battery info, check hs_data for battery fields
                if val is None or str(val).lower() in ('none', 'unknown', ''):
                    for bkey in ('battery_state', 'battery', 'battery_level'):
                        if hs_data.get(bkey) is not None:
                            val = hs_data[bkey]
                            break

            logging.debug("get_camera_battery_info: '%s' resolved to: %s", camera_name, val)
            return val if val is not None else 'No Battery'
        return None

    def get_camera_battery_voltage_info(self, camera_name):
        if camera_name in self.cameras:
            val = getattr(self.cameras[camera_name], 'battery_voltage', None)
            if val is None:
                attrs = getattr(self.cameras[camera_name], 'attributes', {})
                if isinstance(attrs, dict):
                    val = attrs.get('battery_voltage')
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
        # logging.debug('get_camera_type_info: {} {}'.format(camera_name, temp))
        if temp in ['owl']: return 'mini'
        elif temp in ['catalina']: return 'gen2'
        elif temp in ['lotus', 'galapagos', 'tulip', 'freesia']: return 'doorbell'
        elif temp in ['xt2']: return 'XT-2'
        elif temp in ['clownfish']: return 'gen3'
        elif temp in ['sedona']: return 'outdoor4'                
        elif temp in ['hawk']: return 'mini2'
        elif temp in ['pigeon', 'superior']: return 'wiredFloodLight'   
        elif temp in ['trogon']: return 'floodlight'    
        elif temp in ['chickadee']: return 'mini2K+'   
        elif temp in ['sonoran']: return 'outdoor2K+'   
        else:
            ct = getattr(self.cameras[camera_name], 'camera_type', '')
            if ct in ['mini', 'doorbell']:
                return ct
            hs_data = self.get_device_homescreen_data(camera_name)
            if hs_data:
                dtype = str(hs_data.get('type', '')).lower()
                if dtype in ['doorbell', 'lotus', 'galapagos']: return 'doorbell'
                elif dtype in ['owl', 'mini']: return 'mini'
            return 'default'

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
            # logging.debug('get_camera_motion_detected_info: {} {}'.format(camera_name, getattr(self.cameras[camera_name], 'motion_detected', None)))    
            return getattr(self.cameras[camera_name], 'motion_detected', None)
        return None

    def camera_supports_temperature(self, camera_name):
        if camera_name not in self.cameras:
            return False
        cam = self.cameras[camera_name]

        # 1. If an actual temperature reading is available, it definitely supports temperature
        temp_c = self.get_camera_temperatureC_info(camera_name)
        if temp_c is not None:
            logging.debug("camera_supports_temperature: '%s' reports temperature %s C -> True", camera_name, temp_c)
            return True

        # 2. Known models without temperature sensor
        product_type = str(getattr(cam, 'product_type', '')).lower()
        if product_type in ['owl', 'hawk', 'pigeon', 'superior', 'chickadee', 'lotus', 'galapagos', 'tulip', 'freesia']:
            logging.debug("camera_supports_temperature: '%s' (product_type='%s') does not support temperature -> False", camera_name, product_type)
            return False

        cam_type = str(self.get_camera_type_info(camera_name)).lower()
        if cam_type in ['mini', 'mini2', 'mini2k+', 'wiredfloodlight', 'doorbell']:
            logging.debug("camera_supports_temperature: '%s' (cam_type='%s') does not support temperature -> False", camera_name, cam_type)
            return False

        # 3. Known battery cameras with built-in temperature sensor
        if cam_type in ['gen2', 'xt-2', 'gen3', 'outdoor4', 'outdoor2k+', 'floodlight', 'blink outdoor']:
            logging.debug("camera_supports_temperature: '%s' is known temp-capable cam_type '%s' -> True", camera_name, cam_type)
            return True
        if product_type in ['catalina', 'xt2', 'clownfish', 'sedona', 'sonoran', 'trogon']:
            logging.debug("camera_supports_temperature: '%s' is known temp-capable product_type '%s' -> True", camera_name, product_type)
            return True

        # 4. Check camera attributes/signals for temperature keys
        for attr in ('temperature', 'temperature_c', 'temperature_calibrated'):
            if getattr(cam, attr, None) is not None:
                logging.debug("camera_supports_temperature: '%s' has attribute '%s' -> True", camera_name, attr)
                return True

        attrs = getattr(cam, 'attributes', None)
        if isinstance(attrs, dict):
            for k in ('temperature', 'temperature_c', 'temperature_calibrated'):
                if attrs.get(k) is not None:
                    logging.debug("camera_supports_temperature: '%s' has attrs['%s'] -> True", camera_name, k)
                    return True

        signals = getattr(cam, 'signals', None)
        if isinstance(signals, dict) and signals.get('temp') is not None:
            logging.debug("camera_supports_temperature: '%s' has signals['temp'] -> True", camera_name)
            return True

        hs_data = self.get_device_homescreen_data(camera_name)
        if isinstance(hs_data, dict):
            for k in ('temperature', 'temp'):
                if hs_data.get(k) is not None:
                    logging.debug("camera_supports_temperature: '%s' has hs_data['%s'] -> True", camera_name, k)
                    return True

        logging.debug("camera_supports_temperature: '%s' does not report or support temperature -> False", camera_name)
        return False

    def get_camera_temperatureC_info(self, camera_name):
        if camera_name not in self.cameras:
            return None
        cam = self.cameras[camera_name]
        # 1. Direct temperature_c property
        temp_c = getattr(cam, 'temperature_c', None)
        if temp_c is not None:
            return temp_c
        # 2. temperature_calibrated (Fahrenheit from sensors endpoint)
        temp_cal = getattr(cam, 'temperature_calibrated', None)
        if temp_cal is not None:
            try:
                return round((float(temp_cal) - 32.0) * 5.0 / 9.0, 1)
            except (ValueError, TypeError):
                pass
        # 3. temperature property (Fahrenheit in blinkpy)
        temp = getattr(cam, 'temperature', None)
        if temp is not None:
            try:
                return round((float(temp) - 32.0) * 5.0 / 9.0, 1)
            except (ValueError, TypeError):
                pass
        # 4. Check attributes dictionary
        attrs = getattr(cam, 'attributes', None)
        if isinstance(attrs, dict):
            if attrs.get('temperature_c') is not None:
                return attrs['temperature_c']
            if attrs.get('temperature_calibrated') is not None:
                try:
                    return round((float(attrs['temperature_calibrated']) - 32.0) * 5.0 / 9.0, 1)
                except (ValueError, TypeError):
                    pass
            if attrs.get('temperature') is not None:
                try:
                    return round((float(attrs['temperature']) - 32.0) * 5.0 / 9.0, 1)
                except (ValueError, TypeError):
                    pass
        # 5. Check signals dictionary
        signals = getattr(cam, 'signals', None)
        if isinstance(signals, dict) and signals.get('temp') is not None:
            try:
                return round((float(signals['temp']) - 32.0) * 5.0 / 9.0, 1)
            except (ValueError, TypeError):
                pass
        # 6. Check homescreen data
        hs_data = self.get_device_homescreen_data(camera_name)
        if isinstance(hs_data, dict):
            for k in ('temperature', 'temp'):
                if hs_data.get(k) is not None:
                    try:
                        return round((float(hs_data[k]) - 32.0) * 5.0 / 9.0, 1)
                    except (ValueError, TypeError):
                        pass
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







