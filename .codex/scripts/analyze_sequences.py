#!/usr/bin/env python3
"""Analyze Silent Steel sequence dumps for opcode and branch patterns."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import re
from pathlib import Path


RESOURCE_RE = re.compile(r"^(?P<resource_id>\d+):\s*(?P<body>.*)$")
INSTRUCTION_RE = re.compile(r"\?(?P<opcode>R\$|r\$|##|[A-Za-z&*#])(?P<args>[^>{}]*)")
PLAYER_CHOICE_RE = re.compile(r"(?P<score>[+=-])\s*!(?P<audio_id>\d{4})(?P<text>[^{}]*)")


@dataclasses.dataclass(frozen=True)
class Instruction:
    dump_name: str
    resource_id: int
    opcode: str
    args: str

    @property
    def mnemonic(self) -> str:
        return f"?{self.opcode}"

    @property
    def numeric_args(self) -> list[int]:
        return [int(value) for value in re.findall(r"\d+", self.args)]


def load_dump(path: Path) -> dict[int, str]:
    resources: dict[int, str] = {}

    with path.open("r", encoding="utf-8") as dump_file:
        for line in dump_file:
            match = RESOURCE_RE.match(line.rstrip("\n"))
            if not match:
                continue

            resources[int(match.group("resource_id"))] = match.group("body")

    return resources


def iter_instructions(dump_name: str, resources: dict[int, str]) -> list[Instruction]:
    instructions: list[Instruction] = []

    for resource_id, body in resources.items():
        for match in INSTRUCTION_RE.finditer(body):
            args = match.group("args").split(";", 1)[0].strip()
            instructions.append(
                Instruction(
                    dump_name=dump_name,
                    resource_id=resource_id,
                    opcode=match.group("opcode"),
                    args=args,
                )
            )

    return instructions


def parse_choices(resources: dict[int, str]) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()

    for body in resources.values():
        for match in PLAYER_CHOICE_RE.finditer(body):
            counts[match.group("score")] += 1

    return counts


def summarize_dump(path: Path) -> dict:
    resources = load_dump(path)
    instructions = iter_instructions(path.name, resources)
    opcode_counts = collections.Counter(instruction.mnemonic for instruction in instructions)
    choice_counts = parse_choices(resources)
    markers: collections.defaultdict[int, list[int]] = collections.defaultdict(list)
    raw_star_branches: list[tuple[int, list[int], str]] = []

    for instruction in instructions:
        if instruction.mnemonic == "?&":
            numbers = instruction.numeric_args
            if numbers:
                markers[numbers[0]].append(instruction.resource_id)

        if instruction.mnemonic == "?*":
            numbers = instruction.numeric_args
            raw_star_branches.append((instruction.resource_id, numbers, instruction.args))

    marker_ids = set(markers)
    star_branches = [
        {
            "resource_id": resource_id,
            "args": numbers,
            "raw": raw_args,
            "first_arg_has_marker": bool(numbers and numbers[0] in marker_ids),
        }
        for resource_id, numbers, raw_args in raw_star_branches
    ]
    branch_first_args = {
        branch["args"][0]
        for branch in star_branches
        if branch["args"]
    }
    branch_targets = {
        target
        for branch in star_branches
        for target in branch["args"][1:]
    }

    return {
        "dump": path.name,
        "resource_count": len(resources),
        "instruction_count": len(instructions),
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "choice_counts": dict(sorted(choice_counts.items())),
        "marker_count": sum(len(values) for values in markers.values()),
        "unique_marker_ids": sorted(marker_ids),
        "star_branch_count": len(star_branches),
        "star_first_args_with_markers": sorted(branch_first_args & marker_ids),
        "star_first_args_without_markers": sorted(branch_first_args - marker_ids),
        "markers_never_seen_as_star_first_arg": sorted(marker_ids - branch_first_args),
        "star_targets_that_are_markers": sorted(branch_targets & marker_ids),
        "star_branches": star_branches,
    }


def format_report(summaries: list[dict]) -> str:
    lines: list[str] = []

    for summary in summaries:
        lines.append(f"# {summary['dump']}")
        lines.append(f"resources: {summary['resource_count']}")
        lines.append(f"instructions: {summary['instruction_count']}")
        lines.append(f"choice counts: {summary['choice_counts']}")
        lines.append("opcode counts:")
        for opcode, count in summary["opcode_counts"].items():
            lines.append(f"  {opcode}: {count}")
        lines.append(f"markers (?&): {summary['marker_count']}")
        lines.append(f"star branches (?*): {summary['star_branch_count']}")
        lines.append(
            "star first args also marked by ?&: "
            + json.dumps(summary["star_first_args_with_markers"])
        )
        lines.append(
            "star first args without matching ?& marker: "
            + json.dumps(summary["star_first_args_without_markers"])
        )
        lines.append(
            "star target args that are ?& markers: "
            + json.dumps(summary["star_targets_that_are_markers"])
        )
        lines.append("")
        lines.append("sample ?* branches:")
        for branch in summary["star_branches"][:25]:
            lines.append(
                f"  {branch['resource_id']}: ?*{branch['raw']} "
                f"first_arg_has_marker={branch['first_arg_has_marker']}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Silent Steel sequence dumps for script opcode patterns."
    )
    parser.add_argument(
        "dumps",
        nargs="+",
        type=Path,
        help="One or more sequence dump files to analyze.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path for machine-readable JSON output.",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        help="Optional path for a human-readable text report.",
    )
    args = parser.parse_args()

    summaries = [summarize_dump(path) for path in args.dumps]
    report = format_report(summaries)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")

    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
