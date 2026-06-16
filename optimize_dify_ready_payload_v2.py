from pathlib import Path


ROOT = Path("dify_ready_payload_v2")


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def parse_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def format_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def is_separator_row(line: str) -> bool:
    cells = parse_row(line)
    if not cells:
        return False
    for cell in cells:
        compact = cell.replace(":", "").replace("-", "").strip()
        if compact or "-" not in cell:
            return False
    return True


def separator_for(width: int) -> str:
    return "| " + " | ".join(["---"] * width) + " |"


def normalize_table(filename: str, block: list[str]) -> list[str]:
    if not block:
        return block

    has_separator = len(block) >= 2 and is_separator_row(block[1])
    header = parse_row(block[0])
    data_lines = block[2:] if has_separator else block[1:]
    rows = [parse_row(line) for line in data_lines]
    width = len(header)

    normalized_rows: list[list[str]] = []
    last_non_empty = [""] * width

    for row in rows:
        if len(row) < width:
            row = row + [""] * (width - len(row))
        elif len(row) > width:
            row = row[:width]

        # Tables converted from PDF merged cells: make the repeated context explicit.
        if header[:2] == ["竞赛分类", "排名"]:
            if not row[0]:
                row[0] = last_non_empty[0]

        if header[:3] == ["奖项级别", "奖项等级", "分值"]:
            if not row[0]:
                row[0] = last_non_empty[0]

        if header[:2] == ["排名", "竞赛分类"]:
            if row[0] == "…":
                row = ["3至n-1", "递推省略"] + ["按公式递减"] * (width - 2)
            elif not row[0]:
                row[0] = last_non_empty[0]

        if header and header[0] == "总人数名次":
            row = [cell if cell else "不适用" for cell in row]

        if header[:4] == ["学院代码", "学院", "专业代码", "专业名称"]:
            if len(row) >= 2 and row[1] == "**总计**":
                row[0] = "合计"
                row[2] = "不适用"
                row[3] = "全部专业"
            else:
                if not row[0]:
                    row[0] = last_non_empty[0]
                if not row[1]:
                    row[1] = last_non_empty[1]

        if header[:3] == ["排名", "学院", "名额"]:
            if len(row) >= 2 and row[1] == "**合计**" and not row[0]:
                row[0] = "合计"

        if "备注" in header:
            remark_idx = header.index("备注")
            if remark_idx < len(row) and not row[remark_idx]:
                row[remark_idx] = "无特别说明"

        # Last pass: do not leave blank cells for Dify chunks that may be retrieved alone.
        row = [cell if cell else "不适用" for cell in row]

        for idx, cell in enumerate(row):
            if cell and cell != "不适用":
                last_non_empty[idx] = cell

        normalized_rows.append(row)

    output = [format_row(header), separator_for(width)]
    output.extend(format_row(row) for row in normalized_rows)
    return output


