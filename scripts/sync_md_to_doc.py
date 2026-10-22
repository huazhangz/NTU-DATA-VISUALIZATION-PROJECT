"""Write every project Markdown file into docs/MD.doc.

The .md files stay the source. docs/MD.doc is the WPS/Word copy.
Run from the repository root:

    python3 scripts/sync_md_to_doc.py
"""

from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "MD.doc"

# Project documents only. Do not pull tool caches.
MARKDOWN_FILES = [
    "README.md",
    "reports/project_status/SD6105_project_status_and_pipeline.md",
    "reports/data_cleaning/run_20261022_185006/00_workspace_audit.md",
    "reports/data_cleaning/run_20261022_185006/00_execution_plan.md",
    "reports/data_cleaning/run_20261022_185006/01_source_provenance.md",
    "reports/data_cleaning/run_20261022_185006/02_initial_profile.md",
    "reports/data_cleaning/run_20261022_185006/03_cleaning_specification.md",
    "reports/data_cleaning/run_20261022_185006/04_implementation_report.md",
    "reports/data_cleaning/run_20261022_185006/05_validation_report.md",
    "reports/data_cleaning/run_20261022_185006/06_final_data_quality_report.md",
    "reports/data_cleaning/run_20261022_185006/06_cleaning_handoff.md",
    "reports/data_cleaning/run_20261022_185006/07_resume_reference_check.md",
]


def combined_markdown() -> str:
    stamp = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M")
    parts = [
        "# SD6105 Markdown 同步文档",
        "",
        f"生成时间：{stamp}（亚洲/新加坡）。",
        "",
        "本文件把仓库里的 Markdown 汇总成一份 Word 文档，供 WPS 打开。各 `.md` 文件仍然单独保存。更新 Markdown 后，在仓库根目录运行 `python3 scripts/sync_md_to_doc.py`。",
        "",
        "来源文件：",
        "",
    ]
    for relative in MARKDOWN_FILES:
        parts.append(f"- `{relative}`")
    parts.append("")
    for relative in MARKDOWN_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"Missing Markdown file: {relative}")
        text = path.read_text(encoding="utf-8").strip()
        parts.extend(
            [
                "",
                "---",
                "",
                f"# 文件：{relative}",
                "",
                text,
                "",
            ]
        )
    return "\n".join(parts) + "\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        source = work / "combined.md"
        docx = work / "MD.docx"
        source.write_text(combined_markdown(), encoding="utf-8")
        subprocess.run(
            ["pandoc", str(source), "-o", str(docx), "--from", "markdown", "--to", "docx"],
            check=True,
        )
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--norestore",
                "--convert-to",
                "doc",
                "--outdir",
                str(work),
                str(docx),
            ],
            check=True,
        )
        produced = work / "MD.doc"
        if not produced.is_file():
            raise SystemExit("LibreOffice did not write MD.doc")
        OUTPUT.write_bytes(produced.read_bytes())
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes) from {len(MARKDOWN_FILES)} Markdown files.")


if __name__ == "__main__":
    main()
