#! /usr/bin/env python
# -*- coding: utf-8 -*-

""" Validate and upload Catami project to specified server

expects file structure as

Root Dir
  |--Campaign.txt
  |--Image Dir 01
  |       |--description.txt
  |       |--images.csv
  |       |--images01.jpg
  |       |--images02.jpg
  |       |-- ...
  |--Image Dir 02
  |       |--description.txt
  |       |--images.csv
  |       |--images01.jpg
  |       |--images02.jpg
  |       |-- ...
  ...

v1.0 30/05/2013 markg@ivec.org
"""
import os
import os.path
import argparse

#web interaction
import urlparse
import requests
import httplib

#format support
import csv
import json
import numpy as np

from multiprocessing import Pool
import time

# progress bars
from progressbar import ProgressBar, Percentage, Bar, Timer

from PIL import Image
# from PIL.ExifTags import TAGS, GPSTAGS

# Command line options setup
parser = argparse.ArgumentParser()

parser.add_argument('--validate', action='store_true', default=False, help='Validate only, do not upload anything to a Catami server.')

parser.add_argument('--server', nargs=1, help='Catami server location for upload, ie: http://catami.org')
parser.add_argument('--username', nargs=1, help='User name for your Catami account.')
parser.add_argument('--apikey', nargs=1, help='API Key for your Catami account, please see your Catami admin.')

group = parser.add_mutually_exclusive_group()
group.add_argument('--deployment', nargs=1, help='Path to root Catami data directory for campaign, ie: /data/somthing/some_campaign. You must also specify --campaign-api')
group.add_argument('--campaign', nargs=1, help='Path to root Catami data directory for campaign, ie: /data/somthing/some_campaign')

parser.add_argument('--campaign_api', nargs=1, help='URL for Campaign specified at --server')

args = parser.parse_args()

if not args.validate:
    if args.deployment and not args.campaign:
        parser.exit(1, 'You must specify --deployment or --campaign')

    if not args.deployment and not args.campaign_api:
        parser.exit(1, 'You must specify --campaign_api with --deployment')

    if args.campaign and args.campaign_api:
        parser.exit(1, 'You cannot specify --campaign_api with --campaign')

    if args.server:
        server_root = args.server[0]
    if args.username:
        username = args.username[0]
    if args.apikey:
        apikey = args.apikey[0]

if not args.validate:
    if not args.server or not args.username or not args.apikey:
            parser.exit(1, 'You must specify --server, --username and --apikey, or use --validate. See --help for more info.')

#Filenames for critical campaign/deployment files
images_filename = 'images.csv'
description_filename = 'description.txt'
campaign_filename = 'campaign.txt'

#used to check for duplicate POST attempting
duplicate_error_message = 'duplicate key value violates unique constraint'


def get_status_code(host, path="/"):
    """ This function retreives the status code of a website by requesting
        HEAD data from the host. This means that it only requests the headers.
        If the host cannot be reached or something else goes wrong, it returns
        None instead.
    """
    try:
        conn = httplib.HTTPConnection(server_root, 80)
        conn.request("HEAD", path)
        return conn.getresponse().status
    except StandardError:
        return None


def check_url(server, path):
    """ Does simple check on server+path to verify response
    """

    r = requests.get(urlparse.urljoin(server, path))
    if r.status_code != requests.codes.ok:
        print 'FAILED: server API problem detected for', path
        return False

    return True


def basic_import_checks(root_import_path, server_root):
    """Basic Checks, for directories, key files and the server
    """

    everthing_is_fine = True

    if not os.path.isdir(root_import_path):
        everthing_is_fine = False
        print 'ERROR: This is not a valid path. Check the path to your Catami data package.'

    if get_status_code(server_root, '/api/dev') == 404:
        everthing_is_fine = False
        print 'ERROR: Something\'s wrong with the server:', server_root

    #  check for expected files
    if not os.path.isfile(os.path.join(root_import_path, campaign_filename)):
        everthing_is_fine = False
        print 'MISSING: Campaign file is missing at', root_import_path

    directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

    if len(directories) == 0:
        everthing_is_fine = False
        print('MISSING: I didn\'t find any directories to import. Check that the specified path contains the expected image directories.')

    for directory in directories:
        image_dir = os.path.join(root_import_path, directory)
        if not check_deployment_files(image_dir):
            print 'MISSING: Deployment is incomplete at', image_dir
            everthing_is_fine = False

    return everthing_is_fine


