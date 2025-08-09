import json
import sys
import nefile
import random
import os
import wave
import play_media as pm

CONTINUE = -1
AUTOPLAY = False
PROMO = True
SALTY_LANGUAGE = True
SILENT_RUN = True

global media_bundle
global active_media

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def split_lines(data):
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


def execute_instruction(instruction):
    global media_bundle
    global active_media

    instruction_parts = instruction.split(";")

    if (len(instruction_parts) > 1 and len(instruction_parts[1].strip()) > 0):
        print("<< %s" % instruction_parts[1].strip())

    instruction = instruction_parts[0].strip()

    print(f"Current Instruction: {instruction}")

    if (instruction[0:3] in ("?r$")):
        # Play a Video Clip
        pm.play_video(active_video_file=active_media["video_file"], video_parts=active_media["video_parts"], idx=int(instruction[3:]))

    elif (instruction[0:3] in ("?R$")):
        # Play a Potentially Censored Video Clip
        # TODO: verify this is the command that determines if the PG or PG-13 version should play.
        sub_instruction_parts = instruction[3:].split(",")

        for i, sub_instruction_part in enumerate(sub_instruction_parts):
            print(f"Sub-Instruction Part: {sub_instruction_part}")

            if (not SALTY_LANGUAGE and (i == 0)):
                # Family Friendly needs to play. Skip index.
                continue

            pm.play_video(active_video_file=active_media["video_file"], video_parts=active_media["video_parts"], idx=int(sub_instruction_part))
            break

    elif (instruction[0:2] in ("?j", "?J")):
        # Jump to Instruction
        return int(instruction[2:])

    elif (instruction[0:2] in ("?g")):
        # Disc Swap request
        # TODO: verify this is accurate...
        match instruction[0:6]:
            case "?g0100":
                # Disc 1
                active_media = media_bundle["disc_1"]
                print("Swapped to Disc 1")

            case "?g0200":
                # Disc 2
                active_media = media_bundle["disc_2"]
                print("Swapped to Disc 2")

            case "?g0300":
                # Disc 3
                active_media = media_bundle["disc_3"]
                print("Swapped to Disc 3")

            case "?g0400":
                # Disc 4
                active_media = media_bundle["disc_4"]
                print("Swapped to Disc 4")

        # Return the rest of the instruction.
        return int(instruction[7:])

    else:
        # Unknown Command
        print(f"{bcolors.BOLD}Warning command: {bcolors.OKBLUE}{instruction}{bcolors.ENDC}")

    return CONTINUE


def play_sequence(sequence):
    instructions = sequence.strip().split(">")
    for instruction in instructions:
        instruction = instruction.strip()
        if (len(instruction) > 0):
            ret = execute_instruction(instruction)
            if (ret != CONTINUE):
                return ret
    return CONTINUE


def run_exchange(exchange):
    options = {}
    lastOption = ""
    for line in exchange:
        if (line[0] in ["+", "=", "-"]):
            options[line] = []
            lastOption = line
        elif (line[0] == ">"):
            options[lastOption].append(line)
        else:
            print("WARNING WRONG EXCHANGE: %s" % line)
    for idx, key in enumerate(options.keys()):
        print("%i. %s" % (idx+1, key[7:]))
    choice_idx = -1
    while (choice_idx < 0 or choice_idx > 2):
        if not AUTOPLAY:
            inputstr = input("Your Choice: ")
            if (inputstr.isdigit()):
                choice_idx = int(inputstr)-1
        else:
            choice_idx = random.randrange(3)
            print("Your Choice: %i" % (choice_idx+1))

    choice_str = list(options.keys())[choice_idx]
    print(">> %s" % choice_str[7:])
    audio_idx = choice_str[3:7]

    if (not SILENT_RUN):
        pm.play_audio(active_audio_file=active_media["audio_file"], audio_parts=active_media["audio_parts"], idx=int(audio_idx))

    result_str = random.choice(options[choice_str])
    instructions = result_str.split(">")
    for instruction in instructions:
        instruction = instruction.strip()
        if (len(instruction) > 0):
            ret = execute_instruction(instruction)
            if (ret != CONTINUE):
                return ret
    return CONTINUE


def play_resource(resource):
    lines = split_lines(list(resource))
    exchange = -1

    for scene in lines:

        with open("Scenes.txt", "a") as f:
            f.write(f"{str(scene)}\n")

        if (isinstance(scene, str) and scene.startswith("sequence")):
            ret = play_sequence(scene[8:])
            if (ret != CONTINUE):
                return ret
        elif isinstance(scene, str) and scene.endswith('EXCHANGE'):
            exchange = int(scene[0:-9])
        elif exchange > 0 or (isinstance(scene, list) and scene[0][0:1] == "+"):
            ret = run_exchange(scene)
            if (ret != CONTINUE):
                return ret
            exchange = -1

        else:
            print(bcolors.BOLD+"Warning Unsupported Scene: " +
                  bcolors.OKBLUE+json.dumps(scene) + bcolors.ENDC)
    return CONTINUE

