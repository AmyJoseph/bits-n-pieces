More testing to see whether trimming everything in URL after path ever breaks anything
Testing if Content-Disposition regex ever fails

check that the revised request requests "just work" without passing a proxy dict on the network.

Write up requirements including EXIFtool
Work out how to package / bundle w EXIFtool

Add something to check for hash clashes
Compare hashes in directory

Add database
add collection name and identifier (uuid)
add option to override filename #use at own risk!
add get metadata option
add datetime
	from whiteboard notes:
		for url in my_urls:
		md = get_url(url, get_md=True)
		my_log.append(md)
Log to Excel
