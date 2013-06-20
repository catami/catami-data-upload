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

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

parser = argparse.ArgumentParser(description='Parse AUV Data to produce a valid Catami project.')
parser.add_argument('--path', nargs=1, help='Path to root AUV data directory')
parser.add_argument('--deployment', action='store_true', default=False, help='Convert the directory as a deployment, to be attached to an existing campaign')

args = parser.parse_args()
make_deployment = args.deployment
root_import_path = args.path[0]

print 'Looking in: ', root_import_path

if not os.path.isdir(root_import_path):
    raise Exception('This is not a valid path. Check the path to your kayak data.')

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


def convert_deployment(root_import_path, directory):
    """converts a given directory to a deployment
    """

    return True


def main():
    """Builds Catami format package for Kayak AIMS data
    """

    if make_deployment:
        convert_deployment(root_import_path, '')
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
            convert_deployment(root_import_path, directory)

    print '...All done'


if __name__ == "__main__":
        main()
