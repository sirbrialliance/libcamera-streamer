#!/usr/bin/env python3

# This was supposed to originally be based on
# https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server.py
# which is based on https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# But like, having 640x480 snapshots is crappy and there's no support for doing
# switch_mode_and_capture_request while using start_recording so things are getting ugly.

import io
import logging
import socketserver
from http import server
import threading
import time
import simplejpeg

from libcamera import Transform
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, JpegEncoder
from picamera2.outputs import FileOutput

STREAM_SIZE = (640, 480)
PORT = 8070
# libcamera.Transform(rotation: int = 0, hflip: bool = False, vflip: bool = False, transpose: bool = False)
# TRANSFORM = Transform(rotation=180)
TRANSFORM = Transform()

# Note that when we set a lower resolution, the camera it probably cropping the image a ton.
# OFC, docs for that are hidden and I can only seem to find the explanation for Pi modules 1 and
# 2 (picamera) over here https://picamera.readthedocs.io/en/release-1.13/fov.html#camera-modes
# We're targeting v3 and picamera2



# https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf#%5B%7B%22num%22%3A70%2C%22gen%22%3A0%7D%2C%7B%22name%22%3A%22XYZ%22%7D%2C115%2C841.89%2Cnull%5D

def gen_index_page():
    global picam2
    return f"""
<!doctype HTML>
<html>
<head>
    <title>libcamera-streamer</title>
    <style>
        html, body {{ margin: 0; padding: 0; color: white; background: #555; }}
        p {{ margin: 10px; }}
    </style>
</head>
<body>
    <p>
        Native resolution: {str(picam2.sensor_resolution)}<br>
        Native color: {picam2.sensor_format}<br>
        Attached camera:
    </p>
    <img src="stream.mjpg" width="{STREAM_SIZE[0]}" height="{STREAM_SIZE[1]}" />
    <br>
    <br>
    <a href="snapshot.jpg">High-resolution snapshot</a>
</body>
</html>
"""


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def _cache_me_not(self):
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')

    def do_GET(self):


        if self.path == '/':
            page_data = gen_index_page().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(page_data))
            self._cache_me_not()
            self.end_headers()
            self.wfile.write(page_data)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self._cache_me_not()
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            self._stream_jpeg()
        elif self.path == '/snapshot.jpg':
            self._send_snapshot()
        else:
            self.send_error(404)
            self.end_headers()

    def _stream_jpeg(self):
        try:
            while True:
                with jpeg_output.condition:
                    jpeg_output.condition.wait()
                    frame = jpeg_output.frame
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
        except Exception as e:
            logging.warning(
                'Removed streaming client %s: %s',
                self.client_address, str(e)
            )

    def _send_snapshot(self):
        self.send_response(200)

        log.info("will get image")

        with picam2_lock:
            log.info("got lock")

            # pause usual preview stream to grab a full-resolution image
            picam2.stop_encoder()


            # log.info("request image")
            # request = picam2.switch_mode_capture_request_and_stop(camera_config_snapshot)
            # log.info("got image")
            # img_data = request.make_array("main")
            # img_format = request.config["main"]["format"]
            # request.release()

            log.info("request image")
            img_data = picam2.switch_mode_and_capture_array(camera_config_snapshot)
            log.info("got image")

            # picam2.configure(camera_config_stream)
            picam2.start_encoder(jpeg_encoder[0], jpeg_encoder[1])
            log.info("resume record")

        log.info("start encode")
        jpeg_data = simplejpeg.encode_jpeg(
            img_data, quality=80,
            colorspace=JpegEncoder.FORMAT_TABLE[camera_config_snapshot["main"]["format"]],
            colorsubsampling="420",
        )
        log.info("encoded")

        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', len(jpeg_data))
        self._cache_me_not()
        self.end_headers()
        self.wfile.write(jpeg_data)


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


log = logging.getLogger("streamer")
logging.basicConfig(level=logging.DEBUG)
# logging.getLogger("picamera2", logging.INFO)

log.info("Checking camera")

picam2 = Picamera2()
camera_config_stream = picam2.create_video_configuration(main={"size": STREAM_SIZE,})
camera_config_stream["transform"] = TRANSFORM
camera_config_snapshot = picam2.create_still_configuration()
camera_config_snapshot["transform"] = TRANSFORM

picam2.configure(camera_config_stream)
picam2.start()

jpeg_output = StreamingOutput()
jpeg_encoder = (MJPEGEncoder(), FileOutput(jpeg_output)) # 22% CPU on my Pi 4
# jpeg_encoder = (JpegEncoder(), FileOutput(jpeg_output)) # ~46% CPU on my Pi 4
picam2.start_encoder(jpeg_encoder[0], jpeg_encoder[1])

# def pumper_thread():
#     while True:
#         # log.debug("will pump")
#         picam2.process_requests(None)
#         # log.debug("pumped requests")
#         time.sleep(1)
# threading.Thread(target=pumper_thread, daemon=True).start()

picam2_lock = threading.Lock()
log.info("Entering main loop")
try:
    address = ('', PORT)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    with picam2_lock:
        picam2.stop_recording()

