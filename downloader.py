#! /usr/bin/env python3

"""
Module to assist with downloading resources from URLs.

Main code is a class called "DownloadResource", which attempts to download the resource at a given URL, and also returns attributes about the resource.
Assigns filenames by minting a UUID, but also returns original filenames as parsed from headers and/or URL.

Function "download_from_list" takes a list, tuple or set of URLs and passes each one to DownloadResource - will therefore download the resources and return a list with a DownloadResource object from each URL in the original list.

Function "change_filename" can be run after a resource is downloaded and a DownloadObject has been created. You can use this to change the UUID filename to an alternative of your choosing, including the filename_from_headers or filename_from_url.

"""

from datetime import datetime
# from downloader_db import Resources
import exiftool # req
import hashlib
import logging
import ntpath
import os
import peewee
from pprint import pprint
import re
import requests # req
import time
from urllib.parse import urlparse, urlunparse
import uuid

logging.basicConfig(level=logging.INFO)

database_path = 'test_db.db'
# turn on for testing - will delete the db at the start of each run
if os.path.exists(database_path):
	os.remove(database_path)
database = peewee.SqliteDatabase(database_path)

class Resources(peewee.Model):
	download_status = peewee.BooleanField(null = True, default = None)
	message = peewee.CharField(max_length = 300, null = True, default = None)
	directory = peewee.CharField(max_length = 200, null = True, default = None)
	url_original = peewee.CharField(max_length = 300)
	url_resolved = peewee.CharField(max_length = 300, null = True, default = None)
	url_final = peewee.CharField(max_length = 300, null = True, default = None)
	datetime = peewee.DateTimeField(null=True, default=None)
	filename = peewee.CharField(max_length = 100, null=True, default=None)
	filepath = peewee.CharField(max_length = 300, null=True, default=None)
	filename_from_url = peewee.CharField(max_length = 100, null=True, default=None)
	filename_from_headers = peewee.CharField(max_length = 100, null=True, default=None)
	filetype_extension = peewee.CharField(max_length=25, null=True, default=None)
	mimetype = peewee.CharField(max_length=40, null=True, default=None)
	md5 = peewee.CharField(max_length=40, null=True, default=None)

	class Meta:
		database = database

try:
	Resources.create_table()
except peewee.OperationalError:
	print("This table already exists!")

class DownloadResource:
	"""Attempts to download the resource at a given URL, and also returns attributes about the resource and saves everything to a database.
	...

	Attributes
	----------
		download_status : bool
			True if resource successfully downloaded, else False
		message : str
			Gives more detailed information about the success or failure of the download attempt, including errors

		url_original : str
			The URL passed to the class
		url_resolved : str
			The URL after any redirects have been resolved
		url_final : str
			The final URL that will be downloaded. Has been cleaned of any parameters, queries or fragments after URL path

		filename : str
			Filename of the downloaded file
		filepath : str
			Filepath of downloaded file
		filename_from_url : str
			Filename from the part of the final resolved, cleaned URL after the last "\"
		filename_from_headers : str
			Filename from 'Content-Disposition' in URL headers if exists, else None
		filetype_extension : str
			Extension of downloaded file (from EXIFtool)
		mimetype : str
			MIMEtype of downloaded file (from EXIFtool)
		md5 : str
			md5 hash of downloaded file

	METHODS
	-------
	
	get_real_download_url
	get_original_filename_from_url
	get_original_filename_from_request_headers
	download_file
	get_file_metadata
	add_file_extension

	Can be run after creation of object to change filename to user preference:
	change_filename
		
	"""

	def __init__(self, url, directory="content", collect_html=False, proxies=None):
		"""
		Parameters
		----------
		url : str
			URL of reseource to be downloaded
		directory : str, optional
			Location of destination directory. Default is a directory called "content" in the current directory
		collect_html : bool, optional
			Set to True if desired behaviour is to download resource if it is just an HTML page. Default is False: download attempt will fail with error message "Target was webpage - deleted"
		proxies : dict, optional
			Pass a proxies dictionary if it will be required for requests.
		"""

		self.download_status = None
		self.message = None
		self.directory = directory
		self.collect_html = collect_html
		self.proxies = proxies
		self.url_original = url
		self.url_resolved = None
		self.url_final = None
				
		# creates an entry in the Resources table and returns it as "self.id"
		self.record = Resources.create(url_original = self.url_original)

		self.get_real_download_url()

		# continue if no error with requesting URL
		if self.download_status != False:

			self.get_original_filename_from_url()
			self.get_original_filename_from_request_headers()
			self.download_file()
			self.get_file_metadata()

		# check file extension is correct if file downloaded and not deleted by collect_html flag setting
		if self.download_status == True:
			self.add_file_extension()

			pprint (self.record.__dict__['__data__'])

		# log outcome
			if self.mimetype == None:
				logging.warning(f"{self.url_original}: Downloaded unknown file type.\nFinal URL: {self.url_final}.\n{self.filename}")
			else:
				logging.info(f"{self.url_original}: Downloaded {self.mimetype}.\nFinal URL: {self.url_final}.\n{self.filename}")
			if self.message is not None:
				logging.info(self.message)

		elif self.download_status == False:
			logging.warning(f"{self.url_original}: Failed.")
			if self.url_final != None:
				logging.warning(f"Final URL: {self.url_final}.")
			logging.warning(self.message)
		# this is here in case something somehow makes it through without changing download_status to True or False
		else:
			logging.warning(f"{self.url_original} NO STATUS SET.")
			
		# clean up
		if hasattr(self, "r"):
			del self.r
		del self.collect_html
		del self.proxies

		time.sleep(.5)

