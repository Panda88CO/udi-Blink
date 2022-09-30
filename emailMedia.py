
import requests
from time import sleep
#from svglib.svglib import svg2rlg
#from reportlab.graphics import renderPM
import base64

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




def sendEmail(mediaFileName, email, captureTime):

    subject = 'Captured Media File'
    body = 'This is an email with captured image from camera'
    sender_email = 'isy_powerwall@outlook.com'
    receiver_email = email
    password = 'isy123ISY!@#'

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject
    #message["Bcc"] = receiver_email  # Recommended for mass emails

    # Add body to email
    message.attach(MIMEText(body, 'plain'))

    filename = mediaFileName  # In same directory as script

    # Open PDF file in binary mode
    with open(filename, 'rb') as attachment:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())

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
              