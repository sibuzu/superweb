"""Build the offline strategy atlas. Standard-library only; run from any directory."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXCLUDED_PROGRAMS = {"SuperFinlab", "SuperJack", "SuperTrade", "DavidTrade/UltraDavid", "DeepIB", "SuperIB", "SuperJackLite", "SuperDailyX", "SuperOptionPlot", "SuperOptionQuote"}
# Audited support classes whose names do not start with StgBase. Keep these in
# the class index so their parameters still flow into concrete descendants.
SUPPORT_CLASSES = {
    "DavidTrade/Stg深度沖": "共用深度模型框架；countryCode空白且DeepInputs未實作。",
    "WinStock/Stg深度沖": "共用深度模型框架；countryCode空白且DeepInputs未實作。",
    "NetBack/StgStock": "僅提供股票資金與篩選參數封裝，沒有策略API或訊號。",
    "SuperCB/StgXBase": "僅提供可轉債槓桿及損益共用計算，沒有進出場核心。",
}
TOKEN = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|@"(?:""|[^"])*"|\$?"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')


def mask(text, strings=True):
    def replace(m):
        s = m.group()
        return re.sub(r"[^\n]", " ", s) if strings or s.startswith(("//", "/*")) else s
    value = TOKEN.sub(replace, text)
    return re.sub(r"(?m)^\s*#.*$", lambda m: " " * len(m.group()), value)


def pairs(code, left="{", right="}"):
    stack, result = [], {}
    for i, char in enumerate(code):
        if char == left:
            stack.append(i)
        elif char == right and stack:
            result[stack.pop()] = i
    return result


def cs_string(s):
    s = s.strip()
    if s.startswith('@"'):
        return s[2:-1].replace('""', '"')
    if s.startswith('"') and s.endswith('"'):
        return re.sub(r'\\([trn"\\])', lambda m: {"t": "\t", "r": "\r", "n": "\n"}.get(m[1], m[1]), s[1:-1])
    return s


def attr(text, name):
    m = re.search(r"\b" + name + r'\(\s*(@?"(?:\\.|""|[^"\\])*")\s*\)', text)
    return cs_string(m[1]).strip() if m else ""


def preceding_attrs(text, code, start, brackets):
    reverse = {v: k for k, v in brackets.items()}
    end = start
    while end > 0:
        cursor = end - 1
        while cursor >= 0 and code[cursor].isspace():
            cursor -= 1
        if cursor in reverse:
            end = reverse[cursor]
        else:
            break
    return text[end:start]


def split_args(text):
    code = mask(text)
    depth = 0
    starts, parts = 0, []
    for i, c in enumerate(code):
        if c in "([{<": depth += 1
        if c in ")]}>": depth -= 1
        if c == "," and depth == 0:
            parts.append(text[starts:i].strip())
            starts = i + 1
    parts.append(text[starts:].strip())
    return parts


def category_name(expression, constants):
    return constants.get(expression, cs_string(expression)).strip() or "未分類"


def parse_file(path):
    text = path.read_text(encoding="utf-8-sig")
    code, uncommented = mask(text), mask(text, False)
    braces, brackets = pairs(code), pairs(code, "[", "]")
    depth, depths = 0, []
    for c in code:
        depths.append(depth)
        depth += (c == "{") - (c == "}")
    ns = re.search(r"\bnamespace\s+([\w.]+)", code)
    namespace = ns[1] if ns else ""
    constants = {m[1]: cs_string(m[2]) for m in re.finditer(r'\bconst\s+string\s+(\w+)\s*=\s*(@?"(?:\\.|[^"\\])*")', uncommented)}
    result, enums = [], {}
    for em in re.finditer(r"\benum\s+(\w+)\s*(?::\s*\w+\s*)?\{", code):
        start = code.find("{", em.start())
        if start not in braces: continue
        body = uncommented[start + 1:braces[start]]
        enums[em[1]] = [re.sub(r"\s+", " ", v.strip()) for v in split_args(body) if v.strip()]
    for cm in re.finditer(r"\bclass\s+(Stg\w*)\s*(?:\:\s*([^\{]+))?\{", code):
        name = cm[1]
        start = code.find("{", cm.start())
        end = braces.get(start)
        if end is None: continue
        body_depth = depths[start] + 1
        base = (cm[2] or "").strip().split(",")[0].strip()
        props = []
        # Public properties; balanced accessors prevent nested methods/objects leaking in.
        pattern = r"\bpublic\s+(?:(?:new|virtual|override|static|sealed|abstract|readonly)\s+)*([\w.<>,?\[\]\s]+?)\s+(\w+)\s*(\{|=>)"
        for pm in re.compile(pattern).finditer(code, start + 1, end):
            if depths[pm.start()] != body_depth: continue
            ptype, pname, delim = pm.groups()
            if ptype.strip() in ("class", "enum") or pname.startswith("BR"): continue
            pstart = pm.end() - len(delim)
            pend = braces.get(pstart, pstart) if delim == "{" else code.find(";", pstart)
            accessor = code[pstart:pend + 1]
            if delim == "{" and not re.search(r"\b(get|set|init)\b", accessor): continue
            attrs = preceding_attrs(text, code, pm.start(), brackets)
            cat = re.search(r"\bCategory\(([^)]+)\)", attrs)
            props.append(dict(name=pname, type=re.sub(r"\s+", "", ptype), label=attr(attrs, "DisplayName") or pname,
                              description=attr(attrs, "Description"), categoryExpr=cat[1].strip() if cat else "",
                              hidden=bool(re.search(r"Browsable\(\s*false\s*\)", attrs)),
                              writable=bool(re.search(r"\b(set|init)\b", accessor)) and not bool(re.search(r"ReadOnly\(\s*true\s*\)", attrs)),
                              declaration=text[pm.start():pend + 1]))
        desc = next((p["description"] for p in props if p["name"] == "策略名稱" and p["description"]), "")
        literal_name = next((re.search(r'\breturn\s+"([^"\n]+)"', p["declaration"]) for p in props if p["name"] == "策略名稱"), None)
        is_separator = bool(literal_name and re.search(r"---", literal_name[1])) or name in ("StgSep", "Stg日線策略", "Stg分K策略") or bool(re.fullmatch(r"Stg_+", name))
        result.append(dict(name=name, namespace=namespace, base=base, path=path.relative_to(ROOT).as_posix(),
                           props=props, constants=constants, description=desc, separator=is_separator))
    return result, enums, text


def family(name):
    rules = [
        ("基準持有", r"BuyHold|BnH|BHS|持有固定"),
        ("價差與配對", r"Spread|Pair|雙幣對沖|價差|RollYield|VX"),
        ("選擇權", r"BCSP|APT|ART|ABC|選擇|CallPut"),
        ("籌碼與量價", r"外資|未平倉|散戶|買賣超|北上|明牌|借券|成交量|OBV|Volume|委量|PriceVolume|量|擠氣球|Balloon"),
        ("時間與日內", r"時間|當沖|日沖|隔日沖|夜多|隔夜|結算|日內|DayNM|DTime|OddEven"),
        ("均線與趨勢", r"均線|MA|TMA|DMA|蛛網|Kern|ADX|Aroon|肯特納|HDS|BDS|HDX|HDM|HDV|HDZ|BPS|FTS"),
        ("動能與輪動", r"動能|DMS|SMS|PIndex|RSI|TKern|VRP"),
        ("通道與突破", r"布林|Bollinger|突破|Break|TBO|BOM|BO|BB|SDC|高低比|波動"),
        ("網格與分批", r"Grid|網格|加碼|分批"),
        ("盤口與深度", r"David|Deep|Dsp|DVol|DTime"),
    ]
    return next((label for label, pattern in rules if re.search(pattern, name, re.I)), "其他策略")


def discover_programs():
    programs = {}
    for project in sorted((ROOT / "src").rglob("*.csproj")):
        if project.parent.relative_to(ROOT / "src").as_posix() in EXCLUDED_PROGRAMS:
            continue
        if any(part in ("bin", "obj", "packages", ".vs") for part in project.parts):
            continue
        try:
            nodes = ET.parse(project).iter()
        except ET.ParseError:
            continue
        compiled = set()
        for node in nodes:
            if node.tag.rsplit("}", 1)[-1] != "Compile":
                continue
            include = node.get("Include", "").replace("\\", "/")
            if include.endswith(".cs"):
                path = (project.parent / include).resolve()
                if path.is_file(): compiled.add(path)
        candidates = {p for p in compiled if p.name.startswith("Stg") and p.parent.name in ("Strategy", "Strategies")}
        if not candidates:
            continue
        pid = project.parent.relative_to(ROOT / "src").as_posix()
        program = programs.setdefault(pid, dict(projects=[], compiled=set(), strategies=set()))
        program["projects"].append(project.relative_to(ROOT).as_posix())
        program["compiled"].update(compiled)
        program["strategies"].update(candidates)
    return dict(sorted(programs.items(), key=lambda item: item[0].casefold()))


def main():
    discovered = discover_programs()
    compiled_sources = {pid: info["compiled"] for pid, info in discovered.items()}
    paths = list({p for info in discovered.values() for p in info["strategies"]})
    paths.sort()
    classes, sources, all_enums = [], {}, {}
    programs = {}
    for path in paths:
        entries, enums, text = parse_file(path)
        program = path.parent.parent.relative_to(ROOT / "src").as_posix()
        all_enums.setdefault(program, {}).update(enums)
        for c in entries:
            c["program"] = program
        classes.extend(entries)
        key = path.relative_to(ROOT).as_posix()
        sources[key] = text
        programs.setdefault(program, dict(id=program, name=path.parent.parent.name, path=path.parent.parent.relative_to(ROOT).as_posix(), files=[]))["files"].append(key)
    index = {(c["program"], c["name"]): c for c in classes}
    # Enums also live outside the Strategies folder.
    for pid in discovered:
        for path in sorted(compiled_sources[pid]):
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            code = mask(text)
            brace_pairs = pairs(code)
            for em in re.finditer(r"\benum\s+(\w+)\s*(?::\s*\w+\s*)?\{", code):
                start = code.find("{", em.start())
                if start not in brace_pairs: continue
                body = mask(text[start + 1:brace_pairs[start]], False)
                body = re.sub(r"\[[^\]]*\]", "", body)
                all_enums[pid][em[1]] = [re.sub(r"\s+", " ", v.strip()) for v in split_args(body) if v.strip()]
    analyses = {}
    for path in sorted((HERE / "analysis").glob("*.json")):
        analyses.update(json.loads(path.read_text(encoding="utf-8-sig")))
    overview_file = HERE / "programs.json"
    overviews = json.loads(overview_file.read_text(encoding="utf-8-sig")) if overview_file.exists() else {}

    def chain(c):
        result, seen = [], set()
        while c and c["name"] not in seen:
            seen.add(c["name"])
            result.append(c)
            c = index.get((c["program"], c["base"].split(".")[-1]))
        return result[::-1]

    items, inventory = [], []
    for c in classes:
        hierarchy = chain(c)
        descendant = any(x["name"] == "StgBase" for x in hierarchy)
        role = "strategy" if descendant and c["name"] != "StgBase" and not c["name"].startswith("StgBase") else "support"
        if c["separator"] or c["name"].startswith("StgItem"): role = "support"
        # A few programs load external strategies into StgBase itself.
        name = c["name"]
        pid = c["program"]
        list_path = c["path"].rsplit("/", 1)[0] + "/StgList.cs"
        list_raw = sources.get(list_path, "")
        list_code = mask(list_raw, False)
        registered_match = re.search(r"\bnew\s+" + re.escape(name) + r"\s*\(", list_code)
        registration = "listed" if registered_match else "unlisted"
        consts, effective = {}, {}
        for parent in hierarchy:
            consts.update(parent["constants"])
            for p in parent["props"]:
                effective[p["name"]] = p
        params = []
        for p in effective.values():
            category = category_name(p["categoryExpr"], consts)
            if not p["writable"]: continue
            if re.search(r"結果|績效|統計|報表|回測結果", category): continue
            if not p["categoryExpr"] and (p["hidden"] or not re.match(r"^(?:string|int|decimal|double|float|bool|DateTime|TimeSpan|enum\w+)$", p["type"])): continue
            params.append({k: p[k] for k in ("name", "type", "label", "description")} |
                          dict(category=category, options=all_enums[pid].get(p["type"], [])))
        key = pid + "/" + name
        if key in SUPPORT_CLASSES:
            role = "support"
        if role != "strategy":
            continue
        if any(i["id"] == key for i in items):
            raise ValueError(f"Duplicate compiled strategy id: {key}")
        inventory.append(dict(id=key, program=pid, name=name, path=c["path"], lineage=[p["name"] for p in hierarchy]))
        analysis = analyses.get(key)
        ready = bool(analysis and analysis.get("summary") and all(analysis.get(part) for part in ("entry", "exit", "mechanics")) and all(analysis.get("parameterNotes", {}).get(p["name"]) or p["description"] for p in params))
        items.append(dict(id=key, name=name, title=name[3:], program=pid, family=analysis.get("family", family(name)) if analysis else family(name), description=c["description"],
                          inherits=[p["name"][3:] for p in hierarchy[:-1] if not p["name"].startswith("StgBase") and pid + "/" + p["name"] not in SUPPORT_CLASSES],
                          registration=registration,
                          parameters=[{k: p[k] for k in ("name", "type", "label", "description", "category", "options")} for p in params],
                          analysis=analysis, analysisStatus="complete" if ready else "pending"))
    for pid, prog in programs.items():
        strategy = [i for i in items if i["program"] == pid]
        prog.update(strategyCount=len(strategy),
                    completedCount=sum(i["analysisStatus"] == "complete" for i in strategy),
                    overview=overviews.get(pid, ""),
                    families=dict(Counter(i["family"] for i in strategy)),
                    parameterCount=sum(len(i["parameters"]) for i in strategy))
        list_text = sources.get(prog["path"] + "/Strategies/StgList.cs", "")
        prog["dynamic"] = "*.pyx" in list_text or "CreateStrategy" in list_text or "Activator.CreateInstance" in list_text and not strategy
        prog["projects"] = [p.relative_to(ROOT).as_posix() for p in (ROOT / prog["path"]).glob("*.csproj")]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ""
    timestamp = datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    data = dict(meta=dict(generatedAt=timestamp, commit=commit,
                          strategyCount=len(items),
                          parameterCount=sum(len(i["parameters"]) for i in items),
                          parameterDefinitions=len({p["name"] for i in items for p in i["parameters"]}),
                          analysisCount=sum(i["analysisStatus"] == "complete" for i in items),
                          programCount=len(programs),
                          sourceFileCount=len(paths),
                          sourceHash=hashlib.sha256("".join(sources.values()).encode()).hexdigest(),
                          scope="收錄各 VS .csproj 明確納入之 Strategy／Strategies／Stg*.cs；排除未納入專案檔案、基底、狀態物件與分隔列。進度依交易解說及完整參數說明核對。"),
                programs=[{k: programs[pid][k] for k in ("id", "name", "strategyCount", "completedCount", "overview", "families", "parameterCount", "dynamic")} for pid in discovered], items=sorted(items, key=lambda i: (i["program"].casefold(), i["name"])))
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "catalog.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "data" / "catalog.js").write_text("window.STRATEGY_CATALOG=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    (HERE / "work").mkdir(exist_ok=True)
    (HERE / "work" / "inventory.json").write_text(json.dumps(dict(programs=[dict(id=pid, projects=info["projects"]) for pid, info in discovered.items()], strategies=inventory, supportExclusions=SUPPORT_CLASSES), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    progress = ["# 策略整理進度", "", f"程式專案：{len(programs)}；策略類別：{len(items)}；已完成：{data['meta']['analysisCount']}；待整理：{len(items)-data['meta']['analysisCount']}。", "", "僅依 .csproj 納入的檔案盤點，基底／輔助類別不列為策略。依下表順序完成交易原理與參數解說，完成一批即更新網頁。", "", "| 順序 | 程式 | 策略數 | 已完成 | 待整理 |", "| --- | --- | ---: | ---: | ---: |"]
    for n, p in enumerate(data["programs"], 1):
        progress.append(f"| {n} | {p['id']} | {p['strategyCount']} | {p['completedCount']} | {p['strategyCount']-p['completedCount']} |")
    progress += ["", "依使用者指示跳過 " + "、".join(sorted(EXCLUDED_PROGRAMS)) + "，不列入程式總數與待整理項目。", "", f"另經逐項核對排除{len(SUPPORT_CLASSES)}個純支援類別；其參數仍合併至實際策略。排除原因記錄在 work/inventory.json。", "", "內部盤點路徑在 work/inventory.json；網站不顯示原始碼位置。"]
    (HERE / "PROGRESS.md").write_text("\n".join(progress) + "\n", encoding="utf-8")
    print(json.dumps(data["meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
