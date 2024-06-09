# Avata 2 Merge Flights
Python script that processes segmented DJI Avata 2 drone videos to determine which files belong to the same flight, merges them, and manages file organization based on user-defined parameters.

## Features

- **Automatic Flight Detection**: Groups video files into flights based on timestamps within filenames and the video duration.
- **Video Merging**: Uses an external tool to merge videos that are detected as part of the same flight.
- **Customizable Output**: Prompts the user for an output directory name and constructs directories based on the earliest date found in file names.
- **Size Validation and Cleanup**: Checks merged file sizes against the sum of the input files. Deletes source files if the size difference is within a 0.1% threshold. This is to avoid deleting input files if due to full hard disc mp4-merge silently fails and outputs a half finished output video.
- **Error Handling**: Provides detailed error messages and skips deletion if file sizes do not match closely enough.

## Set Up

1. Make sure you have [Python 3.x](https://www.python.org/downloads/windows/) installed. 
2. Download mp4-merge tool from here: [https://github.com/gyroflow/mp4-merge](https://github.com/gyroflow/mp4-merge/releases)
3. Install [MoviePy](https://zulko.github.io/moviepy/) by opening command prompt and typing: pip install moviepy
4. Modify the `OUTPUT_BASE_PATH` and `MP4_MERGE_PATH` in the script to point to your desired output directory and the location of mp4-merge tool, respectively.

## Usage

Select all your video files straight from the SD card and drag and drop them onto the script.

![Example output.](https://i.imgur.com/8COUGs3.png "example output of Avata 2 Merge Flights script")


