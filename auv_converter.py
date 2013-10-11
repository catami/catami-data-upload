#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Parse AUV data from U-Syd
Catami Data Spec V1.0
https://github.com/catami/catami/wiki/Data-importing

Based on the original Catami import code
Data without source are set to fill (-999 for numerical data, 'null' for string data)

v1.0 28/05/2013 markg@ivec.org
"""
import os
import os.path
import imghdr
import argparse
import glob
import time

from multiprocessing import Pool, Lock

# date handling
import datetime
from dateutil.tz import tzutc

# for netcdf files
from scipy.io import netcdf

# for trackfiles from the data fabric
import csv

# progress bars
from progressbar import ProgressBar, Percentage, Bar, Timer

from PIL import Image

globallock = Lock()

parser = argparse.ArgumentParser(description='Parse AUV Data to produce a valid Catami project.')
parser.add_argument('--path', nargs=1, help='Path to root AUV data directory')
parser.add_argument('--deployment', action='store_true', default=False, help='Convert the directory as a deployment, to be attached to an existing campaign')
parser.add_argument('--outputpath', nargs=1, help='Path to create for the converted data package')

args = parser.parse_args()
make_deployment = args.deployment
root_import_path = args.path[0]
root_output_path = args.outputpath[0]

print 'Looking in: ', root_import_path

if not os.path.isdir(root_import_path):
    raise Exception('This is not a valid path. Check the path to your AUV data.')

if os.path.isdir(root_output_path):
    raise Exception('The specified output path already exists.')

images_filename = 'images.csv'
description_filename = 'description.txt'
campaign_filename = 'campaign.txt'

#version 1.0 format described at https://github.com/catami/catami/wiki/Data-importing
current_format_version = '1.0'
fill_value = -999.


class LimitTracker:
    """A class to easily track limits of a value/field.

    The field specifies the option key of the object to look up, or if
    field is None (the default) use the value itself. All values are
    converted to floats before comparison.

    minimum and maximum specify starting points.
    """

    def __init__(self, field=None, minimum=float("inf"),
                 maximum=float("-inf")):
        self.maximum = maximum
        self.minimum = minimum
        self.field = field

    def check(self, newobject):
        """Check a new value against the existing limits.
        """
        # check if field exists
        if self.field and self.field in newobject:
            value = float(newobject[self.field])
            # then see if it is a new maximum
            self.maximum = max(self.maximum, value)
            self.minimum = min(self.minimum, value)
        elif not self.field:
            value = float(newobject)
            self.maximum = max(self.maximum, value)
            self.minimum = min(self.minimum, value)


class NetCDFParser:
    """A class to wrap retrieving values from AUV NetCDF files.

    The class requires a string with {date_string} in the place for the
    date string as it is not absolutely defined given the starting point.
    It searches for times within 10 seconds of the initial guess.

    It implements the iterator interface returning dictionaries with salinity,
    temperature and time of measurement.
    """
    secs_in_day = 24.0 * 3600.0
    imos_seconds_offset = 631152000.0
    imos_days_offset = imos_seconds_offset / secs_in_day

    def __init__(self, file_handle):
        self.file_handle = file_handle

        # the netcdf file
        self.reader = netcdf.netcdf_file(self.file_handle, mode='r')

        if not 'TIME' in self.reader.variables:
            # error, something is missing
            print 'WARNING: TIME not in netcdf file variables list.'
            raise KeyError("Key 'TIME' not in netcdf file variables list.")

        if not 'PSAL' in self.reader.variables:
            print 'WARNING: PSAL not in netcdf file variables list.'
            raise KeyError("Key 'PSAL' not in netcdf file variables list.")

        if not 'TEMP' in self.reader.variables:
            print 'WARNING: TEMP not in netcdf file variables list.'
            raise KeyError("Key 'TEMP' not in netcdf file variables list.")

        # the index we are up to...
        self.index = 0
        self.items = len(self.reader.variables['TIME'].data)
        print("Finished opening NetCDF file.")

    def imos_to_unix(self, imos_time):
        """Convert IMOS time to UNIX time.

        IMOS time is days since IMOS epoch which is 1950-01-01.
        """
        return (imos_time - self.imos_days_offset) * self.secs_in_day

    def unix_to_datetime(self, unix_time):
        """Short hand to convert unix to datetime."""
        return datetime.datetime.fromtimestamp(unix_time, tz=tzutc())

    def imos_to_datetime(self, imos_time):
        """Convert IMOS time to python datetime object.

        Utility function that chains the imos to unix and
        unix to datetime functions.
        """
        return datetime.datetime.fromtimestamp(self.imos_to_unix(imos_time),
                                               tz=tzutc())
    def isFinished(self):
        return self.index >= self.items

    def next(self):
        """Get the next row in the NetCDF File.
        """
        i = self.index
        self.index += 1

        time = self.reader.variables['TIME'].data[i]
        sal = self.reader.variables['PSAL'].data[i]
        temp = self.reader.variables['TEMP'].data[i]

        return {'date_time': self.imos_to_datetime(time),
                'salinity': sal,
                'temperature': temp}


class TrackParser:
    """A class to parse the csv stereo pose tracks for AUV deployments.

    It can be given a URI that it will retrieve the file from. It returns
    a dictionary using the header row to determine the keys and the values
    for each row.
    """

    def __init__(self, file_handle):
        """Open a parser for AUV track files.

        -- file_location can be url or local file location.
        """
        self.file_handle = file_handle

        self.reader = csv.reader(self.file_handle)

        # skip until year is the first entry
        for row in self.reader:
            if len(row) >= 1 and row[0] == 'year':
                self.header = row
                break
                # the next line is the first data line
                # so construction is finished

    def next(self):
        """Get next row of track file."""
        # create a dict of the column headers and the values
        return dict(zip(self.header, self.reader.next()))

    def __iter__(self):
        return self


class AUVImporter(object):
    """Group of methods related to importing AUV missions.

    Methods to check for existence of required files etc.
    And a method to actually import the required files."""

    @classmethod
    def dependency_check(cls, deployment_path):
        # try and get files required, if throw exception
        # then return False (don't have required files)
        # else return True (do have what is required to import)
        try:
            files = cls.dependency_get(deployment_path)
        except IOError as e:
            return False
        else:
            return True

    @classmethod
    def dependency_get(cls, deployment_path):
        # find the hydro netcdf file
        netcdf_pattern = os.path.join(deployment_path, 'hydro_netcdf/IMOS_AUV_ST_*Z_SIRIUS_FV00.nc')

        matches = glob.glob(netcdf_pattern)

        if len(matches) < 1:
            raise IOError("Cannot find netcdf file.")
        elif len(matches) > 1:
            raise IOError("Too many potential netcdf files.")

        print("NetCDF File: {0}".format(matches[0]))

        netcdf_filename = matches[0]

        # find the track file
        track_pattern = os.path.join(deployment_path, 'track_files/*_latlong.csv')

        matches = glob.glob(track_pattern)

        if len(matches) < 1:
            print 'WARNING: Cannot file track file.'
            raise IOError("Cannot find track file.")
        elif len(matches) > 1:
            print 'WARNING: Too many potential track files.'
            raise IOError("Too many potential track files.")

        print("Track File: {0}".format(matches[0]))

        track_filename = matches[0]

        # get the image subfolder name
        image_folder_pattern = os.path.join(deployment_path, 'i*_gtif')

        matches = glob.glob(image_folder_pattern)

        if len(matches) < 1:
            raise IOError("Cannot find geotiff folder.")
        elif len(matches) > 1:
            raise IOError("Too many potential geotiff folders.")

        print("Images Folder: {0}".format(matches[0]))

        image_foldername = matches[0]

        files = {}
        files['netcdf'] = netcdf_filename
        files['track'] = track_filename
        files['image'] = image_foldername

        return files

    @classmethod
    def import_path(cls, auvdeployment, deployment_path):
        print "Importing auv path"
        files = cls.dependency_get(deployment_path)
        # do it this way as it was the way it was written...
        auvdeployment_import(auvdeployment, files)


def auvdeployment_import(files):
    """Import an AUV deployment from disk.

    This uses the track file and hydro netcdf files (as per RELEASE_DATA).
    If the deployment comes in the CATAMI deployment format use that importer
    instead.

    Certain parameters of the deployment should be prefilled - namely short_name,
    campaign, license, descriptive_keywords and owner. The rest are obtained from the
    on disk information.

    Information obtained within the function includes start and end time stamps,
    start and end positions, min and max depths and mission aim. Additionally the
    region column, and other AUV specific fields are filled.
    """

    print("MESSAGE: Starting auvdeployment import")
    auvdeployment = {}

    netcdf = NetCDFParser(open(files['netcdf'], "rb"))
    track_parser = TrackParser(open(files['track'], "r"))
    image_subfolder = files['image']

    # now start going through and creating the data
    auvdeployment['mission_aim'] = "Generic Description."
    auvdeployment['min_depth'] = 14000
    auvdeployment['max_depth'] = 0

    auvdeployment['start_time_stamp'] = datetime.datetime.now()
    auvdeployment['end_time_stamp'] = datetime.datetime.now()

    # create the left-colour camera object
    # we don't normally give out the right mono
    # images...
    leftcamera = {}

    leftcamera['name'] = "Left Colour"
    leftcamera['angle'] = "Downward"

    first_image = None
    last_image = None

    lat_lim = LimitTracker('latitude')
    lon_lim = LimitTracker('longitude')

    print("First readings from netcdf file.")
    earlier_seabird = netcdf.next()
    later_seabird = netcdf.next()

    # now we get to the images... (and related data)
    print("Begin parsing images.")

    first_image = None
    last_image = None
    image_list = []
    # campaign_name = auvdeployment.campaign.short_name
    # deployment_name = auvdeployment.short_name
    count = 0
    for row in track_parser:
        count += 1
        current_image = {}
        image_name = os.path.splitext(row['leftimage'])[0] + ".tif"

        image_datetime = datetime.datetime.strptime(os.path.splitext(image_name)[0], "PR_%Y%m%d_%H%M%S_%f_LC16")
        image_datetime = image_datetime.replace(tzinfo=tzutc())
        current_image['date_time'] = str(image_datetime)
        current_image['position'] = "POINT ({0} {1})".format(row['longitude'], row['latitude'])
        current_image['latitude'] = row['latitude']
        current_image['longitude'] = row['longitude']

        depth = float(row['depth'])
        current_image['depth'] = row['depth']
        # quickly calculate limit info

        if depth > float(auvdeployment['max_depth']):
            auvdeployment['max_depth'] = str(depth)

        if depth < float(auvdeployment['min_depth']):
            auvdeployment['min_depth'] = str(depth)

        lat_lim.check(row)
        lon_lim.check(row)

        # calculate image locations and create thumbnail
        current_image['image_path'] = os.path.join(image_subfolder, image_name)

        # get the extra measurements from the seabird data
        while image_datetime > later_seabird['date_time'] and not netcdf.isFinished():
            later_seabird, earlier_seabird = earlier_seabird, netcdf.next()

        # find which is closer - could use interpolation instead
        if (later_seabird['date_time'] - image_datetime) > (image_datetime - earlier_seabird['date_time']):
            closer_seabird = earlier_seabird
        else:
            closer_seabird = later_seabird

        current_image['temperature'] = closer_seabird['temperature']
        current_image['salinity'] = closer_seabird['salinity']
        current_image['roll'] = row['roll']
        current_image['pitch'] = row['pitch']
        current_image['yaw'] = row['heading']
        current_image['altitude'] = row['altitude']
        current_image['camera'] = leftcamera['name']
        current_image['camera_angle'] = leftcamera['angle']

        image_list.append(current_image)

        # we need first and last to get start/end points and times
        last_image = current_image
        if first_image is None:
            first_image = current_image

    # now save the actual min/max depth as well as start/end times and
    # start position and end position

    print 'done with ', count, 'images'
    auvdeployment['start_time_stamp'] = first_image['date_time']
    auvdeployment['end_time_stamp'] = last_image['date_time']

    auvdeployment['start_position'] = first_image['position']
    auvdeployment['end_position'] = last_image['position']

    auvdeployment['transect_shape'] = 'POLYGON(({0} {2}, {0} {3}, {1} {3}, {1} {2}, {0} {2} ))'.format(lon_lim.minimum, lon_lim.maximum, lat_lim.minimum, lat_lim.maximum)

    return auvdeployment, image_list


def is_image(image_path):
    """ boolean test for useful image class
    """
    if imghdr.what(image_path) == 'jpeg' or imghdr.what(image_path) == 'png':
        return True
    else:
        return False


def convert_file(local_tuple):
    """ convert image to a Catami safe format
    """
    input_image = local_tuple[0]
    output_image = local_tuple[1]
    quality_val = 90
    try:
        Image.open(input_image).save(output_image, quality=quality_val)
    except Exception, e:
        raise e


def convert_deployment(deployment_import_path, deployment_output_path):
    """ creates a new directory and populates it with a Catami format structure based on the deployment
        found in 'deployment_import_path'.
        Images are converted to JPG
    """

    success = True

    print 'import path is', deployment_import_path
    print 'output path is', deployment_output_path

    files = AUVImporter.dependency_get(deployment_import_path)
    auvdeployment, image_list = auvdeployment_import(files)

    if auvdeployment is None or image_list is None:
        success = False

    if success:

        try:
            os.makedirs(deployment_output_path)
        except OSError as exception:
                raise exception

        print deployment_import_path.split('/')[-2]
        print deployment_import_path.split('/')[-1]

        if deployment_import_path[-1] == '/':
            auvdeployment['short_name'] = deployment_import_path.split('/')[-2]
        else:
            auvdeployment['short_name'] = deployment_import_path.split('/')[-1]

        if not os.path.isfile(os.path.join(deployment_output_path, images_filename)):
            with open(os.path.join(deployment_output_path, images_filename), "w") as f:
                version_string = 'version:'+current_format_version+'\n'
                f.write(version_string)
                headers = 'Time ,Latitude , Longitude  , Depth  , ImageName , CameraName , CameraAngle , Temperature (celcius) , Salinity (psu) , Pitch (radians) , Roll (radians) , Yaw (radians) , Altitude (metres)\n'
                f.write(headers)
        print 'Made', images_filename, 'in', deployment_output_path

        # make the description file if it doesn't exist
        if not os.path.isfile(os.path.join(deployment_output_path, description_filename)):
            with open(os.path.join(deployment_output_path, description_filename), "w") as f:
                version_string = 'version:'+current_format_version+'\n'
                f.write(version_string)
                deployment_type_string = 'Type: AUV\n'
                f.write(deployment_type_string)
                Description_string = 'Description:'+auvdeployment['short_name']+' Imported AUV\n'
                f.write(Description_string)
                Operater_string = 'Operator: \n'
                f.write(Operater_string)
                Keyword_string = 'Keywords: \n'
                f.write(Keyword_string)

        print 'Made', description_filename, 'in', auvdeployment['short_name']

        count = 0

        print 'Making images index...'
        pbar = ProgressBar(widgets=[Percentage(), Bar(), Timer()], maxval=len(image_list)).start()

        for image in image_list:
                count = count + 1
                pbar.update(count)
                image_name = os.path.splitext(image['image_path'].split('/')[-1])[0]+'.jpg'
                #append to csv
                with open(os.path.join(deployment_output_path, images_filename), "a") as f:
                    # in CATAMI 'depth' is depth of seafloor.  AUV 'depth' is depth of platform, so seafloor depth is AUV depth+ AUV altitude
                    depth_actual = float(image['depth']) + float(image['altitude'])

                    csv_string = image['date_time']+','+str(image['latitude'])+','+str(image['longitude'])+','+str(depth_actual)+','+image_name+','+image['camera']+','+image['camera_angle']+','+str(image['temperature'])+','+str(image['salinity'])+','+str(image['pitch'])+','+str(image['roll'])+','+str(image['yaw'])+','+str(image['altitude'])+'\n'
                    f.write(csv_string)
        pbar.finish()

        image_name_list = []
        for image in image_list:
            image_name_list.append((image['image_path'], os.path.join(deployment_output_path, os.path.splitext(image['image_path'].split('/')[-1])[0]+'.jpg')))
        # for image in image_list:
        #     count = count + 1
        #     pbar.update(count)
        #     image_name = image['image_path']
        #     new_image_name = os.path.join(deployment_output_path, os.path.splitext(image['image_path'].split('/')[-1])[0]+'.jpg')
        #     try:
        #         Image.open(image_name).save(new_image_name)
        #     except IOError:
        #         print "cannot convert", image_name

        print 'Making image conversions for Catami...'
        pbar = ProgressBar(widgets=[Percentage(), Bar(), Timer()], maxval=len(image_list)).start()
        count = 0
        pool = Pool(processes=10)
        rs = pool.imap_unordered(convert_file, image_name_list)
        pool.close()

        count = 0
        num_tasks = len(image_name_list)
        while (True):
            pbar.update(rs._index)
            if (rs._index == num_tasks):
                break
            time.sleep(0.5)
        pbar.finish()

    print 'Added ', count, 'entries in', deployment_output_path, ":", images_filename

    return success


def main():
    """Builds Catami format package for Kayak AIMS data
    """

    if make_deployment:
        convert_deployment(root_import_path, root_output_path)
    else:
        #look for dirs in the root dir. Ignore pesky hidden dirs added by various naughty things
        directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

        if len(directories) == 0:
            raise Exception('I didn\'t find any directories to import. Check that the specified path contains kayak image directories.')

        if not os.path.isfile(os.path.join(root_import_path, campaign_filename)):
            with open(os.path.join(root_import_path, campaign_filename), "w") as f:
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
        print 'Made', campaign_filename, 'in', root_import_path

        for directory in directories:
            convert_deployment(os.path.join(root_import_path, directory), os.path.join(root_output_path, directory))

    print '...All done'


if __name__ == "__main__":
        main()
