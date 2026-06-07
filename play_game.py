import argparse
import json
import os
import random
import sys

import nefile as nf

import media_player as pm


class GameOptions:
    def __init__(
        self,
        root_path: str,
        start_scene: int,
        ffplay_path: str,
        game_type: str,
        salty_language: bool,
        autoplay: bool,
        silent_run: bool,
        debug: bool,
        input_queue_enabled: bool,
    ) -> None:
        self._root_path = root_path
        self._start_scene = start_scene
        self._ffplay_path = ffplay_path
        self._game_type = game_type
        self._salty_language = salty_language
        self._autoplay = autoplay
        self._silent_run = silent_run
        self._debug = debug
        self.load_input_queue(input_queue_enabled)

    def load_input_queue(self, input_queue_enabled: bool) -> None:
        self._input_queue: list[int] = []

        if not input_queue_enabled:
            return

        with open("Input.txt", "r") as f:
            lines: list[str] = f.readlines()

            for line in lines:
                if str.isnumeric(line.strip()):
                    self._input_queue.append(int(line))
                else:
                    print(f"Specified input ('{line}')is not numeric. Skipping")

        print(f"Input List (presort): {self._input_queue}")

        # Reverse the list, so it can be used as a stack.
        self._input_queue.reverse()

        print(f"Input List is: {self._input_queue}")

        return

    @property
    def root_path(self) -> str:
        return self._root_path

    @property
    def start_scene(self) -> int:
        return self._start_scene

    @property
    def ffplay_path(self) -> str:
        return self._ffplay_path

    @property
    def game_type(self) -> str:
        return self._game_type

    @property
    def salty_language(self) -> bool:
        return self._salty_language

    @property
    def autoplay(self) -> bool:
        return self._autoplay

    @property
    def silent_run(self) -> bool:
        return self._silent_run

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def input_queue(self) -> list[int]:
        return self._input_queue


class GameState:
    current_points: int = 0
    previous_points: int = 0

    def __init__(self):
        self.current_points = 0
        self.previous_points = 0

    def recalculate_points(self, exchange_selection: str) -> None:
        # TODO: the calculation isn't this simple...
        # In some cases, points changed by 2 (i.e. 1 -> -1, -1 -> 1, instead of 1 -> 0, -1 -> 0)

        self.previous_points = self.current_points

        if exchange_selection == "+":
            self.current_points += 1
        elif exchange_selection == "-":
            self.current_points -= 1
        else:
            # i.e. exchange_selection == "="
            # current_points stays the same.
            pass

        return


class game_states:
    CONTINUE = -1  # Advance to next resource/scene.
    END_GAME = -2  # End the game.


class terminal_control:
    UP_ONE_LINE = "\033[A"  # up 1 line
    DELETE_LINE = "\033[K"  # clear line


class terminal_text_styling:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def build_media_entry(
    root_path: str, disc_number: int, video_extension: str, name: str
) -> dict:
    video = f"VIDEO{disc_number}.{video_extension}"
    video_index = f"VIDEO{disc_number}.IDX"
    audio = f"SOUNDS{disc_number}.WAV"
    audio_index = f"SOUNDS{disc_number}.IDX"

    video_file = os.path.join(root_path, video)
    video_index_file = os.path.join(root_path, video_index)
    audio_file = os.path.join(root_path, audio)
    audio_index_file = os.path.join(root_path, audio_index)

    required_files: list[str] = [
        video_file,
        video_index_file,
        audio_file,
        audio_index_file,
    ]
    missing_files: list[str] = [
        filename for filename in required_files if not os.path.exists(filename)
    ]

    if len(missing_files) > 0:
        raise FileNotFoundError(
            f"Missing media files for {name}: {', '.join(missing_files)}"
        )

    return {
        "name": name,
        "video": video,
        "video_file": video_file,
        "video_index": video_index,
        "video_index_file": video_index_file,
        "audio": audio,
        "audio_file": audio_file,
        "audio_index": audio_index,
        "audio_index_file": audio_index_file,
        "video_parts": pm.parse_idx(video_index_file),
        "audio_parts": pm.parse_idx(audio_index_file),
    }