def normalize_tables(filename: str, text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        if is_table_line(lines[index]):
            block: list[str] = []
            while index < len(lines) and is_table_line(lines[index]):
                block.append(lines[index])
                index += 1
            output.extend(normalize_table(filename, block))
        else:
            output.append(lines[index])
            index += 1
    return "\n".join(output) + "\n"


def split_index_tables(text: str) -> str:
    marker = "## 文件清单\n\n"
    start = text.find(marker)
    if start < 0:
        return text

    table_start = start + len(marker)
    lines = text[table_start:].splitlines()
    table: list[str] = []
    rest_start = 0
    for idx, line in enumerate(lines):
        if is_table_line(line):
            table.append(line)
        else:
            rest_start = idx
            break

    if len(table) < 3:
        return text

    header = table[0]
    sep = separator_for(len(parse_row(header)))
    rows = [parse_row(line) for line in table[2:]]
    for row in rows:
        if row and row[0] == "00":
            row[1] = "知识库索引（本文件）"

    buckets = [
        ("### 文件清单：索引、校级政策与专项材料", {"00", "01", "02", "05", "23", "24", "25", "26", "44", "45"}),
        ("### 文件清单：推荐端推免方案", {f"{idx:02d}" for idx in range(3, 22)}),
        ("### 文件清单：接收端复试录取细则", {"22", *{f"{idx:02d}" for idx in range(27, 44)}, "46"}),
    ]

    chunks: list[str] = []
    for title, ids in buckets:
        bucket_rows = [row for row in rows if row and row[0] in ids]
        chunks.append(title)
        chunks.append("")
        chunks.append(format_row(parse_row(header)))
        chunks.append(sep)
        chunks.extend(format_row(row) for row in bucket_rows)
        chunks.append("")

    rest = "\n".join(lines[rest_start:])
    return text[:table_start] + "\n".join(chunks).rstrip() + "\n" + rest + "\n"


def split_c_competition_table(text: str) -> str:
    marker = "## C类竞赛（60项）\n\n"
    start = text.find(marker)
    if start < 0:
        return text

    table_start = start + len(marker)
    lines = text[table_start:].splitlines()
    table: list[str] = []
    rest_start = 0
    for idx, line in enumerate(lines):
        if is_table_line(line):
            table.append(line)
        else:
            rest_start = idx
            break

    if len(table) < 3:
        return text

    header = parse_row(table[0])
    rows = [parse_row(line) for line in table[2:]]
    first_half = [row for row in rows if row and row[0].isdigit() and int(row[0]) <= 58]
    second_half = [row for row in rows if row and row[0].isdigit() and int(row[0]) > 58]

    chunks: list[str] = []
    for title, bucket_rows in [
        ("### C类竞赛（29-58项）", first_half),
        ("### C类竞赛（59-88项）", second_half),
    ]:
        chunks.append(title)
        chunks.append("")
        chunks.append(format_row(header))
        chunks.append(separator_for(len(header)))
        chunks.extend(format_row(row) for row in bucket_rows)
        chunks.append("")

    rest = "\n".join(lines[rest_start:])
    return text[:table_start] + "\n".join(chunks).rstrip() + "\n" + rest + "\n"


def rename_headings_by_section(text: str, sections: list[tuple[str, str, dict[str, str]]]) -> str:
    lines = text.splitlines()
    for start_marker, end_marker, replacements in sections:
        in_section = False
        for idx, line in enumerate(lines):
            if line == start_marker:
                in_section = True
                continue
            if in_section and line == end_marker:
                break
            if in_section and line in replacements:
                lines[idx] = replacements[line]
    return "\n".join(lines) + "\n"


def targeted_text_fixes(filename: str, text: str) -> str:
    if filename == "42_波特兰学院_2025复试录取细则.md":
        text = text.replace(
            "> 文档元信息：分类：复试录取细则；年份：2026届；状态：权威接收版；标签：[保研/复试细则, 复试面试, 导师联系]",
            "> 文档元信息：分类：复试录取细则；年份：2025版/2026参考；状态：历史参考（2026版暂未发布）；标签：[保研/复试细则, 复试面试, 导师联系, 历史参考]",
        )
        text = text.replace(
            "> **时效判定断言**：波特兰学院2026届复试细则暂未发布，系统被授权依据此2025版细则作为当前唯一官方执行标准。",
            "> **时效判定断言**：波特兰学院2026届复试细则暂未发布；回答2026相关问题时，只能将此2025版细则作为临时参考，并必须提示用户等待学院发布最新版。",
        )

    if filename == "24_硕博连读与本硕贯通培养政策.md":
        text = rename_headings_by_section(
            text,
            [
                (
                    "## 三、研究生支教团（详细版）",
                    "## 四、国防科工单位补偿计划",
                    {
                        "### 基本概况": "### 研究生支教团：基本概况",
                        "### 选拔流程": "### 研究生支教团：选拔流程",
                    },
                ),
                (
                    "## 四、国防科工单位补偿计划",
                    "## 五、直博生（直接攻读博士学位研究生）",
                    {
                        "### 基本概况": "### 国防科工补偿计划：基本概况",
                        "### 申请条件": "### 国防科工补偿计划：申请条件",
                        "### 选拔流程": "### 国防科工补偿计划：选拔流程",
                    },
                ),
                (
                    "## 五、直博生（直接攻读博士学位研究生）",
                    "## 六、本-硕贯通（4+2模式）",
                    {
                        "### 政策依据": "### 直博生：政策依据",
                        "### 申请条件": "### 直博生：申请条件",
                    },
                ),
            ],
        )

    if filename == "45_管理创新专项与补充政策.md":
        text = rename_headings_by_section(
            text,
            [
                (
                    "## 二、退役大学生士兵专项计划",
                    "## 三、少数民族高层次骨干人才计划",
                    {
                        "### 政策说明": "### 退役大学生士兵专项：政策说明",
                        "### 与推免的区别": "### 退役大学生士兵专项：与推免的区别",
                    },
                ),
                (
                    "## 三、少数民族高层次骨干人才计划",
                    "## 四、直博生申请刚性前提",
                    {
                        "### 政策说明": "### 少数民族骨干计划：政策说明",
                        "### 与推免的区别": "### 少数民族骨干计划：与推免的区别",
                    },
                ),
            ],
        )

    if filename == "05_2022年推免工作通知.md":
        old = (
            "按照《教育部关于印发〈全国普通高等学校推荐优秀应届本科毕业生免试攻读硕士学位研究生工作管理办法（试行）〉的通知》（教学〔2006〕14号）、"
            "《教育部办公厅关于进一步加强推荐优秀应届本科毕业生免试攻读研究生工作的通知》(教学厅〔2013〕8号)、"
            "《教育部办公厅关于进一步完善推荐优秀应届本科毕业生免试攻读研究生工作办法的通知》（教学厅〔2014〕5号）精神、"
            "《教育部办公厅关于进一步做好高校学生参军入伍工作的通知》（教学厅〔2015〕3号）等上级文件、以及我校《推荐优秀应届本科毕业生免试攻读研究生管理办法》（修订）（校发〔2021〕6号）（以下简称\"管理办法\"），现将我校2022年推免生工作布置如下："
        )
        new = (
            "按照以下文件精神，现将我校2022年推免生工作布置如下：\n\n"
            "- 《教育部关于印发〈全国普通高等学校推荐优秀应届本科毕业生免试攻读硕士学位研究生工作管理办法（试行）〉的通知》（教学〔2006〕14号）\n"
            "- 《教育部办公厅关于进一步加强推荐优秀应届本科毕业生免试攻读研究生工作的通知》（教学厅〔2013〕8号）\n"
            "- 《教育部办公厅关于进一步完善推荐优秀应届本科毕业生免试攻读研究生工作办法的通知》（教学厅〔2014〕5号）\n"
            "- 《教育部办公厅关于进一步做好高校学生参军入伍工作的通知》（教学厅〔2015〕3号）\n"
            "- 我校《推荐优秀应届本科毕业生免试攻读研究生管理办法》（修订）（校发〔2021〕6号）（以下简称\"管理办法\"）"
        )
        text = text.replace(old, new)

    if filename == "00_知识库索引.md":
        text = split_index_tables(text)

    if filename == "02_竞赛分类目录_完整版.md":
        text = split_c_competition_table(text)

    return text


def main() -> None:
    if not ROOT.exists():
        raise SystemExit(f"Missing directory: {ROOT}")

    changed = []
    for path in sorted(ROOT.glob("*.md")):
        original = path.read_text(encoding="utf-8")
        text = targeted_text_fixes(path.name, original)
        text = normalize_tables(path.name, text)
        if text != original:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed.append(path.name)

    print(f"changed_files={len(changed)}")
    for name in changed:
        print(name)


if __name__ == "__main__":
    main()
