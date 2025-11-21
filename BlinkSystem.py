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
        try:
            await self._blink.start()
            return 'OK'
        except BlinkTwoFARequiredError:
            logging.info("Two-Factor Authentication required")
            #await self._blink.prompt_2fa()
            return '2FA_REQUIRED'
        except Exception as e:
            logging.error(f"Start error: {e}")
            return 'ERROR'

    @property
    def auth(self):
        return self._blink.auth if self._blink else None

    @property
    def key_required(self):
        if self._blink and self._blink.auth:
            return self._blink.auth.check_key_required()
        return False
        
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
        
        result = await self._blink.auth.send_auth_key(self._blink, authenKey)
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

    @async_to_sync
    async def refresh(self):
        if self._blink:
            await self._blink.refresh()
            return True
        return False
        
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
        # sync_unit.cameras is a list of camera names in new blinkpy?
        # Or sync_unit.cameras is a dict?
        # Let's assume it behaves like a list of names or objects
        return list(sync_unit.cameras)

    def get_sync_arm_info(self, sync_name):
        if sync_name in self.sync:
            return self.sync[sync_name].arm
        return None

    @async_to_sync
    async def set_sync_arm(self, sync_name, armed=True):
        if sync_name in self.sync:
            await self.sync[sync_name].async_arm(armed)
            return True
        return False

    def get_sync_online(self, sync_name):
        if sync_name in self.sync:
            return self.sync[sync_name].online
        return None

    def get_cameras_on_network(self, network_id):
        camera_list = []
        for name, camera in self.cameras.items():
            if str(camera.sync.network_id) == str(network_id):
                camera_list.append(camera)
        return camera_list

    def get_sync_modules_on_network(self, network_id):
        sync_list = []
        for name, sync in self.sync.items():
            if str(sync.network_id) == str(network_id):
                sync_list.append(sync)
        return sync_list

    def get_network_arm_state(self, network_id):
        networks = self.homescreen.get('networks', [])
        for network in networks:
            if network['id'] == network_id:
                return network['armed']
        return None

    @async_to_sync
    async def set_network_arm_state(self, network_id, arm):
        if self._blink:
            return await self._blink.set_network_arm(network_id, arm)
        return False

    def get_camera_data(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].attributes
        return {}

    def get_camera_battery_info(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].battery or 'No Battery'
        return None

    def get_camera_battery_voltage_info(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].battery_voltage or 'No Battery'
        return None

    def get_camera_arm_info(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].arm
        return None

    @async_to_sync
    async def set_camera_arm(self, camera_name, armed=True):
        if camera_name in self.cameras:
            self.cameras[camera_name].arm = armed
            await self.cameras[camera_name].async_arm(armed)
            return True
        return False

    def get_camera_type_info(self, camera_name):
        if camera_name not in self.cameras: return 'default'
        temp = self.cameras[camera_name].product_type
        if temp == 'owl': return 'mini'
        elif temp == 'catalina': return 'Blink Outdoor'
        elif temp == 'lotus': return 'doorbell'
        elif temp == 'xt2': return 'XT-2'
        elif temp == 'sedona': return 'sedona'
        else: return 'default'

    def get_camera_motion_enabled_info(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].motion_enabled
        return None

    @async_to_sync
    async def set_camera_motion_detect(self, camera_name, enabled=True):
        if camera_name in self.cameras:
            return await self.cameras[camera_name].async_set_motion_detect(enabled)
        return False

    def get_camera_motion_detected_info(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].motion_detected
        return None

    def get_camera_temperatureC_info(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].temperature_c
        return None

    def get_camera_recording_info(self, camera_name):
        return 0

    def get_camera_status(self, camera_name):
        if camera_name in self.cameras:
            return self.cameras[camera_name].status # or online_status?
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







