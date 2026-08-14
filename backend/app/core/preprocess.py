"""
M1 文本清洗 — 只保留清洗函数，无结构信号/置信度逻辑。
"""

import re

from app.core.logging import logger


def normalize_whitespace(text: str) -> str:
    """压缩连续空白为单空格，保留换行。"""
    text = re.sub(r"[^\S\n]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines)


def fix_broken_lines(text: str) -> str:
    """合并异常断行（跳过代码块和表格）。

    向前跳过空白行查找可合并的下一行，处理「成熟\n\n的个体。」这类中间有空行的断行。
    跳过 YAML 分隔符 `---`、`...` 等，避免误吞噬 frontmatter。
    """
    # 需要跳过的独立行（YAML frontmatter 分隔符、Markdown 分隔线等）
    _SKIP_STRIPPED = frozenset({"---", "...", "___", "***"})

    lines = text.split("\n")
    result: list[str] = []
    in_code_block = False
    in_table = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue

        if re.match(r"^\|.*\|$", stripped) and not in_code_block:
            in_table = True
            result.append(line)
            i += 1
            continue
        elif in_table and stripped == "":
            in_table = False
            result.append(line)
            i += 1
            continue
        else:
            in_table = False

        if (
            not in_code_block
            and stripped != ""
            and stripped not in _SKIP_STRIPPED
            and not stripped.startswith("---")
            and not stripped.startswith("#")
            and not re.search(r"[。！？；.!?;:]$", stripped)
        ):
            # 向前查找下一个非空行（跳过中间空白行）
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                next_stripped = lines[j].strip()
                if (
                    next_stripped != ""
                    and next_stripped not in _SKIP_STRIPPED
                    and not re.match(r"^[A-Z]", next_stripped)
                    and not re.match(r"^[、。，！？；：]", next_stripped)
                ):
                    merged = stripped + next_stripped
                    result.append(merged)
                    i = j + 1
                    continue

        result.append(line)
        i += 1

    return "\n".join(result)


def remove_page_numbers(text: str) -> str:
    """移除整行匹配的页码。"""
    lines = text.split("\n")
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+$", stripped):
            continue
        if re.match(r"^[\-·•]\s*\d+\s*[\-·•]$", stripped):
            continue
        if re.match(r"^第\d+页$", stripped):
            continue
        filtered.append(line)
    return "\n".join(filtered)


def clean_markdown_artifacts(text: str) -> str:
    """移除图像、表格格式、脚注、LaTeX 标记。"""
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"<img\s[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[\|\s]*[-]+\s*\|?\s*[-]+\s*[\|\s]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[\^?\w+\]", "", text)
    text = re.sub(r"\[注\].*?(?=\n|$)", "", text)
    text = re.sub(r"\$(.+?)\$", r"\1", text)
    text = re.sub(r"\$\$(.+?)\$\$", r"\1", text, flags=re.DOTALL)
    return text


def clean_text(raw_text: str) -> str:
    """主入口：执行全部清洗流程。"""
    if not raw_text or not raw_text.strip():
        logger.warning("Empty raw text received")
        return ""

    logger.info("Starting text cleaning")

    # 预先统一换行符（\r\n → \n），否则 YAML frontmatter 正则可能因 \r 不命中
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # YAML frontmatter removal — before any line-level processing
    text = re.sub(r"^---.*?\n---", "", text, flags=re.DOTALL)

    text = normalize_whitespace(text)
    text = fix_broken_lines(text)
    text = remove_page_numbers(text)
    text = clean_markdown_artifacts(text)
    return text.strip()
