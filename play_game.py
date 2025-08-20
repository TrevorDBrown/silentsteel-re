import json
import sys
import os
import nefile as nf
import random as rnd
import argparse as ap
import play_media as pm

# My sloppy workaround for passing this data around.
# TODO: make this better!
global media_bundle
global active_media
global input_queue

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

        if (exchange_selection == "+"):
            self.current_points += 1
        elif (exchange_selection == "-"):
            self.current_points -= 1
        else:
            # i.e. exchange_selection == "="
            # current_points stays the same.
            pass

        return


class game_states:
    CONTINUE = -1   # Advance to next resource/scene.
    END_GAME = -2

class terminal_control:
    UP_ONE_LINE = "\033[A" # up 1 line
    DELETE_LINE = "\033[K" # clear line

class terminal_text_styling:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def split_lines(data) -> list:
    parts = []
    string = ""
    while (len(data) > 0):
        char = data.pop(0)

        if (char == "{"):
            if (len(string.strip()) > 0):
                parts.append(string.strip())
            parts.append(split_lines(data))
            string = ""
        elif (char == "}"):
            if (len(string.strip()) > 0):
                parts.append(string.strip())
            if (len(parts) == 1):
                return parts[0]
            return parts
        else:
            string += char
    return parts


def execute_instruction(instruction: str, game_options: dict) -> int:
    global media_bundle
    global active_media

    # Split instruction into instruction part, and subtitle part.
    instruction_parts: list[str] = instruction.split(";")

    # If the split results in two or more parts, the second part represents a subtitle, which should be displayed.
    if (len(instruction_parts) > 1 and len(instruction_parts[1].strip()) > 0):
        if (not game_options["silent_run"]):
            # Because the ffplay outputs a blank line in the terminal, we need to go up a line and print the subtitle.
            sys.stdout.write(f"{terminal_control.UP_ONE_LINE}{terminal_control.DELETE_LINE}")     # TODO: figure out if something like this can be done with a print statement.

        print(f"<< {instruction_parts[1].strip()}")

    # Get the actual instruction.
    instruction: str = instruction_parts[0].strip()

    if (game_options["debug"]):
        print(f"{terminal_text_styling.OKGREEN}Current Full Instruction: {instruction}{terminal_text_styling.ENDC}")

    if (instruction[0:2] == "?v"):
        # Believed to be entry point for game. No action necessary.
        return game_states.CONTINUE

    elif (instruction[0:3] in ("?r$")):
        # Instruction for Video Clip Playback
        pm.play_video(active_video_file=active_media["video_file"], video_parts=active_media["video_parts"], idx=int(instruction[3:]), game_options=game_options)

    elif (instruction[0:3] in ("?R$")):
        # Instruction for Video Clip Playback Selection based on Censorship Level
        sub_instruction_parts: list[str] = instruction[3:].split(",")

        for i, sub_instruction_part in enumerate(sub_instruction_parts):
            if (not game_options["salty_language"] and (i == 0)):
                # "Family Friendly" video needs to play. Skip the current sub-instruction.
                continue

            pm.play_video(active_video_file=active_media["video_file"], video_parts=active_media["video_parts"], idx=int(sub_instruction_part), game_options=game_options)
            break   # This is only needed if the SALTY_LANGUAGE flag is set to True.

    elif (instruction[0:2] in ("?j", "?J")):
        # Instruction to Jump to another instruction.
        return int(instruction[2:])

    elif (instruction[0:2] in ("?g")):
        # Instruction for Disc Swap (i.e. Insert Disc 2 to continue...)
        match instruction[0:6]:
            case "?g0100":      # TODO: this isn't referenced in STEEL.EXE, so unsure what it should actually be...
                # Disc 1
                active_media = media_bundle["disc_1"]
                print(f"{terminal_text_styling.OKGREEN}Swapped to Media from Disc 1{terminal_text_styling.ENDC}")

            case "?g0200":
                # Disc 2
                active_media = media_bundle["disc_2"]
                print(f"{terminal_text_styling.OKGREEN}Swapped to Media from Disc 2{terminal_text_styling.ENDC}")

            case "?g0300":
                # Disc 3
                active_media = media_bundle["disc_3"]
                print(f"{terminal_text_styling.OKGREEN}Swapped to Media from Disc 3{terminal_text_styling.ENDC}")

            case "?g0600":
                # Disc 4
                active_media = media_bundle["disc_4"]
                print(f"{terminal_text_styling.OKGREEN}Swapped to Media from Disc 4{terminal_text_styling.ENDC}")

        # Return the rest of the instruction.
        return int(instruction[7:])

    elif (instruction[0:2] == "?*"):
        # TODO: figure out how this instruction works.
        # print(f"{terminal_text_styling.BOLD}Unknown instruction: {terminal_text_styling.OKBLUE}{instruction}{terminal_text_styling.ENDC}")
        # return game_states.CONTINUE

        sub_instruction_parts: list[str] = instruction[2:].split(",")[1:]

        selected_instruction: str = ""

        if (instruction == "?*9999,9999"):
            return game_states.CONTINUE

        if (len(sub_instruction_parts) > 1):
            selected_instruction = rnd.choice(sub_instruction_parts)
        else:
            selected_instruction = sub_instruction_parts[0]

        return int(selected_instruction)


    elif (instruction[0:6] == '?s0100'):
        # Instruction to End the Game.
        return game_states.END_GAME

    else:
        # The Instruction is unhandled.
        print(f"{terminal_text_styling.BOLD}Unhandled instruction: {terminal_text_styling.OKBLUE}{instruction}{terminal_text_styling.ENDC}")

    return game_states.CONTINUE