def build_multi_disc_media_bundle(root_path: str, video_extension: str) -> dict:
    return {
        f"disc_{disc_number}": build_media_entry(
            root_path=root_path,
            disc_number=disc_number,
            video_extension=video_extension,
            name=f"Disc {disc_number}",
        )
        for disc_number in range(1, 5)
    }


class MediaLibrary:
    media_bundle: dict
    active_media: dict

    def __init__(self, game_options: GameOptions) -> None:
        if game_options.game_type == "promo":
            # Promotional Version (One disc total)
            self.media_bundle = {
                "disc_promo": build_media_entry(
                    root_path=game_options.root_path,
                    disc_number=1,
                    video_extension="MPG",
                    name="Promo Disc",
                )
            }

            self.swap_media("disc_promo")

        elif game_options.game_type == "mpeg":
            # MPEG Full Retail (Four discs total)
            self.media_bundle = build_multi_disc_media_bundle(
                root_path=game_options.root_path, video_extension="MPG"
            )

            # Start with Disc 1 media.
            self.swap_media("disc_1")

        elif game_options.game_type == "avi":
            # AVI Full Retail Version (Four discs total)
            self.media_bundle = build_multi_disc_media_bundle(
                root_path=game_options.root_path, video_extension="AVI"
            )

            # Start with Disc 1 media.
            self.swap_media("disc_1")

        return

    def get_active_media(self) -> dict:
        return self.active_media

    def swap_media(self, target_media: str) -> None:
        self.active_media = self.media_bundle[target_media]

        print(
            f"{terminal_text_styling.OKGREEN}Swapped to Media from {self.active_media['name']}{terminal_text_styling.ENDC}"
        )

        return


def split_lines(data) -> list:
    parts = []
    string = ""
    while len(data) > 0:
        char = data.pop(0)

        if char == "{":
            if len(string.strip()) > 0:
                parts.append(string.strip())
            parts.append(split_lines(data))
            string = ""
        elif char == "}":
            if len(string.strip()) > 0:
                parts.append(string.strip())
            if len(parts) == 1:
                return parts[0]
            return parts
        else:
            string += char
    return parts


