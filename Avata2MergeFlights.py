"""
Avata2MergeFlights - Merge DJI Avata 2 flight videos and subtitles.

Groups MP4 files into flights based on timestamps (files recorded within
10 seconds of each other are treated as one flight), then merges each
flight's videos and SRT subtitle files into single output files.

Usage:
    Avata2MergeFlights.py <file1.MP4> <file2.MP4> ...

    Pass one or more DJI Avata 2 MP4 files as arguments. The script will:
    1. Auto-detect flights by grouping consecutive clips.
    2. Prompt for an output folder name (via dialog).
    3. Merge each flight's clips using mp4_merge and combine the SRT files.
    4. Save results to OUTPUT_BASE_PATH/<date> <folder name>/.
    5. Verify each merge (mp4_merge exit code, size within 0.1%, duration
       within 2 s), then show a confirmation dialog listing that evidence.
       Originals are deleted only after you confirm — review the merged
       videos before confirming.

    Every run writes a full log (argv, grouping decisions, mp4_merge output,
    verification math, deletions) to OUTPUT_BASE_PATH/logs/.

    Expected filename format: DJI_YYYYMMDDHHMMSS_XXXX_D.MP4
    Companion .SRT files (same name) are merged automatically.

Requirements:
    - Python 3, moviepy, tkinter
    - mp4_merge utility (see MP4_MERGE_PATH below)
"""

import os
import sys
import subprocess
import re
import logging
from datetime import datetime, timedelta
from tkinter import simpledialog, Tk, Label, Frame, Text, Scrollbar, Button
from moviepy.editor import VideoFileClip

# Set the base output path and path to the video merging utility
OUTPUT_BASE_PATH = "C:\\Users\\Mario\\Downloads\\FPV"
MP4_MERGE_PATH = "D:\\portable_apps\\mp4_merge-windows64.exe"
LOG_DIR = os.path.join(OUTPUT_BASE_PATH, "logs")

# Deletion safety thresholds
SIZE_TOLERANCE = 0.001        # merged size must match input total within 0.1%
DURATION_TOLERANCE_S = 2.0    # merged duration must match input total within 2 s

log = logging.getLogger("Avata2Merge")

def setup_logging():
    """Log everything to a timestamped file in LOG_DIR and to the console."""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, datetime.now().strftime("merge_%Y%m%d_%H%M%S") + f"_{os.getpid()}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )
    return log_path

def fmt_td(td):
    """Format a timedelta as H:MM:SS.s for logs and reports."""
    total = td.total_seconds()
    hours, remainder = divmod(int(total), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds + total % 1:04.1f}"

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
    duration = timedelta(seconds=clip.duration)
    clip.close()
    return duration

def srt_companion(mp4_path):
    """Return the path of the companion SRT file, or None if it doesn't exist."""
    base = os.path.splitext(mp4_path)[0]
    for ext in ('.SRT', '.srt'):
        candidate = base + ext
        if os.path.exists(candidate):
            return candidate
    return None

def group_files(files):
    """
    Group files that belong to the same flight based on their timestamps.
    Files are considered part of the same flight if the start time of one file
    is within 10 seconds of the end time of the previous file in a sorted list.
    Returns (flights, durations) where durations maps file -> timedelta.
    """
    flights = []
    current_flight = []
    last_end_time = None
    durations = {}

    for file in sorted(files, key=parse_filename):
        start_time = parse_filename(file)
        duration = get_video_duration(file)
        durations[file] = duration
        info = f"{os.path.basename(file)}: {os.path.getsize(file):,} B, duration {fmt_td(duration)}"
        if last_end_time is None:
            log.info(f"  {info} -- first clip, starts Flight 1")
            current_flight.append(file)
        elif start_time <= last_end_time + timedelta(seconds=10):
            gap = (start_time - last_end_time).total_seconds()
            log.info(f"  {info} -- starts {gap:.1f} s after previous clip ended, same flight")
            current_flight.append(file)
        else:
            gap = (start_time - last_end_time).total_seconds()
            flights.append(current_flight)
            log.info(f"  {info} -- starts {gap:.1f} s after previous clip ended (> 10 s), starts Flight {len(flights) + 1}")
            current_flight = [file]
        last_end_time = start_time + duration

    if current_flight:
        flights.append(current_flight)

    return flights, durations

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

