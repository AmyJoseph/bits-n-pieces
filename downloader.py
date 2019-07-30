#! /usr/bin/env python3

import requests
import os
import logging

logging.basicConfig(level=logging.INFO)

def download_pub(url_to_download, download_folder):

	'''Attempts to download file at a given URL.

	Parameters: 
		url_to_download (str): URL of file to download.
		download_folder(str): folder where the file should be saved

		Starts by checking whether the given URL redirects to the "true" URL (e.g. for link-shortener URLS like bit.ly).

	Once it has resolved to the final URL, it parses the URL to find the filename.
	It then checks to see whether a file of that name already exists in the download folder, and finishes by logging a warning if it does.

	If the file doesn't already exist, it requests the URL and checks and logs the response code. 
	If not a 4xx or 5xx error, it checks the file type in the URL headers and logs a warning if it is just a webpage.

	If it is not just a webpage, it downloads the file.
	
	It then checks to see whether the downloaded file is a valid PDF. 	
		*** #TODO: build in checks for other file types! ***
	'''

	logging.info("Attempting download: {}".format(url_to_download))

	# check if the URL redirects
	session = requests.Session()
	try:
		resp = session.head(url_to_download, allow_redirects=True)
		resolved_url = resp.url

		if resolved_url != url_to_download:
			logging.info("Resolves to {}".format(resolved_url))

		# create full filename from url
		fname = os.path.split(resolved_url)[-1]

		# get rid of any url characters after file extension 	
		#TODO: at the moment, this is just checking for existance of '?' in URL after file extension
		if "." in fname:
			name,extn = fname.split(".")
			if "?" in extn:
				extn = extn.split("?")[0]
				fname = ("{}.{}").format(name,extn)

		logging.info("File to download: {}".format(fname))
		
		file_path = os.path.join(download_folder, fname)

		# check that file does not already exist in folder
		if not os.path.exists(file_path):
		# download the file, or log error if file doesn't exist at URL
			r = requests.get(resolved_url)
			logging.info("Status code: {}".format(r.status_code))
			# if r.status_code == 404:
			# 	logging.warning("404 error")
			# elif r.status_code == 503:
			# 	logging.warning("page unavailable")

			if not r.ok:
				logging.warning("{} error".format(r.status_code))

			else:
				# check that you are not attempting to download a webpage
				if "html" in r.headers['Content-Type']:
					logging.warning("Download target is just a webpage")
				else:
					# write file to folder
					with open(file_path, 'wb') as f:
						for chunk in r.iter_content(100000):
							f.write(chunk)

					logging.info("Wrote {}".format(fname))
					
					# check that the thing that was downloaded is a valid PDF by looking for the PDF BOF marker in the binary
					# TODO: currently this is only useful for PDFs!
					with open(file_path, 'rb') as f:
						binary_string = f.read()
					if binary_string[:4] != b"%PDF":
						logging.warning("{} is not a valid PDF".format(fname))
		else:
			logging.warning("Already downloaded {}".format(fname))

	except requests.exceptions.RequestException as e:
		logging.warning("Failed with error: {}". format(e))

