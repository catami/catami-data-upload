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
import httplib
import csv

from PIL import Image
# from PIL.ExifTags import TAGS, GPSTAGS

parser = argparse.ArgumentParser()
parser.add_argument('--path', nargs=1, help='Path to root Catami data directory for campaign, ie: /data/somthing/some_campaign')
parser.add_argument('--server', nargs=1, help='Catami server location for upload, ie: http://catami.org')

args = parser.parse_args()

root_import_path = args.path[0]
server_root = args.server[0]
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
            print 'MISSING: images.csv file is missing in', image_dir

        if not os.path.isfile(os.path.join(image_dir, description_filename)):
            everthing_is_fine = False
            print 'MISSING: description.txt file is missing in', image_dir

    return everthing_is_fine


def check_deployment_images(deployment_path):
    """Check deployment imagery for valid list and valid imagery
    """
    print 'Checking Deployment', images_filename, '...'
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
                camera_text = row[5]
                camera_text = row[6]
                salinity = row[7]
                pitch = row[8]
                roll = row[9]
                yaw = row[10]
                altitude = row[11]

                #image list validation
                #required
                if time_string is None or str(time_string) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'Time is required'
                    is_complete = False

                if latitude is None or str(latitude) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'latitude is required'
                    is_complete = False

                if longitude is None or str(longitude) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'longitude is required'
                    is_complete = False
                if depth is None or str(depth) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'depth is required'
                    is_complete = False
                if image_name is None or str(image_name) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'image_name is required'
                    is_complete = False
                if camera_text is None or str(camera_text) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'camera_text is required'
                    is_complete = False
                if camera_text is None or str(camera_text) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'camera_text is required'
                    is_complete = False

                #not required
                if salinity is None or str(salinity) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'salinity is missing'
                if pitch is None or str(pitch) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'pitch is missing'
                if roll is None or str(roll) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'roll is missing'
                if yaw is None or str(yaw) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'yaw is missing'
                if altitude is None or str(altitude) == 'None':
                    print 'MISSING -', images_filename, 'row:', row_index, 'altitude is missing'

                if not (image_name is None or str(image_name) == 'None'):
                    #lets check this image
                    if os.path.isfile(os.path.join(deployment_path, image_name)):
                        try:
                            Image.open(os.path.join(deployment_path, image_name))
                            good_image_count = good_image_count + 1
                        except:
                            bad_image_count = bad_image_count + 1
                            print 'ERROR -', image_name, ' appears to be an invalid image'
                    else:
                        print 'MISSING -', image_name, ' references in images.csv'
                        row_is_complete = False

                #let's decide what to do with this row
                if not row_is_complete:
                    is_complete = False

                if row_is_broken:
                    is_broken = True

            if bad_image_count > 0:
                print 'ERROR - ', bad_image_count, '(of', good_image_count, ') bad images were found'
                is_broken = True
            else:
                print 'SUCCESS - ', good_image_count, ' images checked'

            #did something important break?
            if is_broken:
                return False

            return is_complete


def check_deployment(deployment_path):
    """Check deployment for valid contents; description.txt, images.csv and the images themselves
    """
    print 'Checking', deployment_path

    if os.path.isfile(os.path.join(deployment_path, description_filename)):
        type_list = ['AUV', 'BRUV', 'TI', 'DOV', 'TV']
        # any missing **required** fields will make this false. spawns MISSING error. Fatal.
        is_complete = True

        # any missing data will make this false. spawns a warning.
        is_minally_ok = True

        # True if something wierd happens
        is_broken = False  # True if something wierd happens. Fatal

        version = ''
        type_text = ''
        description_text = ''
        f = open(os.path.join(deployment_path, description_filename))

        for line in f.readlines():
            split_string = line.rstrip().split(':')
            if split_string[0].lower() == 'Version'.lower():
                version = split_string[1].strip()
            elif split_string[0].lower() == 'Type'.lower():
                type_text = split_string[1].strip()
            elif split_string[0].lower() == 'Description'.lower():
                description_text = split_string[1]

        if version.replace(" ", "") != '1.0':
            print 'ERROR: Version must be 1.0'
            is_broken = True
        if len(type_text.replace(" ", "")) == 0:
            print 'MISSING -', description_filename, ': deployment type is required'
            is_complete = False
        if len(description_text.replace(" ", "")) == 0:
            print 'MISSING -', description_filename, ': deployment description is required'
            is_complete = False

        #check type
        if not type_text.upper() in type_list:
            print 'ERROR: Deployment type of', type_text, 'is not recognised. Must be one of', type_list
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
                print 'Unknown label', split_string[0]
                is_broken = True

        if version.replace(" ", "") != '1.0':
            print 'ERROR: Version must be 1.0'
            is_broken = True

        if len(name.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': campaign name is required'
            is_complete = False

        if len(description_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': description is required'
            is_complete = False

        if len(assoc_researchers_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': associated researchers is required'
            is_complete = False

        if len(assoc_publications_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': associated publications is required'
            is_complete = False

        if len(assoc_research_grants_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': associated research grants is required'
            is_complete = False

        if len(start_date_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': start date is required'
            is_complete = False

        if len(end_date_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': end date is required'
            is_complete = False

        if len(contact_person_text.replace(" ", "")) == 0:
            print 'MISSING -', campaign_filename, ': contact person is required'
            is_complete = False

        # check that end date is not before start date (TBD)
        # final summary
        if is_complete:
            print 'SUCCESS: campaign.txt is verified'
            return True
        else:
            print 'FAILED: campaign.txt is missing required fields. Verification failed. Check earlier messages.'
            return False

        if not is_complete and is_minally_ok:
            print 'SUCCESS: campaign.txt is missing optional fields. Review earlier messages.'
            return True

        if is_broken:
            print 'FAILED: campaign.txt appears to have some bad fields. Check earlier messages'
            return False


if __name__ == "__main__":

    print 'Checking: ', root_import_path
    problem_found = False

    #  basic checks, does the dir exist? is the server live?
    if not basic_import_checks(root_import_path, server_root):
        print 'STOP: Required files and/or resources are missing. Validation stopping right here. Fix errors and try again'
        sys.exit(1)

    # if we are still going then all required files exist. Yay us!
    campaign_status = check_campaign(root_import_path)

    directories = [o for o in os.listdir(root_import_path) if os.path.isdir(os.path.join(root_import_path, o)) and not o.startswith('.')]

    for directory in directories:
        deployment_status = check_deployment(os.path.join(root_import_path, directory))
        deployment_status = check_deployment_images(os.path.join(root_import_path, directory))

    print 'COMPLETE: All checks are done, campaign is ready to upload'
