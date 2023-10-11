import asyncio
from aiohttp import ClientSession
from blinkpy.blinkpy import Blink
from blinkpy.auth import Auth

async def start():
    userName ='christian@olgaard.com'
    password = 'coe123COE!@#*'
    blink = Blink(session=ClientSession())
    # Can set no_prompt when initializing auth handler
    auth = Auth({"username": userName, "password": password}, no_prompt=True)
    blink.auth = auth
    await blink.start()
    return blink

blink = asyncio.run(start())
blink.refresh()
print(blink)