def execute_instruction(
    media_library: MediaLibrary, instruction: str, game_options: dict
) -> tuple[MediaLibrary, GameOptions, int]:
    # Split instruction into instruction part, and subtitle part.
    instruction_parts: list[str] = instruction.split(";")

    # If the split results in two or more parts, the second part represents a subtitle, which should be displayed.
    if len(instruction_parts) > 1 and len(instruction_parts[1].strip()) > 0:
        if not game_options.silent_run:
            # Because the ffplay outputs a blank line in the terminal, we need to go up a line and print the subtitle.
            sys.stdout.write(
                f"{terminal_control.UP_ONE_LINE}{terminal_control.DELETE_LINE}"
            )  # TODO: figure out if something like this can be done with a print statement.

        print(f"<< {instruction_parts[1].strip()}")

    # Get the actual instruction.
    instruction: str = instruction_parts[0].strip()

    if game_options.debug:
        print(
            f"{terminal_text_styling.OKGREEN}Current Full Instruction: {instruction}{terminal_text_styling.ENDC}"
        )

    if instruction[0:2] == "?v":
        # Believed to be entry point for game. No action necessary.
        return media_library, game_options, game_states.CONTINUE

    elif instruction[0:3] in ("?r$"):
        # Instruction for Video Clip Playback
        pm.play_video(
            active_video_file=media_library.get_active_media()["video_file"],
            video_parts=media_library.get_active_media()["video_parts"],
            idx=int(instruction[3:]),
            ffplay_path=game_options.ffplay_path,
        )

    elif instruction[0:3] in ("?R$"):
        # Instruction for Video Clip Playback Selection based on Censorship Level
        sub_instruction_parts: list[str] = instruction[3:].split(",")

        for i, sub_instruction_part in enumerate(sub_instruction_parts):
            if not game_options.salty_language and (i == 0):
                # "Family Friendly" video needs to play. Skip the current sub-instruction.
                continue

            pm.play_video(
                active_video_file=media_library.get_active_media()["video_file"],
                video_parts=media_library.get_active_media()["video_parts"],
                idx=int(sub_instruction_part),
                ffplay_path=game_options.ffplay_path,
            )
            break  # This is only needed if the SALTY_LANGUAGE flag is set to True.

    elif instruction[0:2] in ("?j", "?J"):
        # Instruction to Jump to another instruction.
        return media_library, game_options, int(instruction[2:])

    elif instruction[0:2] in ("?g"):
        # Instruction for Disc Swap (i.e. Insert Disc 2 to continue...)
        disc_code, target_scene = instruction[2:].split(",", 1)
        disc_targets: dict[str, str] = {
            "0100": "disc_1",
            "0200": "disc_2",
            "0300": "disc_3",
            "0600": "disc_4",
        }

        target_media: str | None = disc_targets.get(disc_code)

        if target_media is not None:
            media_library.swap_media(target_media)
        else:
            print(
                f"{terminal_text_styling.WARNING}WARNING: Unknown media swap target {disc_code}{terminal_text_styling.ENDC}"
            )

        return media_library, game_options, int(target_scene)

    elif instruction[0:2] == "?*":
        # TODO: figure out how this instruction works.
        # print(f"{terminal_text_styling.BOLD}Unknown instruction: {terminal_text_styling.OKBLUE}{instruction}{terminal_text_styling.ENDC}")
        # return game_states.CONTINUE

        sub_instruction_parts: list[str] = instruction[2:].split(",")[1:]

        selected_instruction: str = ""

        if instruction == "?*9999,9999":
            return media_library, game_options, game_states.CONTINUE

        if len(sub_instruction_parts) > 1:
            selected_instruction = random.choice(sub_instruction_parts)
        else:
            selected_instruction = sub_instruction_parts[0]

        return media_library, game_options, int(selected_instruction)

    elif instruction[0:6] == "?s0100":
        # Instruction to End the Game.
        return media_library, game_options, game_states.END_GAME

    else:
        # The Instruction is unhandled.
        print(
            f"{terminal_text_styling.BOLD}Unhandled instruction: {terminal_text_styling.OKBLUE}{instruction}{terminal_text_styling.ENDC}"
        )

    return media_library, game_options, game_states.CONTINUE


def play_sequence(
    media_library: MediaLibrary, sequence: str, game_options: GameOptions
) -> tuple[MediaLibrary, GameOptions, int]:
    instructions: list[str] = sequence.strip().split(">")
    ret: int = 0

    for instruction in instructions:
        instruction = instruction.strip()

        if len(instruction) > 0:
            media_library, game_options, ret = execute_instruction(
                media_library, instruction, game_options
            )

            if ret != game_states.CONTINUE:
                return media_library, game_options, ret

    return media_library, game_options, game_states.CONTINUE


