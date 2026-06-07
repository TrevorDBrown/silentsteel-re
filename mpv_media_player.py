import json
import os
import shutil
import socket
import subprocess
import time
import wave

import media_player


class MpvPlayer:
    def __init__(self, mpv_path: str) -> None:
        self._mpv_path = mpv_path
        self._tmp_path = os.path.join(os.getcwd(), ".codex", "tmp", "mpv_segments")
        self._log_path = os.path.join(os.getcwd(), ".codex", "logs")
        self._ipc_path = os.path.join(self._tmp_path, f"mpv-video-{os.getpid()}.sock")
        self._audio_ipc_path = os.path.join(
            self._tmp_path, f"mpv-audio-{os.getpid()}.sock"
        )
        self._segment_counter = 0
        self._log_handles = []

        os.makedirs(self._tmp_path, exist_ok=True)
        os.makedirs(self._log_path, exist_ok=True)
        self._remove_socket(self._ipc_path)
        self._remove_socket(self._audio_ipc_path)

        self._video_process = self._start_mpv(
            self._ipc_path,
            os.path.join(self._log_path, "mpv-video.log"),
            [
                "--force-window=immediate",
                "--no-auto-window-resize",
                "--geometry=854x480",
                "--autofit=854x480",
                "--keepaspect=yes",
                "--keepaspect-window=yes",
            ],
        )
        self._audio_process = self._start_mpv(
            self._audio_ipc_path,
            os.path.join(self._log_path, "mpv-audio.log"),
            [
                "--no-video",
                "--force-window=no",
            ],
        )

        self._wait_for_socket(
            self._ipc_path,
            self._video_process,
            os.path.join(self._log_path, "mpv-video.log"),
        )
        self._wait_for_socket(
            self._audio_ipc_path,
            self._audio_process,
            os.path.join(self._log_path, "mpv-audio.log"),
        )

    def _start_mpv(
        self, ipc_path: str, log_file: str, extra_args: list[str]
    ) -> subprocess.Popen[bytes]:
        log_handle = open(log_file, "w", encoding="utf-8")
        self._log_handles.append(log_handle)

        return subprocess.Popen(
            [
                self._mpv_path,
                "--idle=yes",
                "--input-terminal=no",
                "--no-terminal",
                "--really-quiet",
                f"--input-ipc-server={ipc_path}",
                *extra_args,
            ],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=log_handle,
        )

    def _wait_for_socket(
        self, ipc_path: str, process: subprocess.Popen[bytes], log_file: str
    ) -> None:
        deadline = time.monotonic() + 5

        while time.monotonic() < deadline:
            if os.path.exists(ipc_path):
                return

            if process.poll() is not None:
                raise RuntimeError(
                    f"mpv exited before creating IPC socket {ipc_path}. "
                    f"See {log_file} for details."
                )

            time.sleep(0.05)

        raise RuntimeError(
            f"mpv IPC socket was not created: {ipc_path}. See {log_file} for details."
        )

    def _remove_socket(self, ipc_path: str) -> None:
        try:
            os.unlink(ipc_path)
        except FileNotFoundError:
            pass

    def _send_command(self, ipc_path: str, command: list) -> dict:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as ipc_socket:
            ipc_socket.connect(ipc_path)
            ipc_socket.sendall((json.dumps({"command": command}) + "\n").encode())
            response = ipc_socket.makefile("r", encoding="utf-8").readline()

        if len(response) == 0:
            return {}

        return json.loads(response)

    def _get_property(self, ipc_path: str, property_name: str):
        response = self._send_command(ipc_path, ["get_property", property_name])
        return response.get("data")

    def _load_file_and_wait(
        self, ipc_path: str, filename: str, options: dict[str, str] | None = None
    ) -> None:
        command: list = ["loadfile", filename, "replace"]

        if options is not None:
            command.append(options)

        response = self._send_command(ipc_path, command)
        error = response.get("error")

        if error not in (None, "success"):
            raise RuntimeError(f"mpv command failed: {error}")

        self._wait_until_loaded(ipc_path, filename)
        self._wait_until_idle(ipc_path)

    def _wait_until_loaded(self, ipc_path: str, filename: str) -> None:
        deadline = time.monotonic() + 5

        while time.monotonic() < deadline:
            loaded_path = self._get_property(ipc_path, "path")
            idle_active = self._get_property(ipc_path, "idle-active")

            if loaded_path == filename or idle_active is False:
                return

            time.sleep(0.05)

        raise TimeoutError(f"Timed out waiting for mpv to load {filename}.")

    def _wait_until_idle(self, ipc_path: str) -> None:
        deadline = time.monotonic() + 60 * 30

        while time.monotonic() < deadline:
            idle_active = self._get_property(ipc_path, "idle-active")

            if idle_active:
                return

            time.sleep(0.05)

        raise TimeoutError("Timed out waiting for mpv playback to finish.")

    def play_mpeg_segment(self, active_video_file: str, start: int, end: int) -> None:
        self._segment_counter += 1
        segment_file = os.path.join(
            self._tmp_path, f"video-segment-{os.getpid()}-{self._segment_counter}.mpg"
        )

        with open(active_video_file, "rb") as source_file:
            source_file.seek(start)
            segment_data = source_file.read(end - start)

        with open(segment_file, "wb") as out_file:
            out_file.write(segment_data)

        try:
            self._load_file_and_wait(self._ipc_path, segment_file)
        finally:
            if os.path.exists(segment_file):
                os.unlink(segment_file)

    def play_timed_video_file(
        self, active_video_file: str, start_milliseconds: int, end_milliseconds: int
    ) -> None:
        start_seconds = start_milliseconds / 1000
        duration_seconds = (end_milliseconds - start_milliseconds) / 1000
        self._load_file_and_wait(
            self._ipc_path,
            active_video_file,
            {
                "start": f"{start_seconds:.3f}",
                "length": f"{duration_seconds:.3f}",
            },
        )

    def play_audio_file(
        self, active_audio_file: str, audio_params, start: int, end: int
    ) -> None:
        self._segment_counter += 1
        segment_file = os.path.join(
            self._tmp_path, f"audio-segment-{os.getpid()}-{self._segment_counter}.wav"
        )

        frame_size = audio_params.nchannels * audio_params.sampwidth
        start_frame = start // frame_size
        frame_count = (end - start) // frame_size

        with wave.open(active_audio_file, "rb") as source_file:
            source_file.setpos(start_frame)
            audio_data = source_file.readframes(frame_count)

        with wave.open(segment_file, "wb") as out_file:
            out_file.setparams(audio_params)
            out_file.writeframes(audio_data)

        try:
            self._load_file_and_wait(self._audio_ipc_path, segment_file)
        finally:
            if os.path.exists(segment_file):
                os.unlink(segment_file)

    def shutdown(self) -> None:
        for ipc_path in (self._ipc_path, self._audio_ipc_path):
            try:
                self._send_command(ipc_path, ["quit"])
            except OSError:
                pass

        for process in (self._video_process, self._audio_process):
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2)

        for log_handle in self._log_handles:
            log_handle.close()

        self._remove_socket(self._ipc_path)
        self._remove_socket(self._audio_ipc_path)


