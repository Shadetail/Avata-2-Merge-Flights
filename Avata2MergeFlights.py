import os
import sys
import subprocess
from datetime import datetime, timedelta
from tkinter import simpledialog, Tk, filedialog
from moviepy.editor import VideoFileClip

# Set the base output path and path to the video merging utility
OUTPUT_BASE_PATH = "C:\\Users\\Mario\\Downloads\\FPV"
MP4_MERGE_PATH = "D:\\portable_apps\\mp4_merge-windows64.exe"

def parse_filename(filename):
    """
    Extract the start time from the file name.
    Assumes file names are formatted like 'DJI_YYYYMMDDHHMMSS_XXXX_D.MP4'
    where 'YYYYMMDDHHMMSS' represents the timestamp of when the video was taken.
    """
    basename = os.path.basename(filename)
    date_str = basename[4:18]
    start_time = datetime.strptime(date_str, '%Y%m%d%H%M%S')
    return start_time

def get_video_duration(filename):
    """
    Extract the video duration using the moviepy library.
    Returns the duration as a timedelta object.
    """
    clip = VideoFileClip(filename)
    duration = timedelta(seconds=int(clip.duration))
    clip.close()
    return duration

def group_files(files):
    """
    Group files that belong to the same flight based on their timestamps.
    Files are considered part of the same flight if the start time of one file
    is within 10 seconds of the end time of the previous file in a sorted list.
    """
    flights = []
    current_flight = []
    last_end_time = None

    for file in sorted(files):
        start_time = parse_filename(file)
        duration = get_video_duration(file)
        if last_end_time is None or start_time <= last_end_time + timedelta(seconds=10):
            current_flight.append(file)
        else:
            flights.append(current_flight)
            current_flight = [file]
        last_end_time = start_time + duration

    if current_flight:
        flights.append(current_flight)

    return flights

def merge_videos(flights, output_folder, base_output_name):
    """
    Merge videos of each flight using an external merging utility.
    Deletes source files if the merged file size matches the input files size within a 0.1% margin.
    Adds detailed logging for successful merges, file deletions, and errors.
    """
    for i, flight in enumerate(flights, 1):
        output_file = os.path.join(output_folder, f"{base_output_name} {i}.mp4")
        command = [MP4_MERGE_PATH] + flight + ["--out", output_file]
        subprocess.run(command, shell=True)

        if os.path.exists(output_file):
            output_size = os.path.getsize(output_file)
            input_size = sum(os.path.getsize(f) for f in flight)
            size_difference = abs(input_size - output_size) / input_size
            if size_difference <= 0.001:
                for f in flight:
                    os.remove(f)
                    print("Deleted:", f)
            else:
                print(f"Files not deleted. Size mismatch: {size_difference:.2%} (threshold: 0.1%)")
        else:
            print("Error: Output file not found:", output_file)


def main(files):
    """
    Main function to process the files.
    Opens a dialog for output folder naming and manages the merging process.
    """
    if not files:
        print("No files provided. Exiting.")
        return
    
    print("Detecting Flights... Please wait.")
    flights = group_files(files)
    print("Flights detected:")
    for i, flight in enumerate(flights, 1):
        print(f"Flight {i}:")
        for f in flight:
            print(f"  {os.path.basename(f)}")
        print()  # Print an empty line after each flight

    root = Tk()
    root.withdraw()
    output_folder_name = simpledialog.askstring("Output Folder", "Enter the name of the destination folder:")
    root.destroy()
    if not output_folder_name:
        print("No output folder name provided. Exiting.")
        return

    earliest_date = min(parse_filename(f) for f in files).strftime("%Y %m %d")
    full_output_folder = os.path.join(OUTPUT_BASE_PATH, f"{earliest_date} {output_folder_name}")
    os.makedirs(full_output_folder, exist_ok=True)

    merge_videos(flights, full_output_folder, f"{earliest_date} {output_folder_name}")

    print("Processing complete. Press Enter to exit.")
    input()

if __name__ == "__main__":
    main(sys.argv[1:])
