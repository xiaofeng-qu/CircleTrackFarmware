#!/usr/bin/python

''' Take a picture, find the circular object, and save to the server.'''
import os
from time import time, sleep
import json
import requests
import numpy as np
import cv2 as cv

# do noting, used for creating the trackbar
def nothing(x):
    pass

# send a message to the log
def log(message, message_type):
    try:
        os.environ['FARMWARE_URL']
    except KeyError:
        print(message)
    else:
        log_message = '[CircleTrackFarmware] ' + str(message)
        headers = {
            'Authorization': 'bearer {}'.format(os.environ['FARMWARE_TOKEN']),
            'content-type': "application/json"}
        payload = json.dumps(
            {"kind": "send_message",
             "args": {"message": log_message, "message_type": message_type}})
        requests.post(farmware_api_url() + 'celery_script',
                      data=payload, headers=headers)

# prepare filename with timestamp
def image_filename():
    epoch = int(time())
    filename = '{timestamp}.jpg'.format(timestamp=epoch)
    return filename

# filename with path for uploading an image
def upload_path(filename):
    try:
        images_dir = os.environ['IMAGES_DIR']
    except KeyError:
        images_dir = '/tmp/images'
    path = images_dir + os.sep + filename
    return path

# rotate image if calibration data exists
def rotate(image):
    angle = float(os.environ['CAMERA_CALIBRATION_total_rotation_angle'])
    sign = -1 if angle < 0 else 1
    turns, remainder = -int(angle / 90.), abs(angle) % 90  # 165 --> -1, 75
    if remainder > 45: turns -= 1 * sign  # 75 --> -1 more turn (-2 turns total)
    angle += 90 * turns                   #        -15 degrees
    image = np.rot90(image, k=turns)
    height, width, _ = image.shape
    matrix = cv.getRotationMatrix2D((int(width / 2), int(height / 2)), angle, 1)
    return cv.warpAffine(image, matrix, (width, height))

# take a photo using the USB camera, and detect the circular object
def usb_camera_photo():
    # Settings
    camera_port = 0      # default USB camera port
    discard_frames = 20  # number of frames to discard for auto-adjust

    # Check for camera
    if not os.path.exists('/dev/video' + str(camera_port)):
        print("No camera detected at video{}.".format(camera_port))
        camera_port += 1
        print("Trying video{}...".format(camera_port))
        if not os.path.exists('/dev/video' + str(camera_port)):
            print("No camera detected at video{}.".format(camera_port))
            log("USB Camera not detected.", "error")

    # Open the camera
    camera = cv.VideoCapture(camera_port)
    sleep(0.1)

    # Let camera adjust
    for _ in range(discard_frames):
        camera.grab()

    # Take a photo
    ret, image = camera.read()

    # Close the camera
    camera.release()

    # Output
    if ret:  # an image has been returned by the camera
        filename = image_filename()
        # Try to rotate the image
        try:
            final_image = rotate(image)
        except:
            final_image = image
        else:
            filename = 'rotated_' + filename
        # detect circular objects and mark the objects
        gray = cv.cvtColor(final_image, cv.COLOR_BGR2GRAY)
        gray = cv.GaussianBlur(gray, (15,15), 2)
        # use HoughCircles detect circles
        circles = cv.HoughCircles(gray, cv.HOUGH_GRADIENT, 1, 20, param1 = 80, param2 = 50, minRadius = 1, maxRadius = 100)
        # if found cirles mark them on the captured image
        if circles is not None:
            for circle in circles[0, :]:
                center = (circle[0], circle[1])
                radius = circle[2]
                # draw the circle
                cv.circle(final_image, center, radius, (255, 0, 255), 3)
                # draw the center
                cv.circle(final_image, center, 2, (0, 255, 255), 3)
                cv.putText(final_image, "(" + str(center[0]) + ", " + str(center[1]) + ")", center, cv.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 200), 2)
        # Save the image to file
        cv.imwrite(upload_path(filename), final_image)
        print("Image saved: {}".format(upload_path(filename)))
    else:  # no image has been returned by the camera
        log("Problem getting image.", "error")

# take a photo using the Raspberry Pi Camera, detect the circular objects, and mark them on the photo
def rpi_camera_photo():
    from subprocess import call
    try:
        image_name = image_filename()
        marked_image_name = "marked_" + image_filename()
        filename_path = upload_path(image_name)
        marked_filename_path = upload_path(marked_image_name)
        retcode = call(
            ["raspistill", "-w", "640", "-h", "480", "-o", filename_path])
        if retcode == 0:
            image = cv.imread(filename_path)
            # detect circular objects and mark the objects
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
            gray = cv.GaussianBlur(gray, (15,15), 2)
            # use HoughCircles detect circles
            circles = cv.HoughCircles(gray, cv.HOUGH_GRADIENT, 1, 20, param1 = 80, param2 = 50, minRadius = 1, maxRadius = 100)
            # if found cirles mark them on the captured image
            if circles is not None:
                for circle in circles[0, :]:
                    center = (circle[0], circle[1])
                    radius = circle[2]
                    # draw the circle
                    cv.circle(image, center, radius, (255, 0, 255), 3)
                    # draw the center
                    cv.circle(image, center, 2, (0, 255, 255), 3)
                    cv.putText(image, "(" + str(center[0]) + ", " + str(center[1]) + ")", center, cv.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 200), 2)
            # Save the image to file
            cv.imwrite(marked_filename_path, image)
            print("Image saved: {}".format(marked_filename_path))
        else:
            log("Problem getting image.", "error")
    except OSError:
        log("Raspberry Pi Camera not detected.", "error")
        
if __name__ == '__main__':
    try:
        CAMERA = os.environ['camera']
    except (KeyError, ValueError):
        CAMERA = 'USB'  # default camera

    if 'RPI' in CAMERA:
        rpi_camera_photo()
    else:
        usb_camera_photo()