def merge_srt_files(flight, durations, output_srt_file):
    """
    Merge the companion SRT files of a flight into output_srt_file.
    Returns (srt_map, missing, bad): srt_map maps each MP4 to the SRT that was
    merged for it, missing lists MP4s with no SRT companion, bad lists SRTs
    that exist but have no parseable timestamps (excluded from the merge).
    """
    merged_content = []
    srt_map = {}
    missing = []
    bad = []
    current_offset = timedelta()
    frame_offset = 0
    frame_pattern = re.compile(r'FrameCnt: (\d+)')

    for filename in flight:
        srt_filename = srt_companion(filename)
        if srt_filename is None:
            missing.append(filename)
            # Skip this clip's playtime so later subtitles stay aligned with
            # the merged video; frame counters cannot be compensated this way.
            current_offset += durations[filename]
            continue

        with open(srt_filename, 'r', encoding='utf-8') as infile:
            srt_content = infile.read()

        # Find the last timestamp and frame count in the file
        lines = srt_content.strip().split('\n')
        last_timestamp = None
        last_frame = 0
        for line in reversed(lines):
            if '-->' in line:
                last_timestamp = line.split('-->')[1].strip()
                break

        for line in reversed(lines):
            frame_match = frame_pattern.search(line)
            if frame_match:
                last_frame = int(frame_match.group(1))
                break

        end_time = None
        if last_timestamp:
            try:
                end_time = parse_srt_time(last_timestamp)
            except ValueError as e:
                log.warning(f"Could not parse timestamp in file {srt_filename}: {e}")
                log.warning(f"Problematic line: {last_timestamp}")

        if end_time is None:
            bad.append(srt_filename)
            current_offset += durations[filename]
            continue

        merged_content.append(adjust_srt_timestamps(srt_content, current_offset, frame_offset))
        srt_map[filename] = srt_filename
        current_offset += end_time
        frame_offset += last_frame

    if merged_content:
        with open(output_srt_file, 'w', encoding='utf-8') as outfile:
            outfile.write('\n\n'.join(merged_content))

    return srt_map, missing, bad

def run_mp4_merge(command):
    """
    Run mp4_merge, streaming its output to the console as it arrives so the
    \r-repainted progress percentage stays visible in real time (capturing
    it wholesale would hide it until the process exits). Returns
    (returncode, output) with consecutive progress ticks collapsed to the
    last one so the log stays readable.
    """
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    raw = bytearray()
    while True:
        b = proc.stdout.read(1)
        if not b:
            break
        sys.stdout.buffer.write(b)
        if b in b'\r\n':
            sys.stdout.buffer.flush()
        raw.extend(b)
    returncode = proc.wait()
    if raw and not raw.endswith(b'\n'):
        sys.stdout.buffer.write(b'\n')
    sys.stdout.buffer.flush()

    lines = [l for l in re.split(r'[\r\n]+', raw.decode('utf-8', errors='replace')) if l.strip()]
    trimmed = []
    for idx, line in enumerate(lines):
        if 'Merging...' in line and idx + 1 < len(lines) and 'Merging...' in lines[idx + 1]:
            continue
        trimmed.append(line)
    return returncode, '\n'.join(trimmed)

