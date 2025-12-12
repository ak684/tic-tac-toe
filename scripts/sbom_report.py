#!/usr/bin/env python3
"""
SBOM (Software Bill of Materials) Report Generator

Generates a comprehensive SBOM for the repository and uses AI to analyze
security implications, outdated dependencies, and license compliance.

Environment Variables:
    LLM_API_KEY: API key for the LLM (required for detailed analysis)
    LLM_MODEL: Model to use (default: anthropic/claude-sonnet-4-5-20250929)
    LLM_BASE_URL: Optional base URL for LLM API
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openhands.sdk import LLM, Conversation, get_logger
from openhands.tools.preset.default import get_default_agent

logger = get_logger(__name__)


def install_syft() -> bool:
    """Install syft SBOM generator if not present."""
    # Check if syft is already installed
    result = subprocess.run(["which", "syft"], capture_output=True)
    if result.returncode == 0:
        logger.info("syft is already installed")
        return True

    logger.info("Installing syft...")
    try:
        # Install syft using the official install script
        install_cmd = "curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin"
        result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to install syft: {result.stderr}")
            return False
        logger.info("syft installed successfully")
        return True
    except Exception as e:
        logger.error(f"Error installing syft: {e}")
        return False


def generate_sbom(repo_root: Path) -> dict | None:
    """Generate SBOM using syft and return parsed JSON."""
    sbom_path = repo_root / "reports" / "sbom-raw.json"
    sbom_path.parent.mkdir(exist_ok=True)

    logger.info("Generating SBOM with syft...")
    try:
        result = subprocess.run(
            ["syft", str(repo_root), "-o", f"json={sbom_path}"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode != 0:
            logger.error(f"syft failed: {result.stderr}")
            return None

        # Parse the generated SBOM
        with open(sbom_path) as f:
            sbom_data = json.load(f)

        logger.info(f"SBOM generated: {len(sbom_data.get('artifacts', []))} packages found")
        return sbom_data

    except subprocess.TimeoutExpired:
        logger.error("syft timed out after 5 minutes")
        return None
    except Exception as e:
        logger.error(f"Error generating SBOM: {e}")
        return None


def summarize_sbom(sbom_data: dict) -> dict:
    """Extract summary statistics from SBOM data."""
    artifacts = sbom_data.get("artifacts", [])

    # Count by type
    by_type = {}
    by_license = {}
    packages = []

    for artifact in artifacts:
        pkg_type = artifact.get("type", "unknown")
        by_type[pkg_type] = by_type.get(pkg_type, 0) + 1

        # Extract licenses
        licenses = artifact.get("licenses", [])
        for lic in licenses:
            lic_name = lic.get("value", "unknown") if isinstance(lic, dict) else str(lic)
            by_license[lic_name] = by_license.get(lic_name, 0) + 1

        # Store package info
        packages.append({
            "name": artifact.get("name", "unknown"),
            "version": artifact.get("version", "unknown"),
            "type": pkg_type,
            "licenses": [l.get("value", str(l)) if isinstance(l, dict) else str(l) for l in licenses],
        })

    return {
        "total_packages": len(artifacts),
        "by_type": by_type,
        "by_license": by_license,
        "packages": packages,
    }


def generate_basic_report(repo_root: Path, summary: dict) -> str:
    """Generate a basic SBOM report without LLM analysis."""
    report = f"""# SBOM Report

**Repository:** {repo_root.name}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
**Total Packages:** {summary['total_packages']}

---

## Package Types

| Type | Count |
|------|-------|
"""
    for pkg_type, count in sorted(summary["by_type"].items(), key=lambda x: -x[1]):
        report += f"| {pkg_type} | {count} |\n"

    report += """
---

## License Distribution

| License | Count |
|---------|-------|
"""
    for license_name, count in sorted(summary["by_license"].items(), key=lambda x: -x[1])[:15]:
        report += f"| {license_name} | {count} |\n"

    if len(summary["by_license"]) > 15:
        report += f"| ... and {len(summary['by_license']) - 15} more | |\n"

    report += """
---

## Top Packages

| Package | Version | Type | License |
|---------|---------|------|---------|
"""
    for pkg in summary["packages"][:30]:
        licenses = ", ".join(pkg["licenses"][:2]) if pkg["licenses"] else "Unknown"
        report += f"| {pkg['name']} | {pkg['version']} | {pkg['type']} | {licenses} |\n"

    if len(summary["packages"]) > 30:
        report += f"\n*... and {len(summary['packages']) - 30} more packages*\n"

    report += """
---