def run_exchange(
    media_library: MediaLibrary, exchange: list, game_options: dict
) -> tuple[MediaLibrary, GameOptions, int]:
    options: dict = {}
    last_option: str = ""
    ret: int = 0

    for line in exchange:
        if line[0] in ["+", "=", "-"]:
            options[line] = []
            last_option = line

        elif line[0] == ">":
            options[last_option].append(line)

        else:
            print(
                f"{terminal_text_styling.FAIL}WARNING WRONG EXCHANGE: {line}{terminal_text_styling.ENDC}"
            )

    # Print Exchange Options (1-3)
    for idx, key in enumerate(options.keys()):
        print(f"{idx + 1}. {key[7:]}")

    choice_idx: int = -1

    while choice_idx < 0 or choice_idx > 2:
        if game_options.autoplay:
            # Autoplay is active. Computer will decide.
            choice_idx = random.randrange(3)
            print(f"CPU's Choice: {choice_idx + 1}")

        else:
            if len(game_options.input_queue) > 0:
                # Input via file.
                choice_idx = game_options.input_queue.pop() - 1

                print(f"Input from File: {choice_idx + 1}")

            else:
                choice = input("Your Choice: ")

                if choice.isdigit():
                    choice_idx = int(choice) - 1

    choice_str: str = list(options.keys())[choice_idx]

    print(f">> {choice_str[7:]}")

    audio_idx: str = choice_str[3:7]

    if not game_options.silent_run:
        pm.play_audio(
            active_audio_file=media_library.get_active_media()["audio_file"],
            audio_parts=media_library.get_active_media()["audio_parts"],
            idx=int(audio_idx),
            ffplay_path=game_options.ffplay_path,
        )

    # TODO: determine if this selects the response to the exchange?
    result_str: str = random.choice(options[choice_str])

    instructions: list[str] = result_str.split(">")

    for instruction in instructions:
        instruction = instruction.strip()
        if len(instruction) > 0:
            media_library, game_options, ret = execute_instruction(
                media_library, instruction, game_options
            )
            if ret != game_states.CONTINUE:
                return media_library, game_options, ret

    return media_library, game_options, game_states.CONTINUE


def play_resource(
    media_library: MediaLibrary, resource: str, game_options: GameOptions
) -> tuple[MediaLibrary, GameOptions, int]:
    lines: list = split_lines(list(resource))
    exchange: int = -1
    ret: int = 0

    for scene in lines:
        if isinstance(scene, str) and scene.startswith("sequence"):
            media_library, game_options, ret = play_sequence(
                media_library, scene[8:], game_options
            )
            if ret != game_states.CONTINUE:
                return media_library, game_options, ret

        elif isinstance(scene, str) and scene.endswith("EXCHANGE"):
            exchange = int(scene[0:-9])

        elif exchange > 0 or (isinstance(scene, list) and scene[0][0:1] == "+"):
            media_library, game_options, ret = run_exchange(
                media_library, scene, game_options
            )
            if ret != game_states.CONTINUE:
                return media_library, game_options, ret
            exchange = -1

        else:
            print(
                f"{terminal_text_styling.BOLD}Unsupported Scene: {terminal_text_styling.OKBLUE}{json.dumps(scene)}{terminal_text_styling.ENDC}"
            )

    return media_library, game_options, game_states.CONTINUE


def extract_game_script(executable_file: str) -> tuple[dict, list, int]:
    # Fetch the Resource Table from the executable.
    steel: nf.NE = nf.NE(executable_file)
    data_resources: dict = steel.resource_table.resources["DATA"]

    scenes: dict = {}
    start_scene_index: int = 0

    for i, (resource_id, resource) in enumerate(data_resources.items()):
        data_str: str = (
            resource.data.read().decode("ascii").rstrip("\x1a \x00")
        )  # there's padding
        scenes[resource_id] = data_str

        # This ensures we use the actual first scene of the game.
        if resource_id == 1001:
            start_scene_index = i

    resource_ids: list = list(scenes.keys())

    return scenes, resource_ids, start_scene_index