def merge_flights(flights, durations, output_folder, base_output_name):
    """
    Merge each flight's videos and SRTs, verify the results, and return a
    list of per-flight result dicts. Deletes nothing.
    """
    results = []
    for i, flight in enumerate(flights, 1):
        output_file = os.path.join(output_folder, f"{base_output_name} {i}.mp4")
        output_srt_file = os.path.join(output_folder, f"{base_output_name} {i}.srt")
        result = {'index': i, 'files': flight, 'output_file': output_file,
                  'ok': False, 'reasons': [], 'problems': [], 'notes': [],
                  'srt_map': {}, 'output_size': None, 'snapshot': {}}
        results.append(result)
        log.info(f"--- Flight {i}: merging {len(flight)} clip(s) -> {output_file}")

        if os.path.exists(output_file) or os.path.exists(output_srt_file):
            result['problems'].append("output file already exists -- refusing to overwrite; "
                                      "rename it or pick a different folder name")
            log.error(f"Flight {i}: output already exists, skipping: {output_file}")
            continue

        try:
            command = [MP4_MERGE_PATH] + flight + ["--out", output_file]
            log.info(f"Running: {subprocess.list2cmdline(command)}")
            returncode, merge_output = run_mp4_merge(command)
            if merge_output:
                log.info(f"mp4_merge output:\n{merge_output}")
            if returncode == 0:
                result['reasons'].append("mp4_merge exited with code 0")
            else:
                result['problems'].append(f"mp4_merge exited with code {returncode}")

            if not os.path.exists(output_file):
                result['problems'].append("output file was not created")
                log.error(f"Flight {i}: output file not found: {output_file}")
                continue

            try:
                srt_map, srt_missing, srt_bad = merge_srt_files(flight, durations, output_srt_file)
                result['srt_map'] = srt_map
                for m in srt_missing:
                    log.warning(f"Flight {i}: no SRT companion for {os.path.basename(m)} -- merged SRT has a "
                                f"telemetry gap there (timestamps compensated, frame counters not)")
                    result['notes'].append(f"{os.path.basename(m)}: no SRT companion -- telemetry gap in merged SRT")
                for b in srt_bad:
                    log.warning(f"Flight {i}: {os.path.basename(b)} has no parseable timestamps -- "
                                f"excluded from merged SRT, file will be kept")
                    result['notes'].append(f"{os.path.basename(b)}: unreadable SRT excluded from merge; it will NOT be deleted")
                if srt_map:
                    result['reasons'].append(f"merged SRT written ({len(srt_map)}/{len(flight)} clips): {os.path.basename(output_srt_file)}")
                else:
                    result['reasons'].append("no usable SRT companions found -- no SRT merged")
            except Exception:
                log.exception(f"Flight {i}: SRT merging failed")
                result['problems'].append("SRT merging raised an error (see log)")

            output_size = os.path.getsize(output_file)
            input_size = sum(os.path.getsize(f) for f in flight)
            size_difference = abs(input_size - output_size) / input_size
            size_line = (f"output size {output_size:,} B vs input total {input_size:,} B "
                         f"(diff {size_difference:.3%}, limit {SIZE_TOLERANCE:.1%})")
            log.info(f"Flight {i}: {size_line}")
            if size_difference <= SIZE_TOLERANCE:
                result['reasons'].append(size_line)
            else:
                result['problems'].append(f"size mismatch: {size_line}")

            try:
                output_duration = get_video_duration(output_file)
                input_duration = sum((durations[f] for f in flight), timedelta())
                duration_diff = abs((output_duration - input_duration).total_seconds())
                dur_line = (f"output duration {fmt_td(output_duration)} vs input total {fmt_td(input_duration)} "
                            f"(diff {duration_diff:.1f} s, limit {DURATION_TOLERANCE_S:.0f} s)")
                log.info(f"Flight {i}: {dur_line}")
                if duration_diff <= DURATION_TOLERANCE_S:
                    result['reasons'].append(dur_line)
                else:
                    result['problems'].append(f"duration mismatch: {dur_line}")
            except Exception:
                log.exception(f"Flight {i}: could not read merged video duration")
                result['problems'].append("could not read merged video duration (see log)")

            result['ok'] = not result['problems']
            if result['ok']:
                # Freeze what verification saw, so deletion can detect any
                # change made while the user reviews the merged videos.
                result['output_size'] = output_size
                for path in flight + sorted(result['srt_map'].values()):
                    st = os.stat(path)
                    result['snapshot'][path] = (st.st_size, st.st_mtime)
        except Exception:
            log.exception(f"Flight {i}: unexpected error")
            result['problems'].append("unexpected error (see log)")
            result['ok'] = False

    return results

def build_report(results):
    """Human-readable per-flight report of what will be deleted and why."""
    lines = []
    for r in results:
        lines.append(f"Flight {r['index']}  ->  {os.path.basename(r['output_file'])}")
        lines.append(f"  Source clips ({len(r['files'])}):")
        for f in r['files']:
            suffix = "  [+ SRT]" if f in r['srt_map'] else ""
            try:
                lines.append(f"    {os.path.basename(f)} ({os.path.getsize(f):,} B){suffix}")
            except OSError:
                lines.append(f"    {os.path.basename(f)} (size unavailable){suffix}")
        if r['ok']:
            lines.append("  WILL BE DELETED -- all checks passed:")
        else:
            lines.append("  WILL BE KEPT -- checks failed:")
            for p in r['problems']:
                lines.append(f"    [FAIL] {p}")
        for reason in r['reasons']:
            lines.append(f"    [ok]   {reason}")
        for note in r['notes']:
            lines.append(f"    [note] {note}")
        lines.append("")
    return '\n'.join(lines)

def confirm_deletion(report_text, delete_count):
    """
    Show a scrollable confirmation dialog with the deletion report.
    Returns True only if the user explicitly clicks Delete; closing the
    window keeps the originals.
    """
    result = {'delete': False}
    root = Tk()
    root.title("Confirm deletion of source files")
    root.attributes('-topmost', True)

    Label(root, justify='left', anchor='w', text=(
        f"Review the merged videos now, before confirming.\n"
        f"Confirming will permanently delete {delete_count} source file(s). "
        f"Closing this window keeps all originals.")).pack(fill='x', padx=10, pady=(10, 5))

    frame = Frame(root)
    frame.pack(fill='both', expand=True, padx=10)
    scrollbar = Scrollbar(frame)
    scrollbar.pack(side='right', fill='y')
    text = Text(frame, wrap='none', width=110, height=35,
                font=('Consolas', 10), yscrollcommand=scrollbar.set)
    text.insert('1.0', report_text)
    text.config(state='disabled')
    text.pack(side='left', fill='both', expand=True)
    scrollbar.config(command=text.yview)

    def on_delete():
        result['delete'] = True
        root.destroy()

    def on_keep():
        root.destroy()

    buttons = Frame(root)
    buttons.pack(pady=10)
    Button(buttons, text=f"Delete {delete_count} source file(s)", command=on_delete).pack(side='left', padx=10)
    keep_button = Button(buttons, text="Keep originals", command=on_keep)
    keep_button.pack(side='left', padx=10)
    keep_button.focus_set()
    root.protocol("WM_DELETE_WINDOW", on_keep)
    root.mainloop()
    return result['delete']

