# File Downloader and Metadata Extractor

This tool is designed to download files from a given URL and extract metadata (like EXIF data) from the downloaded files using **ExifTool**. It supports various file formats, including images, PDFs, and more. The metadata is extracted using the `pyexiftool` Python wrapper for **ExifTool**.

## Features

- **File Downloading**: Downloads files from a specified URL to a local directory.
- **Metadata Extraction**: Extracts metadata from the downloaded file (e.g., EXIF data for images).
- **Error Handling**: Handles errors related to downloads and metadata extraction.
- **Cross-Platform**: Can be used on Windows, macOS, and Linux.

## Requirements

Make sure the following tools and libraries are installed:

- **Python 3.x**: [Download Python](https://www.python.org/downloads/)
- **ExifTool**: [Download ExifTool](https://exiftool.org/) (add to system's PATH)
- **Python Libraries**:
  - `requests` (for downloading files)
  - `pyexiftool` (for metadata extraction)

## Installation

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

## Encoding problem
   
If you get an error related with encoding you can open exiftool.py file from python/site-packages/exiftool folder and change the following line:
![exiftool error and solution](exiftoolfile.png)

 