def play_sequence(sequence: str, game_options: dict) -> int:
    instructions: list[str] = sequence.strip().split(">")

    for instruction in instructions:

        instruction = instruction.strip()

        if (len(instruction) > 0):

            ret: int = execute_instruction(instruction, game_options)

            if (ret != game_states.CONTINUE):
                return ret

    return game_states.CONTINUE


def run_exchange(exchange: list, game_options: dict) -> int:

    global input_queue

    options: dict = {}
    last_option: str = ""

    for line in exchange:
        if (line[0] in ["+", "=", "-"]):
            options[line] = []
            last_option = line

        elif (line[0] == ">"):
            options[last_option].append(line)

        else:
            print(f"{terminal_text_styling.FAIL}WARNING WRONG EXCHANGE: {line}{terminal_text_styling.ENDC}")

    # Print Exchange Options (1-3)
    for idx, key in enumerate(options.keys()):
        print(f"{idx+1}. {key[7:]}")

    choice_idx: int = -1

    while (choice_idx < 0 or choice_idx > 2):
        if (game_options["autoplay"]):
            # Autoplay is active. Computer will decide.
            choice_idx = rnd.randrange(3)
            print(f"CPU's Choice: {choice_idx+1}")

        else:
            if (len(input_queue) > 0):
                # Input via file.
                choice_idx = (input_queue.pop() - 1)

                print(f"Input from File: {choice_idx + 1}")

            else:
                choice = input("Your Choice: ")

                if (choice.isdigit()):
                    choice_idx = int(choice)-1

    choice_str: str = list(options.keys())[choice_idx]

    print(f">> {choice_str[7:]}")

    audio_idx: str = choice_str[3:7]

    if (not game_options["silent_run"]):
        pm.play_audio(active_audio_file=active_media["audio_file"], audio_parts=active_media["audio_parts"], idx=int(audio_idx), game_options=game_options)

    # TODO: determine if this selects the response to the exchange?
    result_str: str = rnd.choice(options[choice_str])

    instructions: list[str] = result_str.split(">")

    for instruction in instructions:
        instruction = instruction.strip()
        if (len(instruction) > 0):
            ret: int = execute_instruction(instruction, game_options)
            if (ret != game_states.CONTINUE):
                return ret

    return game_states.CONTINUE