def check_deployment_files(deployment_path):

    everthing_is_fine = True

    if not os.path.isfile(os.path.join(deployment_path, images_filename)):
        everthing_is_fine = False
        print 'MISSING:images.csv file is missing in', deployment_path

    if not os.path.isfile(os.path.join(deployment_path, description_filename)):
        everthing_is_fine = False
        print 'MISSING:description.txt file is missing in', deployment_path

    return everthing_is_fine


def check_deployment_images(deployment_path):
    """Check deployment imagery for valid list and valid imagery
    """

    print 'MESSAGE: Checking Deployment', images_filename, '...'
    bad_image_count = 0
    good_image_count = 0

    if os.path.isfile(os.path.join(deployment_path, images_filename)):
        with open(os.path.join(deployment_path, images_filename), 'rb') as csvfile:

            #read the CSV file, scanning for null bytes that the csv row parser cannot handle
            images_reader = csv.reader(x.replace('\0', '') for x in csvfile)

            row_index = 2
            #skip the header rows (2)
            images_reader.next()
            images_reader.next()

            # any missing **required** fields will make this false. spawns MISSING error. Fatal.
            is_complete = True

            # True if something wierd happens
            is_broken = False

            for row in images_reader:
                row_index = row_index + 1
                # any missing **required** fields will make this false. spawns MISSING error. Fatal.
                row_is_complete = True

                # any missing data will make this false. spawns a warning.
                row_has_missing = False

                # True if something wierd happens
                row_is_broken = False

                time_string = row[0]
                latitude = row[1]
                longitude = row[2]
                depth = row[3]
                image_name = row[4]
                camera_name = row[5]
                camera_angle = row[6]
                salinity = row[7]
                pitch = row[8]
                roll = row[9]
                yaw = row[10]
                altitude = row[11]

                #image list validation
                #required
                if time_string is None or str(time_string) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'Time is required'
                    row_has_missing = True
                if latitude is None or str(latitude) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'latitude is required'
                    row_has_missing = True
                if longitude is None or str(longitude) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'longitude is required'
                    row_has_missing = True
                if depth is None or str(depth) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'depth is required'
                    row_has_missing = True
                if image_name is None or str(image_name) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'image_name is required'
                    row_has_missing = True
                if camera_name is None or str(camera_name) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'camera_name is required'
                    row_has_missing = True
                if camera_angle is None or str(camera_angle) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'camera_angle is required'
                    row_has_missing = True

                #not required
                if salinity is None or str(salinity) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'salinity is missing'
                if pitch is None or str(pitch) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'pitch is missing'
                if roll is None or str(roll) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'roll is missing'
                if yaw is None or str(yaw) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'yaw is missing'
                if altitude is None or str(altitude) == 'None':
                    print 'MISSING:', images_filename, 'row:', row_index, 'altitude is missing'

                if not (image_name is None or str(image_name) == 'None'):
                    #lets check this image
                    if os.path.isfile(os.path.join(deployment_path, image_name)):
                        try:
                            Image.open(os.path.join(deployment_path, image_name))
                            good_image_count = good_image_count + 1
                        except:
                            bad_image_count = bad_image_count + 1
                            print 'ERROR:', image_name, ' appears to be an invalid image'
                    else:
                        print 'MISSING:', image_name, ' references in images.csv'
                        row_is_complete = False

                #let's decide what to do with this row
                if not row_is_complete:
                    is_complete = False

                if row_is_broken:
                    is_broken = True

            if bad_image_count > 0:
                print 'ERROR:', bad_image_count, '(of', good_image_count, ') bad images were found'
                is_broken = True
            else:
                print 'SUCCESS:', good_image_count, ' images checked'

            #did something important break?
            if is_broken:
                return False

            return is_complete


def read_images_file(deployment_path):
    """read images file and put data into a big structure for manipulation
    """
    image_data = []

    if os.path.isfile(os.path.join(deployment_path, images_filename)):
        with open(os.path.join(deployment_path, images_filename), 'rb') as csvfile:
            images_reader = csv.reader(x.replace('\0', '') for x in csvfile)

            row_index = 2
            #skip the header rows (2)
            images_reader.next()
            images_reader.next()

            for row in images_reader:
                row_index = row_index + 1
                image_data_instance = dict(time=row[0],
                                           latitude=row[1],
                                           longitude=row[2],
                                           depth=row[3],
                                           image_name=row[4],
                                           camera_name=row[5],
                                           camera_angle=row[6],
                                           temperature=row[7],
                                           salinity=row[8],
                                           pitch=row[9],
                                           roll=row[10],
                                           yaw=row[11],
                                           altitude=row[12])
                image_data.append(image_data_instance)
    else:
        print os.path.join(deployment_path, images_filename), 'is no'

    return image_data


