# File Downloader and Metadata Extractor

## File Downloader

The primary script, `downloader.py`, is designed for downloading files from URLs and logging metadata about each download in an SQLite database. It uses **Peewee** for database interactions and **ExifTool** for metadata extraction.

### Key Features:

- **Database Logging**: Each download is logged in an SQLite database. The database includes fields like the original URL, resolved URL, filename, MIME type, and more.
- **Metadata Extraction**: Uses **ExifTool** to extract metadata such as file size, MIME type, and MD5 hash from the downloaded files.
- **File Renaming**: Allows renaming of files based on the URL, request headers, or a custom name.
- **Error Handling**: Handles HTTP errors, connection errors, and invalid URLs.

### Requirements:

- **Python 3.x**
- **Peewee ORM**: Used for SQLite database interactions.
- **ExifTool**: Used for metadata extraction. Install from [ExifTool](https://exiftool.org/).
- **Python Libraries**:
  - `requests`
  - `peewee`
  - `pyexiftool`

### Installation

1. Download [exiftools](https://exiftool.org/install.html)
2. Add to path in environmental variables. (sysdm.cpl -->advanced-->environmental variables--> path)
3. Install PyExifTools.
   ```
   pip install pyexiftool

   ```
4. Add your link to download and folder where to download as in the example and run :
   
   ```
   def main():
    # Example URL of a file to download
    url = "https://example.com/image.jpg"  # Replace with the actual URL of the file
    save_directory = r"C:\Users\YourUsername\Downloads"
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
    
    # Step 1: Download the file
    downloaded_file = download_file(url, save_directory)
    # Step 2: Extrac metadata with Exiftool
    if downloaded_file:
        extract_metadata(downloaded_file)

   if __name__ == "__main__":
    main()
   ```

### Encoding problem
   
If you get an error related with encoding you can open exiftool.py file from python/site-packages/exiftool folder and change the following line:
![exiftool error and solution](exiftoolfile.png)

 
## Light Modified Downloader

The `downloader_light_modified.py` script is a streamlined version of the main downloader. It focuses on essential functionality, with a few key differences:

### Key Differences from the Main Downloader:

1. **No Database Logging**: Unlike the main script, this version does not log download details into a database. It simply downloads the files and extracts metadata without writing to any external storage.

2. **Simplified Metadata Extraction**: Metadata extraction via **ExifTool** is retained, but without additional operations like saving metadata in a database.

3. **Faster Execution**: Since there is no database interaction, the script executes faster, making it ideal for use cases where only the file and basic metadata are required.

4. **Renaming Functionality**: The ability to rename files based on headers or URL is still available, but without updating records in a database.

5. **Focused on Basic Downloads**: It is intended for simpler use cases where the overhead of database operations is unnecessary. You can download files, extract basic metadata, and optionally rename the files.

### When to Use:

- [Podasts](https://github.com/nlnzcollservices/podcast-collector)
