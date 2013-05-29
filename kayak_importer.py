#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Parse AIMS Kayak (GoPro) files to produce valid Catami project
v1.0

expects file structure as

Root Dir
  |--Campaign.txt
  |--Image Dir 01
  |       |--images01.jpg
  |       |--images02.jpg
  |       |-- ...
  |--Image Dir 02
  |       |--images01.jpg
  |       |--images02.jpg
  |       |-- ...
  ...
Most data is taken from the XLSX file (inspected JPG files have lat/longs in EXIF, XLSX lat/longs are considered authoratative)
Camera details are taken from image EXIF data
Data without source are set to fill (-999 for numerical data, 'null' for string data)

v1.0 28/05/2013 markg@ivec.org
"""
import os
import os.path
import imghdr

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

images_filename = 'images.csv'
description_filename = 'description.txt'
campaign_filename = 'campaign.txt'

#version 1.0 format described at https://github.com/catami/catami/wiki/Data-importing
current_format_version = '1.0'
fill_value = -999.


#add boolean test for useful image class
def is_image(image_path):
    if imghdr.what(image_path) == 'jpeg' or imghdr.what(image_path) == 'png':
        return True
    else:
        return False


def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for gps_tag in value:
                    sub_decoded = GPSTAGS.get(gps_tag, gps_tag)
                    gps_data[sub_decoded] = value[gps_tag]
                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value
    return exif_data


def _convert_to_degress(value):
    """Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
    deg_num, deg_denom = value[0]
    d = float(deg_num) / float(deg_denom)

    min_num, min_denom = value[1]
    m = float(min_num) / float(min_denom)

    sec_num, sec_denom = value[2]
    s = float(sec_num) / float(sec_denom)
    return d + (m / 60.0) + (s / 3600.0)


def get_photo_datetime(image_name):
    """Returns datetime.datetime for the photo collection time"""
    image = Image.open(image_name)
    info = image._getexif()
    photo_datetime = None

    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "DateTimeOriginal":
                photo_datetime = value

    return photo_datetime


def get_lat_lon(image_name):
    """Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
    image = Image.open(image_name)

    exif_data = get_exif_data(image)

    lat = None
    lon = None

    if "GPSInfo" in exif_data:
        gps_info = exif_data["GPSInfo"]

        gps_latitude = gps_info.get("GPSLatitude")
        gps_latitude_ref = gps_info.get('GPSLatitudeRef')
        gps_longitude = gps_info.get('GPSLongitude')
        gps_longitude_ref = gps_info.get('GPSLongitudeRef')
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degress(gps_latitude)
            if gps_latitude_ref != "N":
                lat *= -1

            lon = _convert_to_degress(gps_longitude)
            if gps_longitude_ref != "E":
                lon *= -1

    return lat, lon


def get_camera_makemodel(image_name):
    """Returns a camera make and model from the exif data of an PIL Image item."""
    image = Image.open(image_name)
    info = image._getexif()
    if info:
        make = None
        model = None
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "Model":
                model = value
            if decoded == "Make":
                make = value
        make_model_string = make+model
    else:
        make_model_string = 'null'

    return make_model_string

if __name__ == "__main__":
    """Builds Catami format package for Kayak AIMS data"""

    directories = [o for o in os.listdir('.') if os.path.isdir(o)]
    if not os.path.isfile(campaign_filename):
        with open(campaign_filename, "w") as f:
            string = 'version:'+current_format_version+'\n'
            f.write(string)
            string = 'Name:\n'
            f.write(string)
            string = 'Description:\n'
            f.write(string)
            string = 'Associated Researchers:\n'
            f.write(string)
            string = 'Associated Publications:\n'
            f.write(string)
            string = 'Associated Research Grants:\n'
            f.write(string)
            string = 'Start Date:\n'
            f.write(string)
            string = 'End Date:\n'
            f.write(string)
            string = 'Contact Person:\n'
            f.write(string)

    for directory in directories:
        filelist = [o for o in os.listdir(directory) if os.path.isfile(os.path.join(directory, o))]

        if not os.path.isfile(os.path.join(directory, images_filename)):
            with open(os.path.join(directory, images_filename), "w") as f:
                version_string = 'version:'+current_format_version+'\n'
                f.write(version_string)
                headers = 'Time ,Latitude , Longitude  , Depth  , ImageName , CameraName , CameraAngle , Temperature (celcius) , Salinity (psu) , Pitch (radians) , Roll (radians) , Yaw (radians) , Altitude (metres)\n'
                f.write(headers)

        # make the descriptopm file if it doesn't exist
        if not os.path.isfile(os.path.join(directory, description_filename)):
            with open(os.path.join(directory, description_filename), "w") as f:
                version_string = 'version:'+current_format_version+'\n'
                f.write(version_string)
                deployment_type_string = 'Type: TI\n'
                f.write(deployment_type_string)
                Description_string = 'Description:'+directory+' Kayak Transects\n'
                f.write(Description_string)

        for image in filelist:
            if is_image(os.path.join(directory, image)):
                latitude, longitude = get_lat_lon(os.path.join(directory, image))
                depth = 2.0
                image_datetime = get_photo_datetime(os.path.join(directory, image))
                camera_name = get_camera_makemodel(os.path.join(directory, image))
                camera_angle = 'Downward'
                temperature = fill_value
                salinity = fill_value
                pitch_angle = fill_value
                roll_angle = fill_value
                yaw_angle = fill_value
                altitude = fill_value

                #append to csv
                with open(os.path.join(directory, images_filename), "a") as f:
                    csv_string = unicode(image_datetime)+','+str(latitude)+','+str(longitude)+','+str(depth)+','+image+','+camera_name+','+camera_angle+','+str(temperature)+','+str(salinity)+','+str(pitch_angle)+','+str(roll_angle)+','+str(yaw_angle)+','+str(altitude)+'\n'
                    f.write(csv_string)