def setup_ffplay() -> MpvPlayer | str:
    mpv_path = shutil.which("mpv")

    if mpv_path is None:
        print("Error - mpv was not found on PATH.")
        return ""

    print(f"Using mpv at: {mpv_path}")
    return MpvPlayer(mpv_path)


def shutdown_player(player: MpvPlayer | str) -> None:
    if isinstance(player, MpvPlayer):
        player.shutdown()


def parse_idx(filename) -> dict:
    return media_player.parse_idx(filename)


def play_audio(
    active_audio_file: str, audio_parts: dict, idx: int, ffplay_path: MpvPlayer
) -> None:
    if idx not in audio_parts:
        print(f"WARNING: Audio not found {idx}")
        return

    with wave.open(active_audio_file, "rb") as wav:
        audio_params = wav.getparams()

    part = audio_parts[idx]
    start = part["start"]
    end = part["end"]
    bitrate = audio_params.framerate * audio_params.nchannels * audio_params.sampwidth
    _start_sec = start / bitrate
    _duration = (end - start) / bitrate

    ffplay_path.play_audio_file(active_audio_file, audio_params, start, end)


def play_video(
    active_video_file: str, video_parts: dict, idx: int, ffplay_path: MpvPlayer
) -> None:
    if idx not in video_parts:
        print(f"WARNING: Video not found {idx}")
        return

    part = video_parts[idx]
    start = part["start"]
    end = part["end"]

    if active_video_file.endswith("MPG"):
        ffplay_path.play_mpeg_segment(active_video_file, start, end)
    elif active_video_file.endswith("AVI"):
        ffplay_path.play_timed_video_file(active_video_file, start, end)
    else:
        print(f"WARNING: Video format not handled {idx}")
