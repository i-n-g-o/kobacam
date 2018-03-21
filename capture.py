#!/usr/bin/env python

#
# written by ingo randolf - 2018
# http://ingorandolf.info
#
# for the koba-shop
# http://kobakant.at/KOBA/
#
#

import os
import time
import datetime
import picamera
import BaseHTTPServer
import os.path
import sys

from threading import Thread
from time import sleep

import pwd
import grp

import logging
import PythonMagick


uid = pwd.getpwnam("pi").pw_uid
gid = grp.getgrnam("pi").gr_gid


#############################
## logfile
#############################
logging.basicConfig(filename='capture.log',level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')


#############################
## setup camera
#############################
camera = picamera.PiCamera()

camera.resolution = (2592, 1944)

camera.sharpness = 0
camera.contrast = 0
camera.brightness = 50
camera.saturation = 0
camera.ISO = 0
camera.video_stabilization = False
camera.exposure_compensation = 0
camera.exposure_mode = 'auto'
camera.meter_mode = 'average'
camera.awb_mode = 'auto'
camera.image_effect = 'none'
camera.color_effects = None
camera.rotation = 0
camera.hflip = False
camera.vflip = False
camera.crop = (0.0, 0.0, 1.0, 1.0)


#############################
## setup webserver
#############################
HOST_NAME = ''
PORT_NUMBER_DEFAULT = 8000 # Maybe set this to 9000.

dothread = True
sleep_time = 1 # seconds
capture_interval = 3600 # 60 minutes
stopped_for_today = False;
path_prefix = ""


#############################
## capture automatically
def threaded_capture(arg):
    global stopped_for_today

    while dothread:
        count = 0
        while dothread and count < capture_interval:
            sleep(sleep_time) #60 seconds
            count += 1

        # capture only if not sunday, > 9:00 &  < 24:00
        if dothread and datetime.datetime.now().weekday() != 6 and datetime.datetime.now().hour >= 8 and not stopped_for_today:
            filename = capture_image()
        elif stopped_for_today and datetime.datetime.now().hour < 8:
            stopped_for_today = False;

    print "done with thread"
    logging.info("done with thread")

#############################
## load a file
def load_binary(file):
    with open(file, 'rb') as file:
        return file.read()



#############################
## postProcess image
def postProcess(filename, filenameout):
    logging.info("process image: " + filename)
    image = PythonMagick.Image(filename)
    image.normalize()
    image.transform("50%")

    logging.info("write processed image: " + filenameout)
    image.write(filenameout)



#############################
## capture one image
def capture_image():
    timeprefix = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    filename = '%s_still_orig.jpg' % timeprefix
    filenameout = '%s_still.jpg' % timeprefix

    # logging
    _str = "capture image: ", filename
    print _str
    logging.info(_str)

    absfilename = path_prefix + 'stills/%s' % filename
    absfilenameout = path_prefix + 'stills/%s' % filenameout

    # capture
    camera.capture(absfilename)

    # post-process the image
    postProcess(absfilename, absfilenameout)

    if os.path.isfile(path_prefix+"stills/latest.jpg"):
        os.remove(path_prefix+"stills/latest.jpg")

    # make symlink to last image
    os.symlink(filenameout, path_prefix+"stills/latest.jpg")

    # os.chmod(absfilename, 0666)
    # os.chmod(path_prefix + "stills/latest.jpg", 0666)
    os.chown(absfilename, uid, gid)
    os.chown(absfilenameout, uid, gid)
    os.chown(path_prefix + "stills/latest.jpg", uid, gid)

    return filenameout


#############################
## request handler
class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.end_headers()
    def do_GET(s):

        if s.path == '/capture':
            filename = capture_image()

            # redirect to /
            s.send_response(302) # do not cache redirection
            s.send_header('Location', '/')
            s.end_headers()
            return

        elif s.path == '/stoptimerfortoday':

            logging.info("stoptimerfortoday")
            stopped_for_today = True

            # redirect to /
            s.send_response(302) # do not cache redirection
            s.send_header('Location', '/')
            s.end_headers()
            return

        elif s.path == '/starttimer':

            logging.info("starttimer")
            stopped_for_today = False

            # redirect to /
            s.send_response(302) # do not cache redirection
            s.send_header('Location', '/')
            s.end_headers()
            return

        elif s.path == '/':
            ### else, server last image
            """Respond to a GET request."""
            s.send_response(200)
            # s.send_header("Content-type", "image/jpeg")
            s.send_header("Content-type", "text/html")
            s.end_headers()

            # write latest jpg to client
            #s.wfile.write(load_binary('stills/latest.jpg'))
            s.wfile.write(load_binary(path_prefix+'index.html').replace("$filename$", os.path.basename(os.path.realpath('stills/latest.jpg'))))

        else:
            p = s.path
            if p.startswith("/"):
                p = p[1:]

            p = path_prefix + p

            if os.path.isfile(p):
                # deliver
                if p.endswith(".jpg") or p.endswith(".jpeg"):
                    s.send_response(200)
                    s.send_header("Content-type", "image/jpeg")
                elif p.endswith(".png"):
                    s.send_response(200)
                    s.send_header("Content-type", "image/png")
                else:
                    s.send_response(505)
                    return

                s.end_headers()
                s.wfile.write(load_binary(p))
            else:
                print "requested file does not exist: ", p
                _str = "requested file does not exist: ", p
                logging.info(_str)
                s.send_response(505)

#############################
## main
if __name__ == '__main__':

    path_prefix = os.path.dirname(os.path.realpath(__file__)) + "/"

    # check if folder "stills" exists
    if os.path.isfile("stills"):
        print "error: we need folder 'stills', but file 'stills' exists"
        logging.debug("error: we need folder 'stills', but file 'stills' exists")
        os.exit(-1)


    if not os.path.isdir("stills"):
        print "creating folder stills"
        logging.info("creating folder stills");
        os.makedirs("stills")

    if capture_interval > 0:
        print "starting automatic capture"
        logging.info("starting automatic capture");
        thread = Thread(target = threaded_capture, args = (10, ))
        thread.start()

    server_class = BaseHTTPServer.HTTPServer
    httpd = None
    try :
        PORT_NUMBER = 80
        httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
        print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, 80)
        _str = time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, 80)
        logging.info(_str)
    except Exception:
        print "could not bind to port 80"
        logging.debug("could not bind to port 80")
        PORT_NUMBER = PORT_NUMBER_DEFAULT
        httpd = server_class((HOST_NAME, PORT_NUMBER), MyHandler)
        print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER)
        _str = time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER)
        logging.info(_str)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()
    print time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER)
    _str = time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER)
    logging.info(_str)

    if capture_interval > 0:
        dothread = False
        thread.join()

    camera.close()
