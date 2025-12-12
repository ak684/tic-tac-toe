#!/usr/bin/env python3
"""
AI Readiness Report Generator

Analyzes a repository's AI-readiness and generates a scored report.

Categories (100 points total):
- README (10 pts): Project overview
- Agent Guidelines (30 pts): AGENTS.md, repo.md, etc.
- Agent Automation (30 pts): .openhands/skills/, setup.sh, etc.
- Test Infrastructure (30 pts): Test files and directories

Environment Variables:
    LLM_API_KEY: API key for the LLM (required for detailed analysis)
    LLM_MODEL: Model to use (default: anthropic/claude-sonnet-4-5-20250929)
    LLM_BASE_URL: Optional base URL for LLM API
"""

import json
import os
import traceback
from datetime import datetime
from pathlib import Path

from openhands.sdk import LLM, Conversation, get_logger
from openhands.tools.preset.default import get_default_agent

logger = get_logger(__name__)

# Files to check for AI readiness
AI_READINESS_FILES = {
    "README.md": {
        "name": "README",
        "description": "Project overview and getting started guide",
        "weight": 10,
        "alternatives": ["readme.md", "README", "README.rst"],
    },
    ".openhands/skills/repo.md": {
        "name": "Agent Guidelines",
        "description": "Static instructions for AI agents (REPO.md, AGENTS.md, etc.)",
        "weight": 30,
        "alternatives": [
            ".openhands/microagents/repo.md",
            "AGENTS.md",
        ],
    },
    ".openhands/skills/": {
        "name": "Agent Automation",
        "description": "Setup scripts, task-specific commands, and automation for AI agents",
        "weight": 30,
        "alternatives": [
            ".openhands/microagents/",
            ".openhands/setup.sh",
        ],
        "exclude_files": ["repo.md"],  # Don't count repo.md - that's covered by Agent Guidelines
    },
    "tests/": {
        "name": "Test Infrastructure",
        "description": "Tests that allow AI agents to verify their changes",
        "weight": 30,
        "alternatives": [
            "test/",
            "__tests__/",
            "spec/",
            "e2e/",
            "integration/",
            "cypress/",
            "playwright/",
        ],
    },
}


def path_exists(full_path: Path, exclude_files: list[str] | None = None) -> bool:
    """Check if path exists as file or non-empty directory.

    Args:
        full_path: Path to check
        exclude_files: For directories, don't count these filenames when checking if non-empty
    """
    if full_path.is_file():
        return True
    if full_path.is_dir():
        try:
            if exclude_files:
                # Directory must have files OTHER than the excluded ones
                for item in full_path.iterdir():
                    if item.name not in exclude_files:
                        return True
                return False
            else:
                return any(full_path.iterdir())
        except PermissionError:
            return False
    return False


def glob_exists(repo_root: Path, pattern: str) -> bool:
    """Check if any files match the glob pattern."""
    return any(repo_root.glob(pattern))


def is_glob_pattern(path: str) -> bool:
    """Check if path contains glob characters."""
    return "*" in path or "?" in path or "[" in path


def scan_files(repo_root: Path) -> dict:
    """Scan the repository for AI readiness files, including alternatives."""
    results = {}

    for file_path, info in AI_READINESS_FILES.items():
        alternatives = info.get("alternatives", [])
        exclude_files = info.get("exclude_files")

        # Check primary path and alternatives
        paths_to_check = [file_path] + alternatives
        found_path = None

        for check_path in paths_to_check:
            if is_glob_pattern(check_path):
                if glob_exists(repo_root, check_path):
                    found_path = check_path
                    break
            else:
                full_path = repo_root / check_path
                if path_exists(full_path, exclude_files):
                    found_path = check_path
                    break

        if found_path:
            if is_glob_pattern(found_path):
                matching_files = list(repo_root.glob(found_path))
                results[file_path] = {
                    **info,
                    "exists": True,
                    "found_at": found_path,
                    "file_count": len(matching_files),
                }
            else:
                full_path = repo_root / found_path
                if full_path.is_dir():
                    # Count files, excluding any in exclude_files
                    file_count = sum(
                        1 for f in full_path.rglob("*")
                        if f.is_file() and (not exclude_files or f.name not in exclude_files)
                    )
                    results[file_path] = {
                        **info,
                        "exists": True,
                        "found_at": found_path,
                        "file_count": file_count,
                    }
                else:
                    content = full_path.read_text(errors="ignore")
                    results[file_path] = {
                        **info,
                        "exists": True,
                        "found_at": found_path,
                        "size": len(content),
                        "lines": content.count("\n") + 1,
                    }
        else:
            results[file_path] = {**info, "exists": False}

    return results


