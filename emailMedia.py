
#import requests
#from time import sleep
#from svglib.svglib import svg2rlg
#from reportlab.graphics import renderPM
#import base64

import smtplib
import ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
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


# It goes to say this work takes effort so please use my referral to support my work
# https://2captcha.com?from=12244449 
# The link above allows you to create a acount with 2captcha 
'''

SUBJECT = "Email Data"

msg = MIMEMultipart()
msg['Subject'] = SUBJECT 
msg['From'] = self.EMAIL_FROM
msg['To'] = ', '.join(self.EMAIL_TO)

part = MIMEBase('application', "octet-stream")
part.set_payload(open("text.txt", "rb").read())
Encoders.encode_base64(part)
    
part.add_header('Content-Disposition', 'attachment; filename="text.txt"')

msg.attach(part)

server = smtplib.SMTP(self.EMAIL_SERVER)
server.sendmail(self.EMAIL_FROM, self.EMAIL_TO, msg.as_string())

'''



def sendEmail(mediaFileName, camera_name):

    subject = 'Captured Media File from {}'.format(camera_name)
    #body = '{} was captured on {} at {}'.format(mediaFileName, camera_name, captureTime)
    ##sender_email = 'isy_powerwall@outlook.com'
    #receiver_email = 'christian@olgaard.com'
    #password = 'isy123ISY!@#'

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject

    part = MIMEBase('application', "octet-stream")
    part.set_payload(open("text.txt", "rb").read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename='+'./'+mediaFileName)

    message.attach(part)    

    filename = mediaFileName  # In same directory as script

    # Encode file in ASCII characters to send by email    
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        'Content-Disposition',
        f'attachment; filename= {filename}',
    )

    # Add attachment to message and convert message to string
    message.attach(part)
    text = message.as_string()

    # Log in to server using secure context and send email


    context = ssl.create_default_context()
    try:
        with smtplib.SMTP('smtp-mail.outlook.com', 587) as smtp:
            smtp.ehlo()  # Say EHLO to server
            smtp.starttls(context=context)  # Puts the connection in TLS mode.
            smtp.ehlo()
            smtp.login(sender_email, password)
            smtp.sendmail(sender_email, receiver_email, text)
            logging.info('Email sent')
    except Exception as e:
        logging.error('Exception sendEmail: ' + str(e))
              