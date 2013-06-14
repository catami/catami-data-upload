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
import sys
import os
import os.path
import argparse
import urlparse
import requests
import httplib
import csv
import json
import numpy as np

from PIL import Image
# from PIL.ExifTags import TAGS, GPSTAGS

# Command line options setup
parser = argparse.ArgumentParser()
parser.add_argument('--campaign', nargs=1, help='Path to root Catami data directory for campaign, ie: /data/somthing/some_campaign')
parser.add_argument('--server', nargs=1, help='Catami server location for upload, ie: http://catami.org')
parser.add_argument('--username', nargs=1, help='User name for your Catami account')
parser.add_argument('--apikey', nargs=1, help='API Key for your Catami account, please see your Catami admin')

args = parser.parse_args()

root_import_path = args.campaign[0]
server_root = args.server[0]
username = args.username[0]
apikey = args.apikey[0]

#Filenames for critical campaign/deployment files
images_filename = 'images.csv'
description_filename = 'description.txt'
campaign_filename = 'campaign.txt'


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

        if not os.path.isfile(os.path.join(image_dir, images_filename)):
            everthing_is_fine = False
            print 'MISSING:images.csv file is missing in', image_dir

        if not os.path.isfile(os.path.join(image_dir, description_filename)):
            everthing_is_fine = False
            print 'MISSING:description.txt file is missing in', image_dir

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
                print 'SUCCESS:', good_image_count,' images checked'

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
    deployment_post_data['short_name'] = deployment_path
    deployment_post_data['mission_aim'] = deployment_info['description']
    deployment_post_data['min_depth'] = str(depth_array.min())
    deployment_post_data['max_depth'] = str(depth_array.max())
    deployment_post_data['campaign'] = ''
    deployment_post_data['contact_person'] = deployment_info['operator']
    deployment_post_data['descriptive_keywords'] = deployment_info['keywords']
    deployment_post_data['license'] = 'CC-BY'

    return deployment_post_data


