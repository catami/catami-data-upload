# Catami Data Uploader

A set of stand-alone tools to cdonvert, upload and/or validate data in the Catami data package format to a specified Catami server.

The variable nature of historical data means that Catami data conversion routines are created on a case-by-case basis. 

catami-upload.py is the validation and upload tool for Catami data.

## Converting a deployment or campaign to Catami format

Before you try to validate or upload Catami data you need to get your data under control.  Catami has a simple, human readable
data format, documented at https://github.com/catami/catami/wiki/Data-importing

### Current conversion routines:
#### aims_ti_converter.py
Converts AIMS Towed Imagery that uses a root level XLSX (Excel) file for imagery geolocation. Imagery is organised
by transect with a directory for each transect. The conversion routine makes each transect into a Catami Deployment for
import and adds a campaign.txt at the root level for Catami Campaign Import

Example usage:

    python aims_ti_converter.py --path /Volumes/STORE_MAC/data/NingalooMar12/
	
Alternately you can convert a single directory to a Catami Deployment, though the script still expects to find the root XLSX file

    python aims_ti_converter.py --deployment --path /Volumes/STORE_MAC/data/NingalooMar12/Muirons1

#### kayak_converter.py
Converts Kayak collected imagery into Catami format.  Multiple directories within a root directory can be converted to the
Catami Campaign/Deployment format, alternately a specified directory of images can be converted to a deployment for import to 
a pre-existing campaign. Geolocation data is taken from the EXIF Geolocation data in the images.  You can specify depth (if no
depth soundings are available) with a single estimate with the --depth flag.

Example usage:

    python kayak_converter.py --path /Volumes/STORE_MAC/data/kayakdata_2012/ --depth 2.0

Alternately you can convert a single directory to a Catami Deployment

    python kayak_converter.py --deployment --path /Volumes/STORE_MAC/data/kayakdata_2012/leg01 --depth 2.0

## Validating and uploading deployment or campaign to a Catami server

catami_upload.py is provided to validate and upload campaigns and deployments to specified Catami servers.  This tool
validates a campaign or deployment and, if validation is successful, uploads the campaign/deployment to a specified
Catami server.

Authentication is required for uploading data to a Catami server and uses your account name and an API key available
from the Catami admin interface.

Example usage:

to up load a campaign and all deployments within

    python catami_upload.py  --campaign /Volumes/STORE_MAC/data/TurquoiseBay_20130516 --server http://localhost:8000 --username user --apikey e688869735a817bf890d701d4d2c713ec9de67d67

to upload a deployment to an existing campaign

    python catami_upload.py  --deployment /Volumes/STORE_MAC/data/TurquoiseBay_20130516/run01 --server http://localhost:8000 --username user --apikey e688869735a817bf890d701d4d2c713ec9de67d67 --campaign_api /api/dev/campaign/92

## Validating a deployment or campaign

