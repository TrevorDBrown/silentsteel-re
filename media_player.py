import os
import struct
import wave
from subprocess import run
import datetime
import local_ffmpeg

def setup_ffplay() -> str:
    ffplay_path: str = ""

    # Check if ffmpeg/ffplay is installed on the system and available on PATH.
    if (local_ffmpeg.is_installed(None)):
        print("Using ffmpeg/ffplay on PATH.")
        return os.path.join(ffplay_path, "ffplay")

    # ffmpeg/ffplay is either not installed on the system, or is unavailable on PATH. Check if a local copy exists in the project directory.
    ffplay_path = os.path.join(os.getcwd(), "bin", "ffmpeg")

    if (local_ffmpeg.is_installed(ffplay_path)):
        print(f"Using ffmpeg/ffplay previously installed at: {ffplay_path}")
        return os.path.join(ffplay_path, "ffplay")

    # ffmpeg/ffplay is not installed in project directory. Install a local copy.
    successful_ffmpeg_install, ffmpeg_install_message = local_ffmpeg.install(ffplay_path)

    if (not successful_ffmpeg_install):
        print(f"Error installing ffmpeg/ffplay: {ffmpeg_install_message}")
        return ""

    # Successful installation of ffplay in project directory.
    return os.path.join(ffplay_path, "ffplay")

def ms_to_timecode(milliseconds: int) -> str:
    """
    Converts milliseconds to a timecode string in HH:MM:SS.mmm format.
    """
    total_seconds = milliseconds / 1000
    td = datetime.timedelta(seconds=total_seconds)

    # Extract hours, minutes, seconds, and milliseconds
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds_part = td.microseconds // 1000

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds_part:03d}"

def parse_idx(filename) -> dict:
    parts: dict = {}
    last_idx: int = -1

    with open(filename, 'rb') as in_file:
        data: bytes = in_file.read(16)
        format: str = data[0:4].decode("ascii")
        length: int = int.from_bytes(data[12:14], "little")

        i: int = 0

        while True:
            i += 1
            idx: int = in_file.read(2)
            if len(idx) == 0:                # breaks loop once no more binary data is read
                break
            idx = int.from_bytes(idx, "little")
            offset = struct.unpack('I', in_file.read(4))[0]
            if (idx > 0):
                parts[idx] = {}
                parts[idx]["start"] = offset
            if (last_idx > 0):
                parts[last_idx]["end"] = offset
            last_idx = idx

        return parts


def play_audio(active_audio_file: str, audio_parts: dict, idx: int, ffplay_path: str) -> None:

    audio_params: dict = {}

    with wave.open(active_audio_file, "rb") as wav:
        audio_params = wav.getparams()

    part = audio_parts[idx]
    start = part["start"]
    end = part["end"]
    bitrate = audio_params.framerate*audio_params.nchannels*audio_params.sampwidth

    # TODO: this somehow isn't frame accurate (sometimes cuts off split second too early or too late)
    start_sec = start/bitrate
    end_sec = end/bitrate
    duration = end_sec-start_sec
    seek = "%.2f" % start_sec
    duration_str = "%.2f" % duration

    # Play the audio.
    run([ffplay_path, '-hide_banner', '-loglevel', 'warning', '-nodisp', '-autoexit', '-i', active_audio_file, '-ss', seek, '-t', duration_str])

    return


def play_video(active_video_file: str, video_parts: dict, idx: int, ffplay_path: str) -> None:

    if (idx in video_parts):
        part = video_parts[idx]
        start = part["start"]
        end = part["end"]
        with open(active_video_file, 'rb') as fin:
            fin.seek(start)

            if (active_video_file.endswith("MPG")):
                # Play as MPEG video.
                run([ffplay_path, '-hide_banner', '-vf', 'scale=-1:480', '-loglevel', 'warning', '-autoexit', '-'], input=fin.read(end - start))

            elif (active_video_file.endswith("AVI")):
                # Play as AVI video.
                run([ffplay_path, '-ss', ms_to_timecode(start), '-t', ms_to_timecode(end - start), active_video_file, '-hide_banner', '-vf', 'scale=-1:480', '-loglevel', 'warning', '-autoexit'])

            else:
                print(f"WARNING: Video format not handled {idx}")
    else:
        print(f"WARNING: Video not found {idx}")

    return