def play_resource(resource, game_options: dict) -> int:
    lines: list = split_lines(list(resource))
    exchange: int = -1

    for scene in lines:
        if (isinstance(scene, str) and scene.startswith("sequence")):
            ret: int = play_sequence(scene[8:], game_options)
            if (ret != game_states.CONTINUE):
                return ret

        elif isinstance(scene, str) and scene.endswith('EXCHANGE'):
            exchange = int(scene[0:-9])

        elif exchange > 0 or (isinstance(scene, list) and scene[0][0:1] == "+"):
            ret: int = run_exchange(scene, game_options)
            if (ret != game_states.CONTINUE):
                return ret
            exchange = -1

        else:
            print(f"{terminal_text_styling.BOLD}Unsupported Scene: {terminal_text_styling.OKBLUE}{json.dumps(scene)}{terminal_text_styling.ENDC}")

    return game_states.CONTINUE

def load_input_queue(input_queue_enabled: bool) -> list[int]:
    new_input_queue: list[int] = []

    if (not input_queue_enabled):
        return new_input_queue

    with open("Input.txt", "r") as f:
        lines: list[str] = f.readlines()

        for line in lines:
            if (str.isnumeric(line.strip())):
                new_input_queue.append(int(line))
            else:
                print(f"Specified input ('{line}')is not numeric. Skipping")

    # Reverse the list, so it can be used as a stack.
    new_input_queue.sort(reverse=True)

    return new_input_queue