def main() -> None:
    global pm

    # Establish arguments.
    arg_parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="Silent Steel Player"
    )
    arg_parser.add_argument(
        "--game",
        "-g",
        dest="game_selection",
        choices=["Silent Steel", "Flash Traffic"],
        help="Specifies which TsAGE title you want to play. Please note: this argument is not currently implemented, and will do nothing.",
    )
    arg_parser.add_argument(
        "--game_type",
        "-t",
        required=True,
        dest="game_type",
        choices=["promo", "mpeg", "avi"],
        help="Specifies the game will be played in Promo (MPEG) Mode, MPEG Full Retail Mode, or AVI Full Retail Mode.",
    )
    arg_parser.add_argument(
        "--salty",
        "-x",
        action="store_true",
        help='Specifies whether the "Salty Language"(i.e . uncensored) or "Family Friendly" (i.e. censored) version of the game will be played.',
    )
    arg_parser.add_argument(
        "--autoplay",
        "-a",
        action="store_true",
        help="Specifies if the game will be auto-played.",
    )
    arg_parser.add_argument(
        "--scene",
        "-s",
        type=int,
        help="Specifies a starting scene. Defaults to first scene.",
    )
    arg_parser.add_argument(
        "--silent_run",
        action="store_true",
        help="Specifies whether or not the player speech should play.",
    )
    arg_parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Provides verbose, debug information.",
    )
    arg_parser.add_argument(
        "--input_queue",
        "-i",
        action="store_true",
        help="Specifies whether there are inputs to be processed in Input.txt.",
    )
    arg_parser.add_argument(
        "--use-mpv",
        action="store_true",
        help="Uses persistent mpv player instances instead of spawning ffplay per clip.",
    )
    arg_parser.add_argument(
        "media_path",
        help="Specifies the path to the media files (e.g. VIDEO1.[MPG|AVI], VIDEO1.WAV, VIDEO1.IDX)",
    )

    # Parse the arguments.
    parsed_args: argparse.Namespace = arg_parser.parse_args()

    # Determine if the media path provided is valid.
    root_path: str = parsed_args.media_path

    if not os.path.exists(root_path):
        print("Error - please specify a valid media path.")
        return

    if parsed_args.use_mpv:
        import mpv_media_player

        pm = mpv_media_player

    # Verify media playback setup.
    ffplay_path = pm.setup_ffplay()

    if ffplay_path == "":
        # No available installation of the selected media backend.
        return

    start_scene: int = -1
    if parsed_args.scene:
        start_scene = parsed_args.scene

    # Create the Game Options.
    game_options: GameOptions = GameOptions(
        root_path=root_path,
        start_scene=start_scene,
        ffplay_path=ffplay_path,
        game_type=parsed_args.game_type,
        salty_language=parsed_args.salty,
        autoplay=parsed_args.autoplay,
        silent_run=parsed_args.silent_run,
        debug=parsed_args.debug,
        input_queue_enabled=parsed_args.input_queue,
    )

    try:
        print("Welcome to the Silent Steel Interactive Movie!")

        # STEEL.EXE references
        executable: str = "STEEL.EXE"
        executable_file: str = os.path.join(root_path, executable)

        # Set up the Media Library.
        media_library = MediaLibrary(game_options=game_options)

        # Get the game script from the original executable.
        scenes, resource_ids, start_index = extract_game_script(executable_file)

        # Scene ID and Indexing
        idx: int = start_index
        sceneId: int = resource_ids[idx]

        # If a start scene is specified, jump to it specifically.
        if game_options.start_scene >= 0:
            sceneId = start_scene
            idx = resource_ids.index(sceneId)

        # We're ready to play!
        ret: int = 0
        while True:
            media_library, game_options, ret = play_resource(
                media_library, scenes[sceneId], game_options
            )

            if ret == game_states.CONTINUE:
                # Play next scene, if one exists.
                idx += 1

                if idx < len(resource_ids):
                    sceneId = resource_ids[idx]

                else:
                    print("Game Over.")
                    break

            elif ret == game_states.END_GAME:
                # End the Game.
                print("Game Over.")
                break

            else:
                # Play the specified scene.
                sceneId = ret
                idx = resource_ids.index(sceneId)

    finally:
        pm.shutdown_player(game_options.ffplay_path)


if __name__ == "__main__":
    main()