def get_camera_data(deployment_path):
    """ checks images list for the camera a returns a dict for posting
        Note: will eventually handle the multiple camera case, if we ever see a deployment with such.
    """

    images_data = read_images_file(deployment_path)

    if images_data is None:
        # holy hell, something has gone wrong here
        print 'FAILED: Failed to read images.csv for camera data'
        return None

    if images_data[-1]['camera_angle'].lower() == 'Downward'.lower():
        angle_value = 0
    elif images_data[-1]['camera_angle'].lower() == 'Upward'.lower():
        angle_value = 1
    elif images_data[-1]['camera_angle'].lower() == 'Slanting/Oblique'.lower():
        angle_value = 2
    elif images_data[-1]['camera_angle'].lower() == 'Horizontal/Seascape'.lower():
        angle_value = 3
    else:
        print 'FAILED: camera angle of', images_data[-1]['camera_angle'].lower(), 'was not recognised.'
        return None

    camera_data = dict(name=images_data[-1]['camera_name'],
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

    #POST campaign

    print 'SENDING: Campaign info...'
    headers = {'Content-type': 'application/json'}
    r = requests.post(url, data=json.dumps(campaign_data), headers=headers, params=params)
    if (r.status_code == requests.codes.created):
        campaign_url = r.headers['location']
        print 'SUCCESS: Campaign header data uploaded:', campaign_url
    else:
        print 'FAILED: Server returned', r.status_code
        return False

    #POST deployment/s

    directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

    for directory in directories:
        print 'SENDING: Deployment info for', directory
        if not post_deployment_to_server(os.path.join(root_import_path, directory), server_root, user_name, api_key, urlparse.urlsplit(campaign_url).path):
            return False

    return True


def post_deployment_to_server(deployment_path, server_root, username, user_apikey, campaign_url):
    """Iterates through campaign directory POSTing data/imagery to the API at a specified Catami server
    """

    deployment_api_path = '/api/dev/generic_deployment/'
    image_metadata_api_path = '/api/dev/generic_image/'
    camera_api_path = '/api/dev/generic_camera/'
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

    # image_object_api_path returns 500 right now
    # if not check_url(server_root, image_object_api_path):
    #     problem_count += 1
    #     print 'FAILED: API unavailable at', image_object_api_path

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
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print r.text
        return False

    # POST images for deployment

    # first post the camera for the images
    camera_data = get_camera_data(deployment_path)
    if camera_data is None:
        print 'FAILED: Could not get camera data for deployment'
        return False

    print 'SENDING: Camera info...'
    url = urlparse.urljoin(server_root, camera_api_path)
    headers = {'Content-type': 'application/json'}
    r = requests.post(url, data=json.dumps(camera_data), headers=headers, params=params)
    if (r.status_code == requests.codes.created):
        camera_url = r.headers['location']
        print 'SUCCESS: Camera data uploaded:', urlparse.urlsplit(camera_url).path
    else:
        print 'FAILED: Server returned', r.status_code
        print 'MESSAGE: Full message from server follows:'
        print r.text
        return False

    image_data = read_images_file(deployment_path)

    #main image posting loop. 

    for index, current_image in enumerate(image_data):
        # if the image has no lat/long we skip it here
        if str(current_image['latitude']).lower() == 'None'.lower() or str(current_image['longitude']).lower() == 'None'.lower():
            print 'MESSAGE: Skipping [', index, '/', len(image_data), ']', current_image['image_name'], 'No geolocation'
            continue

        print 'MESSAGE: Uploading [', index, '/', len(image_data), ']', current_image['image_name']

        # STEP 1: post the measurement data

        measurement_data = dict(temperature=current_image['temperature'],
                                salinity=current_image['salinity'],
                                pitch=current_image['pitch'],
                                roll=current_image['roll'],
                                yaw=current_image['yaw'],
                                altitude=current_image['altitude'])

        print 'SENDING: Measurement for', current_image['image_name']
        url = urlparse.urljoin(server_root, measurement_api_path)
        headers = {'Content-type': 'application/json'}
        r = requests.post(url, data=json.dumps(measurement_data), headers=headers, params=params)
        if (r.status_code == requests.codes.created):
            measurement_url = r.headers['location']
            print 'SUCCESS: Measurement data uploaded:', urlparse.urlsplit(measurement_url).path
        else:
            print 'FAILED: Server returned', r.status_code
            print 'MESSAGE: Full message from server (if any) follows:'
            print r.text
            return False

        # STEP 2 post the image metadata
        image_metadata = dict(measurements=urlparse.urlsplit(measurement_url).path,
                              camera=urlparse.urlsplit(camera_url).path,
                              web_location='',
                              archive_location='None',
                              deployment=urlparse.urlsplit(deployment_url).path,
                              date_time=current_image['time'],
                              position='SRID=4326;POINT('+current_image['longitude']+' '+current_image['latitude']+')',
                              depth=image_data[3]['depth'])
        print 'SENDING: Image metadata for', current_image['image_name']
        url = urlparse.urljoin(server_root, image_metadata_api_path)
        headers = {'Content-type': 'application/json'}
        r = requests.post(url, data=json.dumps(image_metadata), headers=headers, params=params)
        if (r.status_code == requests.codes.created):
            image_metadata_url = r.headers['location']
            print 'SUCCESS: Image metadata uploaded:', urlparse.urlsplit(image_metadata_url).path
        else:
            print 'FAILED: Server returned', r.status_code
            print 'MESSAGE: Full message from server follows:'
            print r.text
            return False

        # STEP 3 finally post the actual image

        print 'SENDING: Image object;', current_image['image_name']
        url = urlparse.urljoin(server_root, image_object_api_path)
        headers = {'Content-type': 'application/json'}
        image_file = {'file': open(current_image['image_name'], 'rb')}

        r = requests.post(url, file=image_file)
        if (r.status_code == requests.codes.created):
            print 'SUCCESS: Image uploaded:', image_file
        else:
            print 'FAILED: Server returned', r.status_code
            print 'MESSAGE: Full message from server follows:'
            print r.text
            return False

    return True


def main():
    """main routine
    """
    print 'MESSAGE: Checking', root_import_path
    problem_found = False

    #  basic checks, does the dir exist? is the server live?
    if not basic_import_checks(root_import_path, server_root):
        print 'ERROR: Required files and/or resources are missing. Validation stopping right here. Fix errors and try again'
        sys.exit(1)

    # if we are still going then all required files exist. Yay us!
    campaign_status = check_campaign(root_import_path)

    directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

    for directory in directories:
        deployment_status = check_deployment(os.path.join(root_import_path, directory))
        deployment_status = check_deployment_images(os.path.join(root_import_path, directory))

    print 'SUCCESS: All checks are done, campaign is ready to upload'

    # username = 'pooper'
    # user_apikey = 'e688869735a817b60ae701d4d2c713ec9de67d67'
    if post_campaign_to_server(root_import_path, server_root, username, apikey):
        print 'SUCCESS: Everything went just great!'
    else:
        print 'ERROR: Everything did not go just great :('


if __name__ == "__main__":
    main()