def calculate_basic_score(scan_results: dict) -> tuple[int, int]:
    """Calculate basic score based on file presence."""
    earned = 0
    possible = 0

    for path, info in scan_results.items():
        weight = info.get("weight", 10)
        possible += weight
        if info.get("exists", False):
            earned += weight

    return earned, possible


def generate_report_with_agent(repo_root: Path, scan_results: dict, score_earned: int, score_possible: int) -> str:
    """Use OpenHands agent to analyze files and generate detailed report."""

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.error("LLM_API_KEY not set, generating basic report only")
        return None

    model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929")
    base_url = os.getenv("LLM_BASE_URL")

    llm_config = {
        "model": model,
        "api_key": api_key,
        "usage_id": "ai_readiness_report",
        "drop_params": True,
    }
    if base_url:
        llm_config["base_url"] = base_url

    llm = LLM(**llm_config)

    agent = get_default_agent(llm=llm, cli_mode=True)
    conversation = Conversation(agent=agent, workspace=str(repo_root))

    # Build context about what files exist
    existing_files = [p for p, info in scan_results.items() if info.get("exists")]
    missing_files = [p for p, info in scan_results.items() if not info.get("exists")]
    score_pct = int((score_earned / score_possible * 100) if score_possible > 0 else 0)

    prompt = f"""Generate a CONCISE AI-readiness report for this repository.

IMPORTANT: You are running in a CI environment where terminal commands may timeout.
Always prefer using file_editor over terminal/bash for all file operations.

AI-READINESS SCORE: {score_pct}% ({score_earned}/{score_possible} points)

EXISTING: {json.dumps(existing_files)}
MISSING: {json.dumps(missing_files)}

CATEGORIES (weights):
- Documentation (10 pts): README quality
- Agent Guidelines (30 pts): AGENTS.md, repo.md - conventions/gotchas for AI agents
- Agent Automation (30 pts): .openhands/skills/, setup.sh - scripts agents can run
- Test Infrastructure (30 pts): Test coverage for verifying changes

STEPS:
1. Quickly explore the codebase structure and key files
2. Assess each category briefly
3. Generate a SHORT report (target: under 150 lines)

REPORT FORMAT:

# AI-Readiness Report — [repo-name] ({datetime.now().strftime('%Y-%m-%d')})

**Score: {score_pct}%** ({score_earned}/{score_possible} points)

## Summary
[2-3 sentences: what can/can't AI agents do effectively with this codebase?]

## Findings

| Category | Status | AI Agent Impact |
|----------|--------|-----------------|
| Documentation (10 pts) | [Present/Missing] | [1 sentence] |
| Agent Guidelines (30 pts) | [Present/Missing] | [1 sentence] |
| Agent Automation (30 pts) | [Present/Missing] | [1 sentence] |
| Test Infrastructure (30 pts) | [Present/Missing] | [1 sentence] |

## Top 3 Actions

### 1. [Action Title]
**Category:** [which category]
**Why:** [1-2 sentences - how this helps AI agents]
**What to create:** [Brief description - NOT the full content, just what file/doc to create]

### 2. [Action Title]
**Category:** [which category]
**Why:** [1-2 sentences]
**What to create:** [Brief description]

### 3. [Action Title]
**Category:** [which category]
**Why:** [1-2 sentences]
**What to create:** [Brief description]

IMPORTANT CONSTRAINTS:
- Keep the report CONCISE - under 150 lines
- Do NOT include full code examples, troubleshooting guides, or decision trees
- Just describe WHAT to create, not the full content
- Every finding must explain the AI agent impact in 1-2 sentences max
- Save to: reports/ai-readiness-{datetime.now().strftime('%Y-%m-%d')}.md
"""

    conversation.send_message(prompt)
    conversation.run()

    return "Report generated by agent"


