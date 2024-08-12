import os
import sys
import subprocess
import re
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

def parse_srt_time(time_str):
    """Parse SRT timestamp string to timedelta object."""
    h, m, s = time_str.replace(',', '.').split(':')
    return timedelta(hours=int(h), minutes=int(m), seconds=float(s))

def format_srt_time(td):
    """Format timedelta object to SRT timestamp string."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def adjust_srt_timestamps(srt_content, time_offset, frame_offset):
    adjusted_lines = []
    current_subtitle = []
    subtitle_count = 0
    frame_pattern = re.compile(r'FrameCnt: (\d+)')

    for line in srt_content.splitlines():
        if line.strip().isdigit():
            if current_subtitle:
                adjusted_lines.extend(current_subtitle)
                adjusted_lines.append('')
            subtitle_count += 1
            current_subtitle = [str(subtitle_count + frame_offset)]
        elif '-->' in line:
            start, end = map(str.strip, line.split('-->'))
            adjusted_start = format_srt_time(parse_srt_time(start) + time_offset)
            adjusted_end = format_srt_time(parse_srt_time(end) + time_offset)
            current_subtitle.append(f"{adjusted_start} --> {adjusted_end}")
        else:
            frame_match = frame_pattern.search(line)
            if frame_match:
                current_frame = int(frame_match.group(1))
                adjusted_frame = current_frame + frame_offset
                line = frame_pattern.sub(f'FrameCnt: {adjusted_frame}', line)
            current_subtitle.append(line)

    if current_subtitle:
        adjusted_lines.extend(current_subtitle)

    return '\n'.join(adjusted_lines)

def merge_srt_files(flight, output_srt_file):
    merged_content = []
    current_offset = timedelta()
    frame_offset = 0

    for filename in flight:
        srt_filename = filename.replace('.MP4', '.SRT')
        if os.path.exists(srt_filename):
            with open(srt_filename, 'r', encoding='utf-8') as infile:
                srt_content = infile.read()
                adjusted_content = adjust_srt_timestamps(srt_content, current_offset, frame_offset)
                merged_content.append(adjusted_content)

            # Find the last timestamp and frame count in the file
            lines = srt_content.strip().split('\n')
            last_timestamp = None
            last_frame = 0
            frame_pattern = re.compile(r'FrameCnt: (\d+)')
            for line in reversed(lines):
                if '-->' in line and not last_timestamp:
                    last_timestamp = line.split('-->')[1].strip()
                    break

            for line in reversed(lines):
                frame_match = frame_pattern.search(line)
                if frame_match:
                    last_frame = int(frame_match.group(1))
                    break

            if last_timestamp:
                try:
                    end_time = parse_srt_time(last_timestamp)
                    current_offset += end_time
                except ValueError as e:
                    print(f"Warning: Could not parse timestamp in file {srt_filename}: {e}")
                    print(f"Problematic line: {last_timestamp}")
            else:
                print(f"Warning: No timestamp found in file {srt_filename}")

            frame_offset += last_frame

    with open(output_srt_file, 'w', encoding='utf-8') as outfile:
        outfile.write('\n\n'.join(merged_content))

    return True  # Indicate successful merging

def merge_videos(flights, output_folder, base_output_name):
    """
    Merge videos of each flight using an external merging utility.
    Also handles corresponding SRT files if they exist.
    """
    for i, flight in enumerate(flights, 1):
        output_file = os.path.join(output_folder, f"{base_output_name} {i}.mp4")
        output_srt_file = os.path.join(output_folder, f"{base_output_name} {i}.srt")
        command = [MP4_MERGE_PATH] + flight + ["--out", output_file]
        subprocess.run(command, shell=True)

        if os.path.exists(output_file):
            srt_success = merge_srt_files(flight, output_srt_file)  # Merge corresponding SRT files
            output_size = os.path.getsize(output_file)
            input_size = sum(os.path.getsize(f) for f in flight)
            size_difference = abs(input_size - output_size) / input_size
            
            if size_difference <= 0.001 and srt_success:
                for f in flight:
                    os.remove(f)
                    print("Deleted:", f)
                    # Delete corresponding SRT file if it exists
                    srt_filename = f.replace('.MP4', '.SRT')
                    if os.path.exists(srt_filename):
                        os.remove(srt_filename)
                        print("Deleted SRT:", srt_filename)
                print(f"Merged SRT file created: {output_srt_file}")
            else:
                if not srt_success:
                    print(f"Files not deleted due to SRT processing errors for Flight {i}")
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
