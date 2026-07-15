"""
M1 Rewrite real-doc validation.

Reads real Obsidian .md files from fixtures/, runs full pipeline,
validates output quality.
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests", "fixtures")

from app.core.atomic_splitter import split_atomic_units
from app.core.preprocess import clean_text
from app.core.section_block_builder import build_section_blocks
from app.core.structural_signal_extractor import extract_structural_signals
from app.core.sub_chunk_builder import build_sub_chunks


def read_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    if not os.path.exists(path):
        print(f"SKIP: {name} not found")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def validate_doc(name: str, text: str) -> list[str]:
    errors: list[str] = []

    # Stage 1: clean
    cleaned = clean_text(text)
    if not cleaned:
        errors.append("FAIL: clean_text returned empty")
        return errors
    print(f"  cleaned: {len(cleaned)} chars (from {len(text)} raw)")

    # Stage 2: extract signals
    signals = extract_structural_signals(cleaned)
    print(f"  signals: {len(signals)}")
    for s in signals:
        print(f"    pos={s.position}, level={s.level}, source={s.source}, content={s.content[:40]}")

    # Stage 3: atomic units
    units = split_atomic_units(cleaned, signals)
    print(f"  atomic units: {len(units)}")
    if not units:
        errors.append("FAIL: no atomic units produced")
        return errors

    # Check for signal-boundary units
    sig_units = [u for u in units if u.is_signal_boundary]
    if not signals:
        pass  # no signals expected
    elif len(sig_units) == 0:
        errors.append(f"WARN: {len(signals)} signals but 0 signal-boundary atomic units")
    else:
        print(f"    signal-boundary: {len(sig_units)}/{len(units)}")

    # Stage 4: sub-chunks
    chunks = build_sub_chunks(units)
    print(f"  sub-chunks: {len(chunks)}")
    total_chunk_chars = 0
    for c in chunks:
        total_chunk_chars += len(c.content)
        if len(c.content) > 3000:
            errors.append(f"FAIL: sub-chunk {c.chunk_index} too large: {len(c.content)} chars")
        if len(c.content) < 50:
            errors.append(f"WARN: sub-chunk {c.chunk_index} too small: {len(c.content)} chars")
        if not (c.start_pos < c.end_pos):
            errors.append(f"FAIL: sub-chunk {c.chunk_index} invalid position: {c.start_pos} >= {c.end_pos}")
    print(f"    total chars: {total_chunk_chars} (cleaned: {len(cleaned)})")
    if abs(total_chunk_chars - len(cleaned)) > 200:
        errors.append(f"FAIL: sub-chunk total ({total_chunk_chars}) differs from cleaned ({len(cleaned)}) by >200")

    # Stage 5: section blocks
    sections = build_section_blocks(chunks, signals)
    print(f"  section blocks: {len(sections)}")
    total_sec_chars = 0
    for s in sections:
        total_sec_chars += len(s.content)
        if len(s.content) > 6000:
            errors.append(f"WARN: section {s.block_index} very large: {len(s.content)} chars")
        if s.title:
            print(f"    [{s.block_index}] title={s.title}, chars={len(s.content)}")
        else:
            print(f"    [{s.block_index}] title=None, chars={len(s.content)}")

        # Check sub-chunk indices reference valid chunks
        for idx in s.sub_chunk_indices:
            if idx >= len(chunks):
                errors.append(f"FAIL: section {s.block_index} invalid sub_chunk index {idx}")
                break

    # Overall check: at least some sections produced
    if sections and len(sections) >= 2:
        # Verify section contents cover the text
        sec_text = "\n".join(s.content for s in sections)
        # Check all signals appear in some section
        for sig in signals:
            sig_in_sec = any(s.start_pos <= sig.position < s.end_pos for s in sections)
            if not sig_in_sec:
                errors.append(f"WARN: signal '{sig.content}' at pos {sig.position} not in any section block")

    print(f"  errors: {len(errors)}")
    return errors


def main():
    if not os.path.exists(FIXTURES_DIR):
        print(f"No fixtures dir at {FIXTURES_DIR}")
        return

    files = sorted(os.listdir(FIXTURES_DIR))
    if not files:
        print("No fixture files")
        return

    total_errors = 0
    for fname in files:
        if not fname.endswith(".md"):
            continue
        print(f"\n{'='*60}")
        print(f"Validating: {fname}")
        print(f"{'='*60}")
        text = read_fixture(fname)
        if not text:
            continue
        errors = validate_doc(fname, text)
        for e in errors:
            print(f"  {e}")
        total_errors += len(errors)

    print(f"\n{'='*60}")
    if total_errors:
        print(f"Total: {total_errors} issues found")
    else:
        print("All real-doc validations passed ✅")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()