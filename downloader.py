#! /usr/bin/env python3

"""
Module to assist with downloading resources from URLs.
NB: When reading the help documentation, you may find it easiest to skip over the whole "class Resources(peewee.Model)" section and pick it back up again at FUNCTIONS.

Main code is a class called "DownloadResource", which attempts to download the resource at a given URL, and also writes an entry to a database about the resource.
Assigns filenames by minting a UUID, but also returns original filenames as parsed from headers and/or URL.

Function "download_file_from_url" runs a single URL through Download Resource, downloads the resource and downloads the new database ID for it.

Function "download_from_list" takes a list, tuple or set of URLs and passes each one to DownloadResource - downloads the resources and returns a list of dictionaries with each original url and its new database ID.

You may wish to first run "start_database" if you want to provide a path for your database, and/or to reset the database before downloading anything (eg for testing).

Function "change_filename" can be run after a resource is downloaded and a DownloadObject has been created. You can use this to change the UUID filename to an alternative of your choosing, including the filename_from_headers or filename_from_url.

"""

from datetime import datetime
import exiftool # req
import hashlib
import logging
import ntpath
import os
import peewee
import re
import requests # req
import time
from urllib.parse import urlparse, urlunparse
import uuid

logging.basicConfig(level=logging.INFO)
# defer initialisation of the db until the path is given by user
# see http://docs.peewee-orm.com/en/latest/peewee/database.html#run-time-database-configuration
database = peewee.SqliteDatabase(None)

class Resources(peewee.Model):
	"""Creates the table for the database
	"""

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

class DownloadResource:
	"""Attempts to download the resource at a given URL, and also writes attributes about the resource to a database.
	...

	Database fields
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

		datetime : datetime object
			The time the resource was requested from url_final

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

	def __init__(self, url, directory, collect_html, proxies):
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
		self.url_final = None
				
		# creates an entry in the Resources table and returns it as "self.record"
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
			self.record.url_resolved = response.url
			
#***	EXPERIMENTAL: clean any parameter, query or fragment attributes from end of URL. IS THIS GOING TO MAKE ANYTHING FALL OVER?!
			url_parsed = urlparse(response.url)
			# replace any parameters, queries or fragments with empty strings in order to rebuild the URL without them
			path_url_tuple = url_parsed[:3] + ("","","")
			self.url_final = urlunparse(path_url_tuple)
			self.record.url_final = urlunparse(path_url_tuple)
		
			# get the thing, recording the time
			self.record.datetime = datetime.now()
			
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

					# get rid of some of the fields written to the db as now longer relevent
					self.record.directory, self.record.filename, self.record.filepath = None, None, None
					self.record.download_status = self.download_status
					self.record.message = self.message
					self.record.save()					
					return

		if 'ExifTool:Error' in metadata:
			if self.message == None:
				self.message = "Unknown filetype"
			else:
				self.message = f"{message} ; Unknown filetype"

			self.record.message = self.message
			
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

		hash_md5 = hashlib.md5()
		with open(self.filepath, "rb") as f:
			for chunk in iter(lambda: f.read(4096), b""):
				hash_md5.update(chunk)
		self.record.md5 = hash_md5.hexdigest()

		self.record.save()

	def add_file_extension(self):
		"""Adds correct file extension as found by EXIFtool to filename 
		"""
		if self.filetype_extension != None:
			new_filepath = os.path.join(self.directory, self.filename + os.extsep + self.filetype_extension.lower())
			os.rename(self.filepath, new_filepath)
			self.record.filepath = new_filepath
			self.record.filename = str(ntpath.basename(self.filepath))

			self.record.save()

def download_from_list(urls, directory="content", collect_html=False, proxies=None):
	"""Run DownloadResource over a list of URLs, downloading resources and returning a list of dictionaries of URLs and their database IDs.
	If you haven't already started a database it will use the default behaviour of using "files_from_urls.db" in current directory as the database, and adding new files if that db already exists, not resetting it.
	...
	Parameters
	----------
	urls : data structure (list, tuple, or set) 
		Contains the URLs of resources to be downloaded
	directory : str, optional. Defaults to /content.
		Location of destination directory
	collect_html : bool, optional
		Set to True if desired behaviour is to download resource if it is just an HTML page. Default is False: download attempt will fail with error message "Target was webpage - deleted"
	proxies : dict, optional
		Pass a proxies dictionary if it will be required for requests.
	"""
	resources_list = []
	for url in urls:
		try:
			resource = DownloadResource(url, directory, collect_html, proxies)
		# start the default database if user hasn't already started one
		except peewee.InterfaceError:
			logging.warning("No database started - will add download to default database 'files_from_urls.db'. You can change this behaviour by calling 'downloader.start_database'.")
			start_database()
			resource = DownloadResource(url, directory, collect_html, proxies)
		# make dictionary of original url and id to return
		resource_dict = {
		'url_original' : resource.record.url_original,
		'id' : resource.record.id}
		resources_list.append(resource_dict)
	return resources_lisT

def change_filename(self, rename_from_headers=False, rename_from_url=False, new_filename=None):
	# TODO REPLACE THIS
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

def start_database(database_path="files_from_urls.db", reset_db=False):
	"""Starts tbe database to be used by DownloadResource.
	...
	Parameters
	----------
	database_path : str, optional
		Desired name of database. Can be a path or just a filename. If just a filename, db will be created in the current directory. If none given, defaults to "files_from_urls.db" in current directory.
	reset_db : bool, optional
		set to True if you want to use the name of a database that may already exist and you want to overwrite it. Mainly for testing purposes. Default is 'False', so using the name of an existing db will add new entries to the existing db.	
	"""	
	# if reset_db = True then any existing db of that name will be deleted
	if os.path.exists(database_path):
		if reset_db == True:
			os.remove(database_path)
			logging.warning(f"'{database_path}' existed - has been reset")
		else:
			logging.info (f"Downloader will add your new files to existing database '{database_path}'")

	# created desired directory location for db if it doesn't already exist
	database_directory = os.path.split(database_path)[0]
	if not database_directory == "":
		if not os.path.exists(database_directory):
			os.makedirs(database_directory)

	# initialise db and make the Resources table
	database.init(database_path)
	try:
		Resources.create_table()
	except peewee.OperationalError:
		print("This table already exists!")

def download_file_from_url(url, directory="content", collect_html=False, proxies=None):
	"""Run DownloadResource on a single URL, downloading the resource and returning its newly-minted database ID.
	If you haven't already started a database it will use the default behaviour of using "files_from_urls.db" in current directory as the database, and adding new files if that db already exists, not resetting it.
	...
	Parameters
	----------
	url : str 
		URLs of the resource to be downloaded
	directory : str, optional.
		Location of destination directory. Defaults to '/content'.
	collect_html : bool, optional
		Set to True if desired behaviour is to download resource if it is just an HTML page. Default is False: download attempt will fail with error message "Target was webpage - deleted"
	proxies : dict, optional
		Pass a proxies dictionary if it will be required for requests.
	"""

	try:
		target_resource = DownloadResource(url, directory, collect_html, proxies)
	# start the default database if user hasn't already started one
	except peewee.InterfaceError:
		logging.warning("No database started - will add download to default database 'files_from_urls.db'. You can change this behaviour by calling 'downloader.start_database'.")
		start_database()
	target_resource = DownloadResource(url, directory, collect_html, proxies)
	# return the new database id for the resource
	return target_resource.record.id