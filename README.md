 ! - Please don't use this script before reading the last "warning" paragraph, or you risk a small chance of having your video messed up. - !

# Avata 2 Merge Flights
Python script that processes segmented DJI Avata 2 drone videos to determine which files belong to the same flight, merges them, verifies the results, and deletes the source files only after showing you the evidence and asking for confirmation.

## Features

- **Automatic Flight Detection**: Groups video files into flights based on timestamps within filenames and the video duration.
- **Video Merging**: Uses an external tool (mp4_merge) to merge videos that are detected as part of the same flight.
- **SRT Merging**: If .SRT files are detected next to videos, they will be merged and copied over as well (timestamps and frame counts within will be adjusted appropriately). If a clip is missing its SRT, the merged SRT compensates the timestamps of later clips so telemetry stays in sync with the video.
- **Verification Before Deletion**: Each merge is verified on three fronts: mp4_merge must exit cleanly, the merged file size must match the sum of the input files within 0.1% (this catches e.g. mp4_merge silently failing on a full disk and writing a half-finished video), and the merged video duration must match the sum of the clip durations within 2 seconds.
- **Confirmation Dialog**: Nothing is deleted automatically anymore. After all flights are merged, a dialog lists every flight with the exact evidence for why deleting its source files is considered safe (or why they will be kept). You can watch the merged videos first — sources are only deleted after you explicitly confirm. Closing the dialog keeps everything.
- **Logging**: Every run writes a full log to `OUTPUT_BASE_PATH/logs/` — the exact files received, flight grouping decisions with time gaps, mp4_merge output, all verification math, and every deletion. If anything ever looks off, the log shows exactly what happened.
- **Extra Safety Guards**: Files are re-checked immediately before deletion (anything that changed or disappeared while you were reviewing is kept), existing output files are never overwritten, and duplicate input files are detected and ignored.

## Set Up

1. Make sure you have [Python 3.x](https://www.python.org/downloads/windows/) installed. 
2. Download mp4-merge tool from here: [https://github.com/gyroflow/mp4-merge](https://github.com/gyroflow/mp4-merge/releases)
3. Install [MoviePy](https://zulko.github.io/moviepy/) by opening command prompt and typing: pip install moviepy
4. Modify the `OUTPUT_BASE_PATH` and `MP4_MERGE_PATH` in the script to point to your desired output directory and the location of mp4-merge tool, respectively.

## Usage

Select all your video files straight from the SD card and drag and drop them onto the script.

![Example output.](https://i.imgur.com/8COUGs3.png "example output of Avata 2 Merge Flights script")

After merging, review the merged videos, then confirm (or decline) the deletion of the source files in the dialog that pops up.

## Warning!

As of August 4 2024, Avata 2 still has the date time bug, where it will tag files with wrong date time in both filestamp and file metadata. This usually just means that output folder will have the wrong date in its name, and sometimes flights will be in wrong order, but on rare occasions it's possible for Avata to fuck up so badly that it manages to trip up the script flight detection feature. While this feature could be made more robust to doublecheck against index numbers at the end of filenames, I'm hoping DJI will actually fix this bug as it's a pretty huge bug experienced by many, if not most users, so I'm not going to invest time into implementing workarounds until I'm conviced they've dropped the ball. Here is an example of script being tripped up by an especially faulty timestamp, so please doublecheck the output of the auto flight detection before starting the merge to avoid having your flights messed up!

![Example error.](https://i.imgur.com/sbCbQkn.png "example faulty flight autodetect due to Avata date time bug")

In this example files with index _21 and _22 should on their own make up the 5th flight.

The only way to workaround this DJI bug on your own seems to be to connect headset to your phone's DJI Fly app before every single flight.