def read_deployment_file(deployment_path):
    """reads the description.txt file for the specified deployment
    """

    deployment_info = {}
    if os.path.isfile(os.path.join(deployment_path, description_filename)):
        f = open(os.path.join(deployment_path, description_filename))

        for line in f.readlines():
            split_string = line.rstrip().split(':')
            if split_string[0].lower() == 'Version'.lower():
                deployment_info['version'] = split_string[1].strip()
            elif split_string[0].lower() == 'Type'.lower():
                deployment_info['type'] = split_string[1].strip()
            elif split_string[0].lower() == 'Description'.lower():
                deployment_info['description'] = split_string[1]
            elif split_string[0].lower() == 'Operator'.lower():
                deployment_info['operator'] = split_string[1]
            elif split_string[0].lower() == 'Keywords'.lower():
                deployment_info['keywords'] = split_string[1]

    return deployment_info


def check_deployment(deployment_path):
    """Check deployment for valid contents; description.txt, images.csv and the images themselves
    """
    print 'MESSAGE: Checking', deployment_path

    if os.path.isfile(os.path.join(deployment_path, description_filename)):
        type_list = ['AUV', 'BRUV', 'TI', 'DOV', 'TV']
        # any missing **required** fields will make this false. spawns MISSING error. Fatal.
        is_complete = True

        # any missing data will make this false. spawns a warning.
        is_minally_ok = True

        # True if something wierd happens
        is_broken = False  # True if something wierd happens. Fatal

        deployment_info = read_deployment_file(deployment_path)

        if deployment_info['version'].replace(" ", "") != '1.0':
            print 'ERROR: Version must be 1.0'
            is_broken = True
        if len(deployment_info['type'].replace(" ", "")) == 0:
            print 'MISSING:', description_filename, ': deployment type is required'
            is_complete = False
        if len(deployment_info['description'].replace(" ", "")) == 0:
            print 'MISSING:', description_filename, ': deployment description is required'
            is_complete = False

        #check type
        if not deployment_info['type'].upper() in type_list:
            print 'ERROR: Deployment type of', deployment_info['type'], 'is not recognised. Must be one of', type_list
            is_broken = True

        if is_complete:
            print 'SUCCESS:', description_filename, 'is verified'
            return True
        else:
            print 'FAILED:', description_filename, 'is missing required fields. Verification failed. Check earlier messages.'
            return False

        if not is_complete and is_minally_ok:
            print 'SUCCESS:', description_filename, 'is missing optional fields. Review earlier messages.'
            return True

        if is_broken:
            print 'FAILED:', description_filename, 'appears to have some bad fields. Check earlier messages'
            return False