*Generated by SBOM Pipeline*
"""
    return report


def generate_report_with_agent(repo_root: Path, summary: dict) -> str:
    """Use OpenHands agent to analyze SBOM and generate detailed report."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.error("LLM_API_KEY not set, generating basic report only")
        return None

    model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929")
    base_url = os.getenv("LLM_BASE_URL")

    llm_config = {
        "model": model,
        "api_key": api_key,
        "usage_id": "sbom_report",
        "drop_params": True,
    }
    if base_url:
        llm_config["base_url"] = base_url

    llm = LLM(**llm_config)
    agent = get_default_agent(llm=llm, cli_mode=True)
    conversation = Conversation(agent=agent, workspace=str(repo_root))

    # Prepare package list for analysis (limit to avoid token overflow)
    top_packages = summary["packages"][:100]
    packages_json = json.dumps(top_packages, indent=2)

    prompt = f"""Generate a CONCISE SBOM security and compliance report for this repository.

IMPORTANT: You are running in a CI environment where terminal commands may timeout or hang.
Always prefer using file_editor over terminal for all file read/write operations.

SBOM SUMMARY:
- Total Packages: {summary['total_packages']}
- Package Types: {json.dumps(summary['by_type'])}
- License Distribution: {json.dumps(dict(list(summary['by_license'].items())[:20]))}

TOP PACKAGES (first 100):
{packages_json}

RAW SBOM FILE: reports/sbom-raw.json (full details available there)

ANALYSIS STEPS:
1. Review the package list for known problematic packages or very outdated versions
2. Check license distribution for copyleft (GPL, AGPL) vs permissive (MIT, Apache, BSD) licenses
3. Identify any license compliance concerns for commercial use
4. Note any packages that commonly have security issues

REPORT FORMAT - Save to: reports/sbom-{datetime.now().strftime('%Y-%m-%d')}.md

# SBOM Report — {repo_root.name} ({datetime.now().strftime('%Y-%m-%d')})

**Total Dependencies:** {summary['total_packages']}

## Executive Summary
[2-3 sentences: Overall health of dependencies, any critical concerns]

## Dependency Overview

| Category | Count | Notes |
|----------|-------|-------|
| Total Packages | {summary['total_packages']} | |
| [Type 1] | [count] | [brief note] |
| [Type 2] | [count] | [brief note] |

## License Compliance

| Risk Level | Licenses | Count | Commercial Impact |
|------------|----------|-------|-------------------|
| Low Risk | MIT, Apache-2.0, BSD | [count] | Safe for commercial use |
| Medium Risk | LGPL, MPL | [count] | [brief impact] |
| High Risk | GPL, AGPL | [count] | [brief impact] |
| Unknown | [list] | [count] | Requires review |

## Security Observations
[3-5 bullet points about potential security concerns based on package analysis]

## Recommendations

### 1. [Top Priority Action]
**Why:** [1 sentence]
**Action:** [What to do]

### 2. [Second Priority]
**Why:** [1 sentence]
**Action:** [What to do]

### 3. [Third Priority]
**Why:** [1 sentence]
**Action:** [What to do]

---

IMPORTANT CONSTRAINTS:
- Keep report under 100 lines
- Focus on actionable insights, not exhaustive lists
- Highlight actual risks, not theoretical ones
- The raw SBOM JSON is available in reports/sbom-raw.json for full details
"""

    conversation.send_message(prompt)
    conversation.run()

    return "Report generated by agent"


def main():
    """Main entry point."""
    repo_root = Path.cwd()
    logger.info(f"Generating SBOM for: {repo_root}")

    # Ensure reports directory exists
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Install syft if needed
    if not install_syft():
        logger.error("Failed to install syft, cannot generate SBOM")
        sys.exit(1)

    # Generate SBOM
    sbom_data = generate_sbom(repo_root)
    if not sbom_data:
        logger.error("Failed to generate SBOM")
        sys.exit(1)

    # Summarize SBOM
    summary = summarize_sbom(sbom_data)
    logger.info(f"SBOM summary: {summary['total_packages']} packages across {len(summary['by_type'])} types")

    # Generate report
    report_path = reports_dir / f"sbom-{datetime.now().strftime('%Y-%m-%d')}.md"
    api_key = os.getenv("LLM_API_KEY")

    if api_key:
        logger.info("Using OpenHands agent for detailed analysis...")
        try:
            generate_report_with_agent(repo_root, summary)
            # Verify agent created the report
            if not report_path.exists():
                logger.warning("Agent didn't create report, falling back to basic")
                report = generate_basic_report(repo_root, summary)
                report_path.write_text(report)
        except Exception as e:
            logger.error(f"Agent failed, falling back to basic report: {e}")
            report = generate_basic_report(repo_root, summary)
            report_path.write_text(report)
    else:
        logger.warning("LLM_API_KEY not set, generating basic report only")
        report = generate_basic_report(repo_root, summary)
        report_path.write_text(report)

    # Print summary
    print(f"\n{'='*50}")
    print(f"SBOM GENERATED: {summary['total_packages']} packages")
    print(f"Report saved to: {report_path}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