def generate_basic_report(repo_root: Path, scan_results: dict) -> str:
    """Generate a basic report without LLM analysis."""
    earned, possible = calculate_basic_score(scan_results)
    score_pct = (earned / possible * 100) if possible > 0 else 0

    report = f"""# AI Readiness Report

**Repository:** {repo_root.name}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
**Overall Score:** {score_pct:.0f}% ({earned}/{possible} points)

---

## File Checklist

| File | Status | Details |
|------|--------|---------|
"""

    for path, info in scan_results.items():
        status = "Present" if info.get("exists") else "Missing"
        emoji = "+" if info.get("exists") else "-"

        if info.get("exists"):
            if "file_count" in info:
                details = f"{info.get('file_count', 0)} files"
            elif "lines" in info:
                details = f"{info.get('lines', 0)} lines"
            else:
                details = info.get("details", "Found")
        else:
            details = f"*{info.get('description')}*"

        report += f"| `{path}` | {emoji} {status} | {details} |\n"

    report += """
---

## Recommendations

"""

    # Generate recommendations based on missing files
    missing = [(p, info) for p, info in scan_results.items() if not info.get("exists")]
    missing.sort(key=lambda x: x[1].get("weight", 0), reverse=True)

    if missing:
        for i, (path, info) in enumerate(missing[:3], 1):
            report += f"{i}. **Add `{path}`**: {info.get('description')}\n"
    else:
        report += "All AI readiness files are present. Consider reviewing each for completeness.\n"

    report += """
---

*Generated by AI Readiness Pipeline*
"""

    return report


def save_basic_report(repo_root: Path, scan_results: dict) -> Path:
    """Generate and save basic report, return the path."""
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    report = generate_basic_report(repo_root, scan_results)
    report_path = reports_dir / f"ai-readiness-{datetime.now().strftime('%Y-%m-%d')}.md"
    report_path.write_text(report)
    logger.info(f"Basic report saved to: {report_path}")
    return report_path


def main():
    """Main entry point."""
    repo_root = Path.cwd()
    logger.info(f"Scanning repository: {repo_root}")

    # Scan for AI readiness files
    scan_results = scan_files(repo_root)
    earned, possible = calculate_basic_score(scan_results)
    logger.info(f"Basic scan complete: {earned}/{possible} points")

    # Ensure reports directory exists
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"ai-readiness-{datetime.now().strftime('%Y-%m-%d')}.md"

    # Try to generate detailed report with agent
    api_key = os.getenv("LLM_API_KEY")

    if api_key:
        logger.info("Using OpenHands agent for detailed analysis...")
        try:
            generate_report_with_agent(repo_root, scan_results, earned, possible)
            # Verify agent created the report
            if not report_path.exists():
                logger.warning("Agent didn't create report, falling back to basic")
                save_basic_report(repo_root, scan_results)
        except Exception as e:
            logger.error(f"Agent failed, falling back to basic report: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            save_basic_report(repo_root, scan_results)
    else:
        logger.warning("LLM_API_KEY not set, generating basic report only")
        save_basic_report(repo_root, scan_results)

    # Print summary
    score_pct = (earned / possible * 100) if possible > 0 else 0
    print(f"\n{'='*50}")
    print(f"AI READINESS SCORE: {score_pct:.0f}%")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