# ***METHODS***

	def get_real_download_url(self):
		"""Cleans any spaces and trailing slashes from the given URL, resolves any redirects and removes any parameters, queries or fragments from end of URL to find final URL to request resource from. Logs error if unable to retrieve URL.
		"""

		url_stripped = self.url_original.strip().rstrip("/")
		# check if the URL redirects
		session = requests.Session()
		try:
			response = session.head(url_stripped, allow_redirects=True, proxies=self.proxies)
			self.url_resolved = response.url
			
#***		# EXPERIMENTAL: clean any parameter, query or fragment attributes from end of URL
			# IS THIS GOING TO MAKE ANYTHING FALL OVER?!
			url_parsed = urlparse(self.url_resolved)
			# replace any parameters, queries or fragments with empty strings in order to rebuild the URL without them
			path_url_tuple = url_parsed[:3] + ("","","")
			self.url_final = urlunparse(path_url_tuple)

			self.record.url_resolved = self.url_resolved
			self.record.url_final = self.url_final
			self.record.save()


			# get the thing, recording the time
			self.record.datetime = datetime.now()
			self.record.save()

			self.r = requests.get(self.url_final, timeout=(5,14), proxies=self.proxies)
			self.r.raise_for_status()
		except requests.exceptions.HTTPError as e:
			self.download_status = False
			self.message = f"HTTPError: {self.r.status_code}"
		except requests.exceptions.ConnectionError as e:
			print (e)
			self.download_status = False
			self.message = f"Connection failed"
		except requests.exceptions.RequestException as e:
			self.download_status = False
			self.message = f"RequestException: {e}"

		self.record.download_status = self.download_status
		self.record.message = self.message
		self.record.save()

	def get_original_filename_from_url(self):
		"""grabs the bit of the url after the last "/"
		"""
		self.record.filename_from_url = os.path.split(self.url_final)[-1]
		self.record.save()

	def get_original_filename_from_request_headers(self):
		"""Uses a regex to find the filename in URL headers['Content-Disposition'] if it exists
		"""

#***		# THIS WILL NEED A LOT MORE ROBUST TESTING!
		if 'Content-Disposition' in self.r.headers:
			regex = '(?<=filename=")(.*)(?=")'
			m = re.search(regex, self.r.headers['Content-Disposition'])
			if m:
				self.record.filename_from_headers = m.group(1)
			else:
				self.message = "'Content-Disposition' exists in headers but failed to parse filename"
				self.record.message = self.message
			self.record.save()

	def download_file(self):
		"""Downloads the resource, minting a unique filename from a UUID and creating the destination directory first if necessary
		"""

		if not os.path.exists(self.directory): os.makedirs(self.directory)
		self.filename = str(uuid.uuid4())
		self.filepath = os.path.join(self.directory, self.filename)

		with open(self.filepath, 'wb') as f:
			for chunk in self.r.iter_content(100000):
				f.write(chunk)
		self.download_status = True

		self.record.download_status = self.download_status
		self.record.filename = self.filename
		self.record.directory = self.directory
		self.record.filepath = self.filepath
		self.record.save()

	def get_file_metadata(self):
		"""Uses EXIFtool to get file extension and MIMEtype, then gets md5 hash
		"""

