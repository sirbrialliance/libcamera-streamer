
# What

A tool for viwing a Pi camera (libcamera) stream and grabbing snapshot images over HTTP.

Mostly adapted from a [certain example](https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server.py).

# Why

Usually we use [mjpg-streamer](https://github.com/jacksonliam/mjpg-streamer) for webcam viewing with [OctoPrint](https://github.com/OctoPrint/OctoPrint). Unfortunately, the method it uses to access Pi cameras doens't work with ARM 64-bit Raspian bullseye. (Or probably any 64-bit OS, for that matter.) It uses MMAL for interacting with the camera which [doens't have 64-bit support](https://github.com/raspberrypi/userland/issues/688).

And by default, OctoPrint uses mjpg-streamer for the webcam view.

# Setup

(Assuming an OctoPi distribution.)

If you ran `raspi-confg` and turned on `Interface Options -> Legacy Camera support` that's bad. Turn it off and reboot.

Copy streamer.py to somewhere on the Pi.

	apt install libcamera0 libcamera-dev libcamera-apps python3-libcamera python3-picamera2
	# Tweak the settings at the start of streamer.py as needed and make sure it runs standalone.
	cd /root/bin
	service webcamd stop
	mv webcamd webcamd.old
	ln -s /path/to/streamer.py webcamd
	service webcamd start

In OctoPrint -> Settings -> Webcam & Timelapse:

- Set `Stream URL` to http://pi_host_or_ip:8070/stream.mjpg
- Set `Snapshot URL` to http://pi_host_or_ip:8070/snapshot.jpg (this is a higher resolution image, makes for better time lapses)