def main() -> None:
    global media_bundle
    global active_media
    global input_queue

    # Verify ffplay setup.
    ffplay_path: str = pm.setup_ffplay()

    if (ffplay_path == ""):
        # No available installation of ffmpeg/ffplay.
        return

    # Establish arguments.
    arg_parser: ap.ArgumentParser = ap.ArgumentParser(prog="Silent Steel Player")
    arg_parser.add_argument("--promo", "-p", action="store_true", help="Specifies the game will be played in Promo Mode (Disc 1 Only)")
    arg_parser.add_argument("--salty", "-x", action="store_true", help="Specifies whether the uncensored (i.e. \"Salty Language\") or censored (i.e. \"Family Friendly\") version of the game will be played.")
    arg_parser.add_argument("--auto", "-a", action="store_true", help="Specifies if the game will be autoplayed.")
    arg_parser.add_argument("--scene", "-s", type=int, help="Specifies a starting scene. Defaults to first scene.")
    arg_parser.add_argument("--silent_run", action="store_true", help="Specifies whether or not the player speech should play.")
    arg_parser.add_argument("--debug", "-d", action="store_true", help="Provides verbose, debug information.")
    arg_parser.add_argument("--input_queue", "-i", action="store_true", help="Specifies whether there are inputs to be processed in Input.txt.")
    arg_parser.add_argument("media_path", help="Specifies the path to the media files (i.e. VIDEO1.MPG/AVI, VIDEO1.WAV, VIDEO1.IDX)")

    # Parse the arguments.
    parsed_args: ap.Namespace = arg_parser.parse_args()

    root_path: str = ""
    if (parsed_args.media_path):
         root_path = parsed_args.media_path
    else:
        root_path = "/Volumes/Untitled"

    start_scene: int = -1
    if (parsed_args.scene):
        start_scene = parsed_args.scene

    input_queue = load_input_queue(parsed_args.input_queue)

    game_options: dict = {
        "root_path": root_path,
        "start_scene": start_scene,
        "ffplay_path": ffplay_path,
        "promo": parsed_args.promo,
        "salty_language": parsed_args.salty,
        "autoplay": parsed_args.auto,
        "silent_run": parsed_args.silent_run,
        "debug": parsed_args.debug
    }

    print("Welcome to the Silent Steel Interactive Movie!")

    # STEEL.EXE references
    executable: str = "STEEL.EXE"
    executable_file: str = os.path.join(root_path, executable)

    if (game_options["promo"]):
        # Promotional Version (One disc total)
        media_bundle = {
            "disc_promo": {
                "video": "VIDEO1.MPG",
                "video_file": os.path.join(root_path, "VIDEO1.MPG"),
                "video_index": "VIDEO1.IDX",
                "video_index_file": os.path.join(root_path, "VIDEO1.IDX"),
                "audio": "SOUNDS1.WAV",
                "audio_file": os.path.join(root_path, "SOUNDS1.WAV"),
                "audio_index": "SOUNDS1.IDX",
                "audio_index_file": os.path.join(root_path, "SOUNDS_1.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root_path, "VIDEO1.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root_path, "SOUNDS1.IDX"))
            }
        }

        active_media = media_bundle["disc_promo"]

    else:
        # Retail Version (Four discs total)
        media_bundle = {
            "disc_1": {
                "video": "VIDEO1.AVI",
                "video_file": os.path.join(root_path, "VIDEO1.AVI"),
                "video_index": "VIDEO1.IDX",
                "video_index_file": os.path.join(root_path, "VIDEO1.IDX"),
                "audio": "SOUNDS1.WAV",
                "audio_file": os.path.join(root_path, "SOUNDS1.WAV"),
                "audio_index": "SOUNDS1.IDX",
                "audio_index_file": os.path.join(root_path, "SOUNDS_1.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root_path, "VIDEO1.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root_path, "SOUNDS1.IDX"))
            },
            "disc_2": {
                "video": "VIDEO2.AVI",
                "video_file": os.path.join(root_path, "VIDEO2.AVI"),
                "video_index": "VIDEO2.IDX",
                "video_index_file": os.path.join(root_path, "VIDEO2.IDX"),
                "audio": "SOUNDS2.WAV",
                "audio_file": os.path.join(root_path, "SOUNDS2.WAV"),
                "audio_index": "SOUNDS2.IDX",
                "audio_index_file": os.path.join(root_path, "SOUNDS2.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root_path, "VIDEO2.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root_path, "SOUNDS2.IDX"))
            },
            "disc_3": {
                "video": "VIDEO3.AVI",
                "video_file": os.path.join(root_path, "VIDEO3.AVI"),
                "video_index": "VIDEO3.IDX",
                "video_index_file": os.path.join(root_path, "VIDEO3.IDX"),
                "audio": "SOUNDS3.WAV",
                "audio_file": os.path.join(root_path, "SOUNDS3.WAV"),
                "audio_index": "SOUNDS3.IDX",
                "audio_index_file": os.path.join(root_path, "SOUNDS3.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root_path, "VIDEO3.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root_path, "SOUNDS3.IDX"))
            },
            "disc_4": {
                "video": "VIDEO4.AVI",
                "video_file": os.path.join(root_path, "VIDEO4.AVI"),
                "video_index": "VIDEO4.IDX",
                "video_index_file": os.path.join(root_path, "VIDEO4.IDX"),
                "audio": "SOUNDS4.WAV",
                "audio_file": os.path.join(root_path, "SOUNDS4.WAV"),
                "audio_index": "SOUNDS4.IDX",
                "audio_index_file": os.path.join(root_path, "SOUNDS4.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root_path, "VIDEO4.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root_path, "SOUNDS4.IDX"))
            }
        }

        # Start with Disc 1 media.
        active_media = media_bundle["disc_1"]

    # Fetch the Resource Table from the executable.
    steel: nf.NE = nf.NE(executable_file)
    data_resources: dict = steel.resource_table.resources["DATA"]

    scenes: dict = {}

    for resource_id, resource in data_resources.items():
        data_str: str = resource.data.read().decode("ascii").rstrip("\x1a \x00")  # there's padding
        scenes[resource_id] = data_str

    resource_ids: list = list(scenes.keys())

    idx: int = 0
    sceneId: int = resource_ids[idx]

    # If a start scene is specified, jump to it.
    if (game_options["start_scene"] >= 0):
        sceneId = start_scene
        idx = resource_ids.index(sceneId)

    # Ready to play!
    while True:
        ret: int = play_resource(scenes[sceneId], game_options)

        if (ret == game_states.CONTINUE):
            # Play next scene, if one exists.
            idx += 1

            if (idx < len(resource_ids)):
                resource_ids[idx]

            else:
                print("Game Over.")
                break

        elif (ret == game_states.END_GAME):
            # End the Game.
            print("Game Over.")
            break

        else:
            # Play the specified scene.
            sceneId = ret
            idx = resource_ids.index(sceneId)


if (__name__ == "__main__"):
    main()