#***	# TODO: put exiftool.exe somewhere where it doesn't need the full path
		with exiftool.ExifTool() as et:
			metadata = et.get_metadata(self.filepath)

		# if discarding html pages, this happens here
		if self.collect_html == False:
			if 'File:MIMEType' in metadata:
				if metadata['File:MIMEType'] == "text/html":
					os.remove(self.filepath)

					self.download_status = False
					self.message = "Target was webpage - deleted"

					self.record.directory, self.record.filename, self.record.filepath = None, None, None
					self.record.download_status = self.download_status
					self.record.message = self.message
					self.record.save()
					pprint (self.record.__dict__['__data__'])

					del self.directory
					del self.filename
					del self.filepath
					
					return

		if 'ExifTool:Error' in metadata:
			if self.message == None:
				self.message = "Unknown filetype"
			else:
				self.message = f"{message} ; Unknown filetype"

			self.record.message = self.message
			self.record.save()

		if 'File:FileTypeExtension' in metadata:
			self.filetype_extension = metadata['File:FileTypeExtension']
		else: 
			self.filetype_extension = None
		if 'File:MIMEType' in metadata:
			self.mimetype = metadata['File:MIMEType']
		else:
			self.mimetype = None

			self.record.filetype_extension = self.filetype_extension
			self.record.mimetype = self.mimetype
			self.record.save()

		hash_md5 = hashlib.md5()
		with open(self.filepath, "rb") as f:
			for chunk in iter(lambda: f.read(4096), b""):
				hash_md5.update(chunk)
		self.record.md5 = hash_md5.hexdigest()

	def add_file_extension(self):
		"""Adds correct file extension as found by EXIFtool to filename 
		"""
		if self.filetype_extension != None:
			new_filepath = os.path.join(self.directory, self.filename + os.extsep + self.filetype_extension.lower())
			os.rename(self.filepath, new_filepath)
			self.filepath = new_filepath
			self.filename = str(ntpath.basename(self.filepath))

			self.record.filepath = self.filepath
			self.record.filename = self.filename
			self.record.save()

def download_from_list(urls, destination_directory="content", collect_html=False):
	"""List comprehension to run DownloadResource over a list of URLs, downloading resources and returning a list of DownloadResource objects
	...
	Parameters
	----------
	urls : data structure (list, tuple, or set) 
		Contains the URLs of resources to be downloaded
	directory : str, optional. Defaults to /content.
		Location of destination directory
	collect_html : bool, optional
		Set to True if desired behaviour is to download resource if it is just an HTML page. Default is False: download attempt will fail with error message "Target was webpage - deleted"
	"""

	downloaded_urls = [DownloadResource(x, destination_directory, collect_html) for x in urls]
	return downloaded_urls


def change_filename(self, rename_from_headers=False, rename_from_url=False, new_filename=None):
	"""Run this method over an existing DownloadObject to change the filename to a string of your choosing.
	Requires a DownloadObject. All other parameters are optional; only one will be actioned, with priority in the order set out below.
	Will not rename to the same name as a file already present in the directory - will return with self.renamed = False.
	...
	Parameters
	----------
	self : an existing DownloadObject instance
	rename_from headers : bool, optional
		set to True if you want to give the file the same filename originally found in the resource header
	rename_from_url : bool, optional
		set to True if you want to give the file the same filename originally found in the URL
	new_filename : str, optional
		Pass any filename you like here (including extension)

	Attributes
	----------
	filename, filepath : str
		Set to new values if succsssful
	renamed : bool
		True if successful, else False. You could use this to retry with a different parameter if unsuccessful (eg if you set to use headers and there was no filename in the headers originally)
	"""

	if self.download_status == True:
		if rename_from_headers == True:
			new_filename = self.filename_from_headers
		elif rename_from_url == True:
			new_filename = self.filename_from_url

		if new_filename == None:
			logging.warning(f"Could not change filename of '{self.filename}' from {self.url_original}: no new filename provided")
			return
	
		new_filepath = os.path.join(self.directory, new_filename)
		if not os.path.exists(new_filepath):
			os.rename(self.filepath, new_filepath)
			logging.info(f"'{self.filepath}' successfully changed to {new_filename}'")
			self.filename = new_filename
			self.filepath = new_filepath
			self.renamed = True
		else:
			logging.warning(f"Could not change filename of '{self.filename}' from {self.url_original}: new name '{new_filename}' already exists in {download_dir}")
	else:
		logging.warning(f"Could not change filename from {self.url_original} - no file was downloaded")
	