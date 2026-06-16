import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "raw_data"
OUTPUT_DIR = ROOT / "dify_ready_payload"
OUTPUT_ZIP = ROOT / "dify_ready_payload.zip"


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
OBSIDIAN_LINK_RE = re.compile(r"\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    return metadata, text[match.end():]


def metadata_block(metadata: dict[str, str]) -> str:
    if not metadata:
        return ""

    labels = {
        "category": "分类",
        "year": "年份",
        "status": "状态",
        "tags": "标签",
    }
    parts = []
    for key in ("category", "year", "status", "tags"):
        value = metadata.get(key)
        if value:
            parts.append(f"{labels[key]}：{value}")

    return f"> 文档元信息：{'；'.join(parts)}\n\n" if parts else ""


def convert_obsidian_link(match: re.Match[str]) -> str:
    target = match.group(1)
    anchor = match.group(2) or ""
    display = match.group(3) or target

    if anchor:
        return f"{display}（参考文档：{target}；参考章节：{anchor[1:]}）"
    return f"{display}（参考文档：{target}）"


def convert_markdown(text: str) -> str:
    metadata, body = parse_frontmatter(text)
    body = OBSIDIAN_LINK_RE.sub(convert_obsidian_link, body)
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
    return metadata_block(metadata) + body


def main() -> None:
    source_files = sorted(SOURCE_DIR.glob("*.md"))
    if not source_files:
        raise SystemExit(f"No markdown files found in {SOURCE_DIR}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    written_files: list[Path] = []
    for source_file in source_files:
        converted = convert_markdown(source_file.read_text(encoding="utf-8"))
        output_file = OUTPUT_DIR / source_file.name
        output_file.write_text(converted, encoding="utf-8", newline="\n")
        written_files.append(output_file)

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for output_file in written_files:
            zf.write(output_file, output_file.name)

    print(f"source_files={len(source_files)}")
    print(f"output_dir={OUTPUT_DIR}")
    print(f"output_zip={OUTPUT_ZIP}")
    print(f"written_files={len(written_files)}")


if __name__ == "__main__":
    main()
