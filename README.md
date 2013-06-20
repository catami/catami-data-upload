Catami Data Uploader
====================

A set of stand-alone tools to cdonvert, upload and/or validate data in the Catami data package format to a specified Catami server.

The variable nature of historical data means that Catami data conversion routines are created on a case-by-case basis. 

catami-upload.py is the validation and upload tool for Catami data.

Converting a deployment or campaign to Catami format
----------------------------------------------------

Before you try to validate or upload Catami data you need to get your data under control.  Catami has a simple, human readable
data format, documented at https://github.com/catami/catami/wiki/Data-importing

Current conversion routines:
* aims_ti_converter.py
Converts AIMS Towed Imagery that uses a root level XLSX (Excel) file for imagery geolocation. Imagery is organised
by transect with a directory for each transect. The conversion routine makes each transect into a Catami Deployment for
import and adds a campaign.txt at the root level for Catami Campaign Import
	ie: > python aims_ti_converter.py --path /Volumes/STORE_MAC/data/NingalooMar12/
	
Alternately you can convert a single directory to a Catami Deployment, though the script still expects to find the root XLSX file
	ie: > python aims_ti_converter.py --deployment --path /Volumes/STORE_MAC/data/NingalooMar12/Muirons1
	
Validating a deployment or campaign
-----------------------------------

Example usage:
python catami_upload.py  --path /Volumes/Store/data/TurquoiseBay_20130516/  --server sandbox.catami.org

Validating and uploading deployment or campaign to a Catami server
------------------------------------------------------------------