def scan_deployment(deployment_path):
    """Scan deployment for data constraints found in images.csv
    returns a dict of the data needed for the deployment POST
    """
    deployment_post_data = {}

    deployment_info = read_deployment_file(deployment_path)

    print 'MESSAGE: Scanning', deployment_path
    image_data = read_images_file(deployment_path)

    # need to find the first image with a lat long
    first_valid_image = None

    for im in image_data:
        if (im['latitude'] is not None and str(im['latitude']) != 'None') and (im['longitude'] is not None and str(im['latitude']) != 'None'):
                first_valid_image = im
                break

    if first_valid_image is None:
        # somehow we got here after all that validation. have to abort. something bad has happened.
        return None

    depth_data_temp = []
    latitude_data_temp = []
    longitude_data_temp = []
    for im in image_data:
        if im['latitude'] is not None and str(im['latitude']) != 'None':
            latitude_data_temp.append(float(im['latitude']))
        if im['longitude'] is not None and str(im['longitude']) != 'None':
            longitude_data_temp.append(float(im['longitude']))
        if im['depth'] is not None and str(im['depth']) != 'None':
            depth_data_temp.append(float(im['depth']))

    depth_array = np.array(depth_data_temp, dtype=float)
    latitude_array = np.array(latitude_data_temp, dtype=float)
    longitude_array = np.array(longitude_data_temp, dtype=float)

    bounding_polygon = 'SRID=4326;POLYGON(('+str(longitude_array.min())+' '+str(latitude_array.min())+','\
        + str(longitude_array.max())+' '+str(latitude_array.min())+','\
        + str(longitude_array.max())+' '+str(latitude_array.max())+','\
        + str(longitude_array.min())+' '+str(latitude_array.max())+','\
        + str(longitude_array.min())+' '+str(latitude_array.min())+'))'

    #note that geo arguments are very picky about internal space characters (only between long/lat pairs)
    #note also: geo order is long/lat
    deployment_post_data['type'] = deployment_info['type']
    deployment_post_data['start_position'] = 'SRID=4326;POINT('+first_valid_image['longitude']+' '+first_valid_image['latitude']+')'
    deployment_post_data['end_position'] = 'SRID=4326;POINT('+image_data[-1]['longitude']+' '+image_data[-1]['latitude']+')'

    deployment_post_data['transect_shape'] = bounding_polygon
    deployment_post_data['start_time_stamp'] = first_valid_image['time']
    deployment_post_data['end_time_stamp'] = image_data[-1]['time']

    if deployment_path[-1] == '/':
        deployment_post_data['short_name'] = deployment_path.split('/')[-2]
    else:
        deployment_post_data['short_name'] = deployment_path.split('/')[-1]

    deployment_post_data['mission_aim'] = deployment_info['description']
    deployment_post_data['min_depth'] = str(depth_array.min())
    deployment_post_data['max_depth'] = str(depth_array.max())
    deployment_post_data['campaign'] = ''
    deployment_post_data['contact_person'] = deployment_info['operator']
    deployment_post_data['descriptive_keywords'] = deployment_info['keywords']
    deployment_post_data['license'] = 'CC-BY'

    return deployment_post_data


def get_camera_data(image_data):
    """ checks images list for the camera a returns a dict for posting
        Note: will eventually handle the multiple camera case, if we ever see a deployment with such.
    """

    if image_data is None:
        # holy hell, something has gone wrong here
        print 'FAILED: Failed to get image data for camera data'
        return None

    if image_data['camera_angle'].lower() == 'Downward'.lower():
        angle_value = 0
    elif image_data['camera_angle'].lower() == 'Upward'.lower():
        angle_value = 1
    elif image_data['camera_angle'].lower() == 'Slanting/Oblique'.lower():
        angle_value = 2
    elif image_data['camera_angle'].lower() == 'Horizontal/Seascape'.lower():
        angle_value = 3
    else:
        print 'FAILED: camera angle of', image_data['camera_angle'].lower(), 'was not recognised.'
        return None

    camera_data = dict(name=image_data['camera_name'],
                       angle=str(angle_value))

    return camera_data


def read_campaign(root_import_path):
    """ reads campaign.txt and returns contents in a dict
    """
    if os.path.isfile(os.path.join(root_import_path, campaign_filename)):
        # any missing **required** fields will make this false. spawns MISSING error. Fatal.
        #is_complete = True

        # any missing data will make this false. spawns a warning.
        #is_minally_ok = True

        # True if something wierd happens
        is_broken = False  # True if something wierd happens. Fatal

        version = ''
        name = ''
        description_text = ''
        assoc_researchers_text = ''
        assoc_publications_text = ''
        assoc_research_grants_text = ''
        start_date_text = ''
        end_date_text = ''
        contact_person_text = ''

        f = open(os.path.join(root_import_path, campaign_filename))

        for line in f.readlines():

            split_string = line.rstrip().split(':')

            if split_string[0].lower() == 'Version'.lower():
                version = split_string[1]
            elif split_string[0].lower() == 'Name'.lower():
                name = split_string[1]
            elif split_string[0].lower() == 'Description'.lower():
                description_text = split_string[1]
            elif split_string[0].lower() == 'Associated Researchers'.lower():
                assoc_researchers_text = split_string[1]
            elif split_string[0].lower() == 'Associated Publications'.lower():
                assoc_publications_text = split_string[1]
            elif split_string[0].lower() == 'Associated Research Grants'.lower():
                assoc_research_grants_text = split_string[1]
            elif split_string[0].lower() == 'Start Date'.lower():
                start_date_text = split_string[1]
            elif split_string[0].lower() == 'End Date'.lower():
                end_date_text = split_string[1]
            elif split_string[0].lower() == 'Contact Person'.lower():
                contact_person_text = split_string[1]
            else:
                print 'ERROR: Unknown label in campaign file;', split_string[0]
                is_broken = True

        campaign_data = dict(version=version,
                             short_name=name,
                             description=description_text,
                             associated_researchers=assoc_researchers_text,
                             associated_publications=assoc_publications_text,
                             associated_research_grants=assoc_research_grants_text,
                             date_start=start_date_text,
                             date_end=end_date_text,
                             contact_person=contact_person_text)
        return campaign_data

    return False