def handle_deletion(results):
    """Show the confirmation dialog and delete sources of verified flights."""
    ok_flights = [r for r in results if r['ok']]
    for r in results:
        if not r['ok']:
            log.warning(f"Flight {r['index']}: source files will be kept: {'; '.join(r['problems'])}")

    if not ok_flights:
        log.info("No flight passed all checks -- no source files will be deleted.")
        return

    total = sum(len(r['files']) + len(r['srt_map']) for r in ok_flights)

    report = build_report(results)
    log.info(f"Deletion report:\n{report}")
    log.info(f"Asking for confirmation to delete {total} file(s)...")
    if not confirm_deletion(report, total):
        log.info("User declined -- no source files were deleted.")
        return

    log.info("User confirmed deletion.")
    deleted = 0
    for r in ok_flights:
        # Revalidate: files can change during the (possibly long) review pause
        # between verification and confirmation.
        try:
            output_intact = os.path.getsize(r['output_file']) == r['output_size']
        except OSError:
            output_intact = False
        if not output_intact:
            log.error(f"Flight {r['index']}: merged output missing or changed since verification -- "
                      f"keeping all its source files")
            continue
        for f in list(r['files']) + sorted(r['srt_map'].values()):
            try:
                st = os.stat(f)
                if (st.st_size, st.st_mtime) != r['snapshot'].get(f):
                    log.error(f"Not deleted (changed since verification): {f}")
                    continue
                os.remove(f)
                deleted += 1
                log.info(f"Deleted: {f}")
            except OSError as e:
                log.error(f"Could not delete {f}: {e}")
    log.info(f"Deleted {deleted} of {total} file(s).")

def main(files):
    """
    Main function to process the files.
    Opens a dialog for output folder naming and manages the merging process.
    """
    log.info(f"Received {len(files)} file argument(s):")
    for f in files:
        if os.path.exists(f):
            log.info(f"  {f} ({os.path.getsize(f):,} B)")
        else:
            log.error(f"  {f} -- DOES NOT EXIST")

    if not files:
        log.error("No files provided. Exiting.")
        return
    if any(not os.path.exists(f) for f in files):
        log.error("Aborting: some input files do not exist. Nothing was merged or deleted.")
        return

    unique_files = []
    seen = set()
    for f in files:
        key = os.path.normcase(os.path.normpath(f))
        if key in seen:
            log.warning(f"Duplicate input ignored: {f}")
        else:
            seen.add(key)
            unique_files.append(f)
    files = unique_files

    log.info("Detecting flights... Please wait.")
    flights, durations = group_files(files)
    log.info(f"Detected {len(flights)} flight(s):")
    for i, flight in enumerate(flights, 1):
        total = sum((durations[f] for f in flight), timedelta())
        log.info(f"  Flight {i}: {len(flight)} clip(s), total duration {fmt_td(total)}")
        for f in flight:
            log.info(f"    {os.path.basename(f)}")

    root = Tk()
    root.withdraw()
    output_folder_name = simpledialog.askstring("Output Folder", "Enter the name of the destination folder:")
    root.destroy()
    if output_folder_name:
        output_folder_name = output_folder_name.strip()
    if not output_folder_name:
        log.info("No output folder name provided. Exiting; nothing was merged or deleted.")
        return
    if re.search(r'[<>:"/\\|?*]', output_folder_name) or '..' in output_folder_name:
        log.error(f"Invalid folder name {output_folder_name!r} -- must be a plain name without "
                  f"path separators or special characters. Exiting; nothing was deleted.")
        return

    earliest_date = min(parse_filename(f) for f in files).strftime("%Y %m %d")
    full_output_folder = os.path.join(OUTPUT_BASE_PATH, f"{earliest_date} {output_folder_name}")
    os.makedirs(full_output_folder, exist_ok=True)
    log.info(f"Output folder: {full_output_folder}")

    results = merge_flights(flights, durations, full_output_folder, f"{earliest_date} {output_folder_name}")
    handle_deletion(results)

    log.info("Processing complete.")

if __name__ == "__main__":
    log_path = setup_logging()
    log.info("=== Avata2MergeFlights started ===")
    log.info(f"Log file: {log_path}")
    try:
        main(sys.argv[1:])
    except Exception:
        log.exception("Unhandled error")
    print(f"\nLog saved to: {log_path}")
    input("Press Enter to exit.")