def main():
    global media_bundle
    global active_media

    root: str = ""

    if len(sys.argv) >= 2 and os.path.isdir(sys.argv[1]):
        root = sys.argv[1]
    else:
        root = "/Volumes/Untitled/"

    executable: str = "STEEL.EXE"
    executable_file: str = os.path.join(root, executable)

    if (PROMO):
        # Promotional Version (One disc total)
        media_bundle = {
            "disc_promo": {
                "video": "VIDEO1.MPG",
                "video_file": os.path.join(root, "VIDEO1.MPG"),
                "video_index": "VIDEO1.IDX",
                "video_index_file": os.path.join(root, "VIDEO1.IDX"),
                "audio": "SOUNDS1.WAV",
                "audio_file": os.path.join(root, "SOUNDS1.WAV"),
                "audio_index": "SOUNDS1.IDX",
                "audio_index_file": os.path.join(root, "SOUNDS_1.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root, "VIDEO1.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root, "SOUNDS1.IDX"))
            }
        }

        active_media = media_bundle["disc_promo"]

    else:
        # Retail Version (Four discs total, start with Disc 1)
        media_bundle = {
            "disc_1": {
                "video": "VIDEO1.AVI",
                "video_file": os.path.join(root, "VIDEO1.AVI"),
                "video_index": "VIDEO1.IDX",
                "video_index_file": os.path.join(root, "VIDEO1.IDX"),
                "audio": "SOUNDS1.WAV",
                "audio_file": os.path.join(root, "SOUNDS1.WAV"),
                "audio_index": "SOUNDS1.IDX",
                "audio_index_file": os.path.join(root, "SOUNDS_1.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root, "VIDEO1.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root, "SOUNDS1.IDX"))
            },
            "disc_2": {
                "video": "VIDEO2.AVI",
                "video_file": os.path.join(root, "VIDEO2.AVI"),
                "video_index": "VIDEO2.IDX",
                "video_index_file": os.path.join(root, "VIDEO2.IDX"),
                "audio": "SOUNDS2.WAV",
                "audio_file": os.path.join(root, "SOUNDS2.WAV"),
                "audio_index": "SOUNDS2.IDX",
                "audio_index_file": os.path.join(root, "SOUNDS2.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root, "VIDEO2.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root, "SOUNDS2.IDX"))
            },
            "disc_3": {
                "video": "VIDEO3.AVI",
                "video_file": os.path.join(root, "VIDEO3.AVI"),
                "video_index": "VIDEO3.IDX",
                "video_index_file": os.path.join(root, "VIDEO3.IDX"),
                "audio": "SOUNDS3.WAV",
                "audio_file": os.path.join(root, "SOUNDS3.WAV"),
                "audio_index": "SOUNDS3.IDX",
                "audio_index_file": os.path.join(root, "SOUNDS3.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root, "VIDEO3.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root, "SOUNDS3.IDX"))
            },
            "disc_4": {
                "video": "VIDEO4.AVI",
                "video_file": os.path.join(root, "VIDEO4.AVI"),
                "video_index": "VIDEO4.IDX",
                "video_index_file": os.path.join(root, "VIDEO4.IDX"),
                "audio": "SOUNDS4.WAV",
                "audio_file": os.path.join(root, "SOUNDS4.WAV"),
                "audio_index": "SOUNDS4.IDX",
                "audio_index_file": os.path.join(root, "SOUNDS4.IDX"),
                "video_parts": pm.parse_idx(os.path.join(root, "VIDEO4.IDX")),
                "audio_parts": pm.parse_idx(os.path.join(root, "SOUNDS4.IDX"))
            }
        }

        active_media = media_bundle["disc_1"]

    # Fetch the Resource Table from the Executable.
    steel = nefile.NE(executable_file)
    data_resources = steel.resource_table.resources["DATA"]

    scenes = {}

    for resource_id, resource in data_resources.items():
        data_str = resource.data.read().decode("ascii").rstrip("\x1a \x00")  # there's padding
        scenes[resource_id] = data_str

    resource_ids = list(scenes.keys())

    idx = 0

    sceneId = resource_ids[idx]

    # TODO: clean this up... parse args.
    if (len(sys.argv) >= 2 and sys.argv[1].isdigit()):
        sceneId = int(sys.argv[1])  # jump forward to this scene/resource
        idx = resource_ids.index(sceneId)

    if (len(sys.argv) >= 2 and "auto" in sys.argv):
        AUTOPLAY = True

    # Main Loop
    while True:

        resource_state = play_resource(scenes[sceneId])

        if (resource_state != CONTINUE):
            sceneId = resource_state
            idx = resource_ids.index(sceneId)

        else:
            idx += 1
            if (idx < len(resource_ids)):
                resource_ids[idx]
            else:
                print("Congratulations - you finished the game!")
                break


if (__name__ == "__main__"):
    main()