def check_campaign(root_import_path):
    """Check campaign.txt for valid contents
    """
    #check campaign file
    if os.path.isfile(os.path.join(root_import_path, campaign_filename)):
        # any missing **required** fields will make this false. spawns MISSING error. Fatal.
        is_complete = True

        # any missing data will make this false. spawns a warning.
        is_minally_ok = True

        # True if something wierd happens
        is_broken = False  # True if something wierd happens. Fatal

        version = ''
        name = ''
        description_text = ''
        assoc_researchers_text = ''
        assoc_publications_text = ''
        assoc_research_grants_text = ''
        start_date_text = ''
        end_date_text = ''
        contact_person_text = ''

        f = open(os.path.join(root_import_path, campaign_filename))

        for line in f.readlines():

            split_string = line.rstrip().split(':')

            if split_string[0].lower() == 'Version'.lower():
                version = split_string[1]
            elif split_string[0].lower() == 'Name'.lower():
                name = split_string[1]
            elif split_string[0].lower() == 'Description'.lower():
                description_text = split_string[1]
            elif split_string[0].lower() == 'Associated Researchers'.lower():
                assoc_researchers_text = split_string[1]
            elif split_string[0].lower() == 'Associated Publications'.lower():
                assoc_publications_text = split_string[1]
            elif split_string[0].lower() == 'Associated Research Grants'.lower():
                assoc_research_grants_text = split_string[1]
            elif split_string[0].lower() == 'Start Date'.lower():
                start_date_text = split_string[1]
            elif split_string[0].lower() == 'End Date'.lower():
                end_date_text = split_string[1]
            elif split_string[0].lower() == 'Contact Person'.lower():
                contact_person_text = split_string[1]
            else:
                print 'ERROR: Unknown label in campaign file;', split_string[0]
                is_broken = True

        if version.replace(" ", "") != '1.0':
            print 'ERROR: Version must be 1.0'
            is_broken = True

        if len(name.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': campaign name is required'
            is_complete = False

        if len(description_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': description is required'
            is_complete = False

        if len(assoc_researchers_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': associated researchers is required'
            is_complete = False

        if len(assoc_publications_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': associated publications is required'
            is_complete = False

        if len(assoc_research_grants_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': associated research grants is required'
            is_complete = False

        if len(start_date_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': start date is required'
            is_complete = False

        if len(end_date_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': end date is required'
            is_complete = False

        if len(contact_person_text.replace(" ", "")) == 0:
            print 'MISSING:', campaign_filename, ': contact person is required'
            is_complete = False

        # check that end date is not before start date (TBD)
        # final summary
        if is_complete:
            print 'SUCCESS: Campaign.txt is verified'
            return True
        else:
            print 'FAILED: Campaign.txt is missing required fields. Verification failed. Check earlier messages.'
            return False

        if not is_complete and is_minally_ok:
            print 'SUCCESS: Campaign.txt is missing optional fields. Review earlier messages.'
            return True

        if is_broken:
            print 'FAILED: Campaign.txt appears to have some bad fields. Check earlier messages'
            return False


def post_campaign_to_server(root_import_path, server_root, user_name, api_key):
    """Iterates through campaign directory POSTing data/imagery to the API at a specified Catami server
        If the object to be posted already exists, silently moves to the next one as needed
    """

    campaign_api_path = '/api/dev/campaign/'

    url = urlparse.urljoin(server_root, campaign_api_path)
    params = dict(username=user_name, api_key=api_key)
    campaign_data = read_campaign(root_import_path)

    # r = requests.get('http://localhost:8000/accounts/mangop/', auth=(username,password))
    # print r.text
    # body = {'id_identification': 'mangop', 'id_password': 'bugger123'}
    # headers = {'Content-type': 'application/x-www-form-urlencoded'}
    # r = http.request_encode_body('POST', url, fields=body, headers=headers)

    #POST campaign.  If the campaign already exists we are probably trying to resume
    # a previously incomplete upload.  In that case we find out which current campaign matches
    # the campaign we get from the campaign.txt and move on.

    print 'SENDING: Campaign info...'

    headers = {'Content-type': 'application/json'}

    r = requests.post(url, data=json.dumps(campaign_data), headers=headers, params=params)
    if r.status_code == requests.codes.created:
        campaign_url = r.headers['location']
        print 'SUCCESS: Campaign header data uploaded:', campaign_url
    elif duplicate_error_message.lower() in r.text.lower():
        url = urlparse.urljoin(server_root, campaign_api_path)
        params['short_name'] = campaign_data['short_name']
        params['date_start'] = campaign_data['date_start']

        r = requests.get(url, headers=headers, params=params)
        if r.status_code != requests.codes.ok:
            print 'FAILED: server API problem detected for', url
            print 'MESSAGE: Full message from server follows:'
            print r.text
            return False
        else:
            # we need the request to return 1 object.  If there is more than 1 (or 0) something is wrong
            if len(r.json()) > 1 or len(r.json()) == 0:
                print 'FAILED: Expected to find one matching campaign, but found', len(r.json())
                for jsonentry in r.json():
                    print 'check:', jsonentry['resource_uri']
                print 'MESSAGE: You should contact the Catami team to sort this out.'
                return False

            campaign_url = r.json()[0]['resource_uri']
            print 'MESSAGE: Resuming upload of', campaign_url
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print str(r.text)
        return False

    #POST deployment/s

    directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

    for directory in directories:
        print 'SENDING: Deployment info for', directory
        if not post_deployment_to_server(os.path.join(root_import_path, directory), server_root, user_name, api_key, urlparse.urlsplit(campaign_url).path):
            return False

    return True


def post_image_to_image_url(post_package):
    """Posts an image to the server using file POST
        If the file already exists, silently moves on.
    """

    status = True

    duplicate_text_head = 'Destination path'
    duplicate_text_tail = 'already exists'

    #image POST also needs:
    #'deployment': deployment ID number
    post_data = {'deployment': post_package['deployment']}
    params = dict(username=post_package['username'], api_key=post_package['user_apikey'])

    url = urlparse.urljoin(server_root, post_package['image_object_api_path'])
    if os.path.isfile(os.path.join(post_package['deployment_path'], post_package['image_name'])):
        image_file = {'img': open(os.path.join(post_package['deployment_path'], post_package['image_name']), 'rb')}
    else:
        print 'FAILED: expect image missing at', os.path.join(post_package['deployment_path'], post_package['image_name'])
        return False

    r = requests.post(url, files=image_file, params=params, data=post_data)

    if duplicate_text_head in r.text and duplicate_text_tail in r.text:
        # this image already exists, we have nothing to do.
        status = True
    elif not (r.status_code == requests.codes.created):
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print r.text
        status = False

    return status


def post_deployment_to_server(deployment_path, server_root, username, user_apikey, campaign_url):
    """Iterates through campaign directory POSTing data/imagery to the API at a specified Catami server
    """

    deployment_api_path = '/api/dev/deployment/'
    image_metadata_api_path = '/api/dev/image/'
    camera_api_path = '/api/dev/camera/'
    measurement_api_path = '/api/dev/measurements/'
    image_object_api_path = '/api/dev/image_upload/'

    # check API interfaces before we get started
    api_fail_count = 0

    if not check_url(server_root, deployment_api_path):
        api_fail_count += 1
        print 'FAILED: API unavailable at', deployment_api_path
    if not check_url(server_root, image_metadata_api_path):
        api_fail_count += 1
        print 'FAILED: API unavailable at', image_metadata_api_path
    if not check_url(server_root, camera_api_path):
        api_fail_count += 1
        print 'FAILED: API unavailable at', camera_api_path
    if not check_url(server_root, measurement_api_path):
        api_fail_count += 1
        print 'FAILED: API unavailable at', measurement_api_path

    if api_fail_count > 0:
        return False

    url = urlparse.urljoin(server_root, deployment_api_path)
    params = dict(username=username, api_key=user_apikey)

    #get deployment data for POST

    deployment_post_data = scan_deployment(deployment_path)
    if deployment_post_data is None:
        print 'FAILED: Deployment scan failed'
        return False

    #add the camppaign, the deployment doesn't really know about it
    deployment_post_data['campaign'] = campaign_url

    #POST deployment data
    print 'SENDING: Deployment info...'
    headers = {'Content-type': 'application/json'}
    r = requests.post(url, data=json.dumps(deployment_post_data), headers=headers, params=params)
    if (r.status_code == requests.codes.created):
        deployment_url = r.headers['location']
        print 'SUCCESS: Deployment header data uploaded:', urlparse.urlsplit(deployment_url).path
    elif duplicate_error_message.lower() in r.text.lower():
        # an object that looks like the post object already exists

        params['short_name'] = deployment_post_data['short_name']

        r = requests.get(url, headers=headers, params=params)
        if r.status_code != requests.codes.ok:
            print 'FAILED: server API problem detected for', url
            print 'MESSAGE: Full message from server follows:'
            print r.text
            return False
        else:
            # we need the request to return 1 object.  If there is more than 1 (or 0) something is wrong
            if len(r.json()) > 2 or len(r.json()) == 0:
                print 'FAILED: Expected to find one matching deployment, but found', len(r.json())
                for jsonentry in r.json():
                    print 'check:', jsonentry['resource_uri']
                print 'MESSAGE: You should contact the Catami team to sort this out.'
                return False

            deployment_url = r.json()['objects'][0]['resource_uri']
            print 'MESSAGE: Resuming upload of', deployment_url
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        return False

    # POST images for deployment

    image_data = read_images_file(deployment_path)

    #main image posting loop.

    print 'MESSAGE: Uploading data to server.'
    count = 0

    list_for_posting = []
    image_data_posted = []
    # STEP 1: post image meta data
    for index, current_image in enumerate(image_data):

        params = dict(username=username, api_key=user_apikey)

        # if the image has no lat/long we skip it here
        if str(current_image['latitude']).lower() == 'None'.lower() or str(current_image['longitude']).lower() == 'None'.lower():
            continue

        # STEP 1 post the image metadata
        image_metadata = dict(web_location="",
                              archive_location="None",
                              image_name=current_image["image_name"],
                              deployment=str(urlparse.urlsplit(deployment_url).path),
                              date_time=current_image["time"],
                              position="SRID=4326;POINT("+current_image["longitude"]+" "+current_image["latitude"]+")",
                              depth=current_image["depth"])
        image_data_posted.append(current_image)
        list_for_posting.append(image_metadata);

    print 'MESSAGE: [Step 1/4] Uploading image metadata to server'
    pbar = ProgressBar(widgets=[Percentage(), Bar(), Timer()], maxval=len(image_data)).start()

    url = urlparse.urljoin(server_root, image_metadata_api_path)
    headers = {'Content-type': 'application/json'}

    jsonlist  = {}
    jsonlist["objects"] = list_for_posting

    r = requests.patch(url, data=json.dumps(jsonlist), headers=headers, params=params)
    if (r.status_code == requests.codes.accepted):
        print "SUCCESS: Image data was uploaded"
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print r.text
        return False
    pbar.finish()

    created_image_objects = json.loads(r.text)['objects']
     
    print 'MESSAGE: [Step 2/5] Preparing camera/measurement metadata'
    
    camera_list_for_post = []
    measurement_list_for_post = []
    image_list_for_posting = []

    # prepare Camera and Measurement Data and image post data
    for index, current_image in enumerate(image_data_posted):
        camera_data = get_camera_data(current_image)
        if camera_data is None:
            print 'FAILED: Could not get camera data for deployment'
            return False
        # add the image api url for camera
        camera_data['image'] = urlparse.urlsplit(created_image_objects[index]['resource_uri']).path
        camera_list_for_post.append(camera_data)
        
        measurement_data = dict(image=urlparse.urlsplit(created_image_objects[index]['resource_uri']).path,
                                temperature=current_image['temperature'],
                                salinity=current_image['salinity'],
                                pitch=current_image['pitch'],
                                roll=current_image['roll'],
                                yaw=current_image['yaw'],
                                altitude=current_image['altitude'])
        measurement_list_for_post.append(measurement_data)

        data_package = current_image

        data_package['deployment'] = deployment_url.split('/')[-2]
        data_package['deployment_path'] = deployment_path
        data_package['image_object_api_path'] = image_object_api_path
        data_package['username'] = params['username']
        data_package['user_apikey'] = params['api_key']

        image_list_for_posting.append(data_package)

    print 'SUCCESS: Camera/measurement metadata ready'

    print 'MESSAGE: [Step 3/5] Uploading camera metadata to server'
    pbar = ProgressBar(widgets=[Percentage(), Bar(), Timer()], maxval=len(image_data)).start()
    jsonlist  = {}
    jsonlist["objects"] = camera_list_for_post
    url = urlparse.urljoin(server_root, camera_api_path)
    headers = {'Content-type': 'application/json'}
    r = requests.patch(url, data=json.dumps(jsonlist), headers=headers, params=params)
    pbar.finish()
    if (r.status_code == requests.codes.accepted):
        print 'SUCCESS: Camera metadata uploaded'
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print r.text
        return False

    print 'MESSAGE: [Step 4/5] Uploading measurement metadata to server'
    pbar = ProgressBar(widgets=[Percentage(), Bar(), Timer()], maxval=len(image_data)).start()
    jsonlist  = {}
    jsonlist["objects"] = measurement_list_for_post
    url = urlparse.urljoin(server_root, measurement_api_path)
    headers = {'Content-type': 'application/json'}
    r = requests.patch(url, data=json.dumps(jsonlist), headers=headers, params=params)
    pbar.finish()
    if (r.status_code == requests.codes.accepted):
        print 'SUCCESS: Measurement metadata uploaded'
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print r.text
        return False

    # need to upload one image first so that the deployment directory is created on the server
    status = post_image_to_image_url(image_list_for_posting[0])

    if not status:
        print 'FAILED: Image upload does not appear to be working. Contact a Catami admin or check your Catami Server'
        return False

    print 'MESSAGE: [Step 5/5] Uploading images to server...'
    pbar = ProgressBar(widgets=[Percentage(), Bar(), Timer()], maxval=len(image_list_for_posting)).start()
    pool = Pool(processes=10)
    rs = pool.imap_unordered(post_image_to_image_url, image_list_for_posting[1:])
    pool.close()

    num_tasks = len(image_list_for_posting) - 1
    while (True):
        pbar.update(rs._index)
        if (rs._index == num_tasks):
            break
        time.sleep(0.5)
    pbar.finish()

    processed_tasks = len(list(rs))

    if processed_tasks < num_tasks:
        print 'FAILED: processed',processed_tasks+1,'of',num_tasks+1,'...Something went wrong'
        return False

    print 'SUCCESS:',processed_tasks+1,'Images uploaded'

    return True


def main():
    """main routine
    """
    problem_found = False

    #campaign import
    if args.campaign:
        if not args.validate:
            root_import_path = args.campaign[0]

        print 'MESSAGE: Checking', root_import_path

        #  basic checks, does the dir exist? is the server live?
        if not basic_import_checks(root_import_path, server_root):
            print 'ERROR: Required files and/or resources are missing. Validation stopping right here. Fix errors and try again'
            problem_found = True

        if not problem_found:
            # if we are still going then all required files exist. Yay us!
            campaign_status = check_campaign(root_import_path)

            directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

            for directory in directories:
                deployment_status = check_deployment(os.path.join(root_import_path, directory))
                deployment_status = check_deployment_images(os.path.join(root_import_path, directory))

            print 'SUCCESS: All checks are done, campaign is ready to upload'

            # username = 'pooper'
            # user_apikey = 'e688869735a817b60ae701d4d2c713ec9de67d67'

            if not args.validate:
                if post_campaign_to_server(root_import_path, server_root, username, apikey):
                    print 'SUCCESS: Everything went just great!'
                else:
                    print 'ERROR: Everything did not go just great :('

    # deployment import
    if args.deployment:
        deployment_dir = args.deployment[0]
        if not args.validate:
            campaign_api_path = args.campaign_api[0]

        print 'MESSAGE: Checking', deployment_dir

        deployment_status = True
        # basic check
        if not check_deployment_files(deployment_dir):
            print 'MISSING: Deployment is incomplete at', deployment_dir
            problem_found = True

        if not problem_found:
            deployment_status = check_deployment(deployment_dir)
            deployment_status = check_deployment_images(deployment_dir)

            if not args.validate:
                if deployment_status:
                    if post_deployment_to_server(deployment_dir, server_root, username, apikey, campaign_api_path):
                        print 'SUCCESS: Everything went just great!'
                    else:
                        print 'ERROR: Everything did not go just great :('
                else:
                        print 'ERROR: Everything did not go just great :('


if __name__ == "__main__":
    main()
