"""Check the published offline catalogue against project membership and work records.

This validates coverage and data integrity, not the correctness of trading explanations.
Run with --require-complete for the final goal completion gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
EXCLUDED = {"SuperFinlab", "SuperJack", "SuperTrade", "DavidTrade/UltraDavid", "DeepIB", "SuperIB", "SuperJackLite", "SuperDailyX", "SuperOptionPlot", "SuperOptionQuote"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate(require_complete=False):
    data = read_json(SITE / "data" / "catalog.json")
    inventory = read_json(SITE / "work" / "inventory.json")
    problems = []

    def check(condition, message):
        if not condition:
            problems.append(message)

    programs = {p["id"]: p for p in data["programs"]}
    items = {i["id"]: i for i in data["items"]}
    records = {i["id"]: i for i in inventory["strategies"]}
    check(len(programs) == len(data["programs"]), "Duplicate program IDs")
    check(len(items) == len(data["items"]), "Duplicate strategy IDs")
    check(set(items) == set(records), "Published strategies differ from source inventory")
    check(not EXCLUDED.intersection(programs), "An excluded program is published")
    check("SuperInvETF" in programs, "SuperInvETF must remain included")

    # Discover projects independently: checking only the generated inventory would
    # miss a whole program omitted from both the inventory and public catalogue.
    expected_projects = {}
    for project in (ROOT / "src").rglob("*.csproj"):
        if any(part in {"bin", "obj", "packages", ".vs"} for part in project.parts):
            continue
        pid = project.parent.relative_to(ROOT / "src").as_posix()
        if pid in EXCLUDED:
            continue
        try:
            nodes = ET.parse(project).iter()
        except ET.ParseError:
            problems.append(f"Cannot read VS project: {project.relative_to(ROOT)}")
            continue
        strategy_files = []
        for node in nodes:
            if node.tag.rsplit("}", 1)[-1] != "Compile" or not node.get("Include"):
                continue
            source = project.parent / node.get("Include").replace("\\", "/")
            if source.name.startswith("Stg") and source.suffix == ".cs" and source.parent.name in {"Strategy", "Strategies"}:
                check(source.is_file(), f"Missing compiled strategy file: {source.relative_to(ROOT)}")
                strategy_files.append(source)
        if strategy_files:
            expected_projects.setdefault(pid, set()).add(project.relative_to(ROOT).as_posix())
    check(set(programs) == set(expected_projects), "Published program coverage differs from VS projects")

    compiled = {}
    for program in inventory["programs"]:
        check(set(program["projects"]) == expected_projects.get(program["id"], set()), f"Project coverage mismatch: {program['id']}")
        files = set()
        for name in program["projects"]:
            project = ROOT / name
            check(project.is_file(), f"Missing VS project: {name}")
            if not project.is_file():
                continue
            for node in ET.parse(project).iter():
                if node.tag.rsplit("}", 1)[-1] == "Compile" and node.get("Include"):
                    files.add((project.parent / node.get("Include").replace("\\", "/")).resolve())
        compiled[program["id"]] = files
    check(set(compiled) == set(programs), "Published programs differ from project inventory")

    # Independently count class declarations, rather than trusting two generated
    # lists that could both omit the same strategy. These legacy sources use
    # ordinary class/base declarations; unknown future syntax fails this check.
    expected_classes = set()
    for pid, paths in compiled.items():
        classes = {}
        for path in paths:
            if not path.is_file() or not path.name.startswith("Stg") or path.parent.name not in {"Strategy", "Strategies"}:
                continue
            source = re.sub(r"/\*[\s\S]*?\*/|(?m:^[ \t]*//[^\n]*$)", "", path.read_text(encoding="utf-8-sig"))
            declaration = r"(?m)^[ \t]*((?:(?:public|internal|protected|private|abstract|sealed|partial|static)\s+)*)class\s+(Stg\w+)\s*:\s*([\w.]+)"
            for match in re.finditer(declaration, source):
                classes[match[2]] = (match[3].split(".")[-1], "abstract" in match[1].split())
        for name, (_, abstract) in classes.items():
            key = pid + "/" + name
            if abstract or name.startswith(("StgBase", "StgItem")) or key in inventory.get("supportExclusions", {}):
                continue
            # Audited menu separators, including the named stock divider.
            if name in {"StgSep", "Stg日線策略", "Stg分K策略"} or re.fullmatch(r"Stg_+", name) or key == "NetBack/Stg_____個股策略______":
                continue
            ancestor, seen = name, set()
            while ancestor in classes and ancestor not in seen:
                seen.add(ancestor)
                ancestor = classes[ancestor][0]
            if ancestor == "StgBase" or "StgBase" in seen:
                expected_classes.add(key)
    check(set(items) == expected_classes, "Strategy coverage differs from compiled class declarations: missing=" + ", ".join(sorted(expected_classes - set(items))) + "; unexpected=" + ", ".join(sorted(set(items) - expected_classes)))

    # Explicit support exclusions remain part of the audit trail even though they
    # have no public strategy page. Their inheritance must still reach real items.
    for key, reason in inventory.get("supportExclusions", {}).items():
        pid, name = key.rsplit("/", 1)
        check(key not in items and key not in records, f"Excluded support class is published: {key}")
        check(isinstance(reason, str) and bool(reason.strip()), f"Support exclusion has no reason: {key}")
        check(any(r["program"] == pid and name in r["lineage"][:-1] for r in records.values()), f"Support exclusion has no retained descendant: {key}")
        declaration = re.compile(r"\bclass\s+" + re.escape(name) + r"\b")
        check(any(path.is_file() and declaration.search(path.read_text(encoding="utf-8-sig")) for path in compiled.get(pid, set())), f"Excluded support class is not compiled: {key}")

    explanations = {}
    for path in sorted((SITE / "analysis").glob("*.json")):
        for key, value in read_json(path).items():
            check(key not in explanations, f"Duplicate explanation ID: {key}")
            explanations[key] = value
    check(not set(explanations).difference(items), "Explanation references a strategy outside the published scope: " + ", ".join(sorted(set(explanations).difference(items))))

    completed = 0
    parameters = 0
    rejected_keys = {"path", "line", "defaults", "range", "owner", "inherited"}
    for key, item in items.items():
        record = records.get(key)
        if not record:
            continue
        source = (ROOT / record["path"]).resolve()
        check(source in compiled.get(item["program"], set()), f"Source is not in Compile: {key}")
        check(source.is_file(), f"Missing strategy source: {key}")
        check(source.name.startswith("Stg") and source.suffix == ".cs", f"Unexpected source kind: {key}")
        check(record["program"] == item["program"], f"Source program mismatch: {key}")
        check(not item["name"].startswith(("StgBase", "StgItem")), f"Support class published: {key}")
        support_names = {name.rsplit("/", 1)[1][3:] for name in inventory.get("supportExclusions", {}) if name.rsplit("/", 1)[0] == item["program"]}
        check(not support_names.intersection(item.get("inherits", [])), f"Support class presented as a parent strategy: {key}")
        check(item["registration"] in ("listed", "unlisted"), f"Unsupported list status: {key}")

        # Check list membership independently against the compiled StgList file.
        list_file = source.parent / "StgList.cs"
        if list_file in compiled.get(item["program"], set()) and list_file.is_file():
            text = list_file.read_text(encoding="utf-8-sig")
            text = re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", "", text)
            listed = bool(re.search(r"\bnew\s+" + re.escape(item["name"]) + r"\s*\(", text))
            check((item["registration"] == "listed") == listed, f"List membership mismatch: {key}")

        names = [p["name"] for p in item["parameters"]]
        check(len(names) == len(set(names)), f"Duplicate effective parameter: {key}")
        for parameter in item["parameters"]:
            check(bool(parameter["category"] and parameter["type"] and parameter["label"]), f"Incomplete parameter: {key}/{parameter['name']}")
            check(not rejected_keys.intersection(parameter), f"Unrequested parameter metadata: {key}/{parameter['name']}")
            check(not parameter["name"].startswith("BR"), f"Batch control published as a parameter: {key}/{parameter['name']}")
            options = parameter.get("options")
            check(isinstance(options, list) and all(isinstance(option, str) and option.strip() for option in options), f"Invalid parameter options: {key}/{parameter['name']}")
            if parameter["type"].startswith("enum"):
                check(bool(options), f"Enumeration options are missing: {key}/{parameter['name']}")
        parameters += len(names)

        analysis = explanations.get(key)
        check(item["analysis"] == analysis, f"Published explanation is stale: {key}")
        ready = bool(analysis and analysis.get("summary") and all(analysis.get(k) for k in ("entry", "exit", "mechanics")) and all(analysis.get("parameterNotes", {}).get(p["name"]) or p["description"] for p in item["parameters"]))
        check(item["analysisStatus"] == ("complete" if ready else "pending"), f"Completion status mismatch: {key}")
        if ready:
            completed += 1
            for field in ("entry", "exit", "mechanics", "caveats"):
                value = analysis.get(field)
                check(isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value), f"Invalid explanation section: {key}/{field}")
            if require_complete:
                for parameter in item["parameters"]:
                    note = analysis.get("parameterNotes", {}).get(parameter["name"])
                    check(isinstance(note, str) and bool(note.strip()), f"Parameter explanation remains incomplete: {key}/{parameter['name']}")
        elif require_complete:
            problems.append(f"Strategy remains incomplete: {key}")

    for pid, program in programs.items():
        own_items = [i for i in items.values() if i["program"] == pid]
        check(program["strategyCount"] == len(own_items), f"Program strategy count mismatch: {pid}")
        check(program["completedCount"] == sum(i["analysisStatus"] == "complete" for i in own_items), f"Program completion count mismatch: {pid}")
        if require_complete:
            check(bool(program.get("overview")), f"Program overview remains incomplete: {pid}")

    meta = data["meta"]
    check(meta["programCount"] == len(programs), "Global program count mismatch")
    check(meta["strategyCount"] == len(items), "Global strategy count mismatch")
    check(meta["analysisCount"] == completed, "Global completion count mismatch")
    check(meta["parameterCount"] == parameters, "Global parameter count mismatch")
    script = (SITE / "data" / "catalog.js").read_text(encoding="utf-8")
    prefix = "window.STRATEGY_CATALOG="
    check(script.startswith(prefix), "Offline data script prefix is invalid")
    if script.startswith(prefix):
        check(json.loads(script[len(prefix):].strip().removesuffix(";")) == data, "Offline JS and JSON data differ")
    progress = (SITE / "PROGRESS.md").read_text(encoding="utf-8")
    check(f"程式專案：{len(programs)}；策略類別：{len(items)}；已完成：{completed}" in progress, "Progress document is stale")

    if problems:
        for problem in problems:
            print("FAIL:", problem)
        print(f"{len(problems)} checks failed.")
        return False
    print(f"PASS: {len(programs)} programs, {len(items)} strategies, {completed} complete, {parameters} effective parameters.")
    print("Project membership, exclusions, list status, parameter schema, explanation coverage, offline data and progress are consistent.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true")
    sys.exit(0 if validate(parser.parse_args().require_complete) else 1)
