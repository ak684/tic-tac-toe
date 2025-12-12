#!/usr/bin/env python3
"""
CVE (Common Vulnerabilities and Exposures) Scanner & Auto-Fixer

Scans the repository for known CVEs using grype and uses AI to:
1. Analyze and prioritize vulnerabilities
2. Automatically apply conservative, targeted fixes (dependency bumps)
3. Generate a detailed security report

Environment Variables:
    LLM_API_KEY: API key for the LLM (required)
    LLM_MODEL: Model to use (default: anthropic/claude-sonnet-4-5-20250929)
    LLM_BASE_URL: Optional base URL for LLM API
    CVE_FAIL_ON_CRITICAL: Set to "true" to fail build on critical CVEs
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


def install_grype() -> bool:
    """Install grype CVE scanner if not present."""
    result = subprocess.run(["which", "grype"], capture_output=True)
    if result.returncode == 0:
        logger.info("grype is already installed")
        return True

    logger.info("Installing grype...")
    try:
        install_cmd = "curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin"
        result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to install grype: {result.stderr}")
            return False
        logger.info("grype installed successfully")
        return True
    except Exception as e:
        logger.error(f"Error installing grype: {e}")
        return False


def run_grype_scan(repo_root: Path) -> dict | None:
    """Run grype CVE scan and return parsed JSON results."""
    scan_path = repo_root / "reports" / "cve-raw.json"
    scan_path.parent.mkdir(exist_ok=True)

    logger.info("Scanning for CVEs with grype...")
    try:
        result = subprocess.run(
            ["grype", f"dir:{repo_root}", "-o", "json", "--file", str(scan_path)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        # grype exits with 0 even when vulnerabilities found
        if result.returncode != 0 and "no vulnerabilities found" not in result.stderr.lower():
            logger.warning(f"grype returned non-zero: {result.stderr}")

        if not scan_path.exists():
            logger.error("grype did not create output file")
            return None

        with open(scan_path) as f:
            scan_data = json.load(f)

        matches = scan_data.get("matches", [])
        logger.info(f"CVE scan complete: {len(matches)} vulnerabilities found")
        return scan_data

    except subprocess.TimeoutExpired:
        logger.error("grype timed out after 10 minutes")
        return None
    except Exception as e:
        logger.error(f"Error running grype scan: {e}")
        return None


def summarize_cves(scan_data: dict) -> dict:
    """Extract summary statistics from grype scan results."""
    matches = scan_data.get("matches", [])

    by_severity = {"Critical": [], "High": [], "Medium": [], "Low": [], "Negligible": [], "Unknown": []}
    by_package = {}
    all_cves = []

    for match in matches:
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})

        severity = vuln.get("severity", "Unknown")
        cve_id = vuln.get("id", "Unknown")
        pkg_name = artifact.get("name", "unknown")
        pkg_version = artifact.get("version", "unknown")
        pkg_type = artifact.get("type", "unknown")
        fix_versions = vuln.get("fix", {}).get("versions", [])

        cve_info = {
            "id": cve_id,
            "severity": severity,
            "package": pkg_name,
            "version": pkg_version,
            "type": pkg_type,
            "fix_versions": fix_versions,
            "description": vuln.get("description", ""),
            "urls": vuln.get("urls", []),
        }

        all_cves.append(cve_info)
        by_severity.get(severity, by_severity["Unknown"]).append(cve_info)

        pkg_key = f"{pkg_name}@{pkg_version}"
        if pkg_key not in by_package:
            by_package[pkg_key] = {
                "name": pkg_name,
                "version": pkg_version,
                "type": pkg_type,
                "cves": [],
                "max_severity": "Unknown",
                "fix_versions": set(),
            }
        by_package[pkg_key]["cves"].append(cve_info)
        by_package[pkg_key]["fix_versions"].update(fix_versions)

        # Track max severity for package
        severity_order = ["Critical", "High", "Medium", "Low", "Negligible", "Unknown"]
        current_max = by_package[pkg_key]["max_severity"]
        if severity_order.index(severity) < severity_order.index(current_max):
            by_package[pkg_key]["max_severity"] = severity

    # Convert fix_versions sets to lists for JSON serialization
    for pkg_key in by_package:
        by_package[pkg_key]["fix_versions"] = list(by_package[pkg_key]["fix_versions"])

    return {
        "total_cves": len(matches),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "by_severity_details": by_severity,
        "by_package": by_package,
        "all_cves": all_cves,
    }


def generate_basic_report(repo_root: Path, summary: dict) -> str:
    """Generate a basic CVE report without LLM analysis."""
    report = f"""# CVE Security Report

**Repository:** {repo_root.name}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
**Total Vulnerabilities:** {summary['total_cves']}

---

## Severity Summary

| Severity | Count |
|----------|-------|
"""
    for severity in ["Critical", "High", "Medium", "Low", "Negligible", "Unknown"]:
        count = summary["by_severity"].get(severity, 0)
        if count > 0:
            report += f"| {severity} | {count} |\n"

    if summary["total_cves"] == 0:
        report += "\nNo vulnerabilities found.\n"
        return report

    report += """
---

## Critical & High Severity Vulnerabilities

"""
    critical_high = summary["by_severity_details"]["Critical"] + summary["by_severity_details"]["High"]
    if not critical_high:
        report += "No critical or high severity vulnerabilities found.\n"
    else:
        report += "| CVE ID | Severity | Package | Current | Fix Available |\n"
        report += "|--------|----------|---------|---------|---------------|\n"
        for cve in critical_high[:20]:
            fix = ", ".join(cve["fix_versions"][:2]) if cve["fix_versions"] else "No fix"
            report += f"| {cve['id']} | {cve['severity']} | {cve['package']} | {cve['version']} | {fix} |\n"
        if len(critical_high) > 20:
            report += f"\n*... and {len(critical_high) - 20} more critical/high vulnerabilities*\n"

    report += """
---

## Packages Requiring Updates

"""
    # Sort packages by severity
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Negligible": 4, "Unknown": 5}
    sorted_packages = sorted(
        summary["by_package"].values(),
        key=lambda x: (severity_order.get(x["max_severity"], 5), -len(x["cves"]))
    )

    if not sorted_packages:
        report += "No package updates required.\n"
    else:
        report += "| Package | Current | CVE Count | Max Severity | Suggested Fix |\n"
        report += "|---------|---------|-----------|--------------|---------------|\n"
        for pkg in sorted_packages[:15]:
            fix = ", ".join(list(pkg["fix_versions"])[:2]) if pkg["fix_versions"] else "Review needed"
            report += f"| {pkg['name']} | {pkg['version']} | {len(pkg['cves'])} | {pkg['max_severity']} | {fix} |\n"
        if len(sorted_packages) > 15:
            report += f"\n*... and {len(sorted_packages) - 15} more packages*\n"

    report += """
---

## Recommended Actions

1. **Update Critical/High packages first** - Focus on packages with available fixes
2. **Review packages without fixes** - Consider alternatives or mitigation strategies
3. **Enable automated scanning** - Run CVE scans on every PR

---

*Generated by CVE Security Pipeline*
"""
    return report


def generate_report_and_fix(repo_root: Path, summary: dict) -> str:
    """Use OpenHands agent to analyze CVEs, apply fixes, and generate report."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.error("LLM_API_KEY not set, generating basic report only")
        return None

    model = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929")
    base_url = os.getenv("LLM_BASE_URL")

    llm_config = {
        "model": model,
        "api_key": api_key,
        "usage_id": "cve_report",
        "drop_params": True,
    }
    if base_url:
        llm_config["base_url"] = base_url

    llm = LLM(**llm_config)
    agent = get_default_agent(llm=llm, cli_mode=True)
    conversation = Conversation(agent=agent, workspace=str(repo_root))

    # Prepare vulnerability data for analysis (limit to most critical)
    critical_high = (
        summary["by_severity_details"]["Critical"] +
        summary["by_severity_details"]["High"]
    )[:30]

    # Get package manager files for context
    pkg_files = []
    for pattern in ["package.json", "package-lock.json", "requirements.txt", "Pipfile", "poetry.lock", "Cargo.toml", "go.mod"]:
        if (repo_root / pattern).exists():
            pkg_files.append(pattern)

    prompt = f"""You are a security engineer. Scan the CVE report, apply safe fixes, and generate a security report.

IMPORTANT: You are running in a CI environment where terminal commands may timeout or hang.
Always prefer using file_editor over terminal for all file read/write operations.

CVE SCAN SUMMARY:
- Total Vulnerabilities: {summary['total_cves']}
- Critical: {summary['by_severity'].get('Critical', 0)}
- High: {summary['by_severity'].get('High', 0)}
- Medium: {summary['by_severity'].get('Medium', 0)}
- Low: {summary['by_severity'].get('Low', 0)}

PACKAGE MANAGER FILES FOUND: {json.dumps(pkg_files)}

RAW CVE DATA: reports/cve-raw.json (full grype scan results)

TOP CRITICAL/HIGH VULNERABILITIES:
{json.dumps(critical_high, indent=2)}

PACKAGES AFFECTED:
{json.dumps(list(summary['by_package'].values())[:20], indent=2, default=str)}

=== YOUR TASK ===

STEP 1: APPLY FIXES
1. Read the package manager files (package.json, requirements.txt, etc.)
2. For each CVE with an available fix version, update the dependency:
   - Use the MINIMUM version that fixes the CVE (not latest)
   - Prefer patch bumps over minor bumps when possible
   - Only fix direct dependencies, not transitive ones
3. After editing package.json, run: npm install --package-lock-only
   (or equivalent for other package managers)

STEP 2: GENERATE REPORT
Save to: reports/cve-{datetime.now().strftime('%Y-%m-%d')}.md

# CVE Security Report - {repo_root.name}

**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Total Vulnerabilities Found:** {summary['total_cves']}

| Critical | High | Medium | Low |
|----------|------|--------|-----|
| {summary['by_severity'].get('Critical', 0)} | {summary['by_severity'].get('High', 0)} | {summary['by_severity'].get('Medium', 0)} | {summary['by_severity'].get('Low', 0)} |

## Executive Summary
[2-3 sentences on security posture]

## Fixes Applied

| Package | Previous | Updated To | CVEs Fixed | Risk |
|---------|----------|------------|------------|------|
| example | 1.0.0 | 1.0.1 | CVE-2024-XXXX | Low (patch bump) |

## Critical/High CVEs Addressed

### CVE-XXXX-XXXXX
- **Package:** name@version
- **Severity:** Critical/High
- **Fix:** Updated to version X.Y.Z
- **Impact:** [1 sentence]

## Remaining Vulnerabilities

[List any CVEs that couldn't be fixed and why - no fix available, breaking change risk, etc.]

## Recommendations

[2-3 actionable next steps]

---

CONSTRAINTS:
- Apply fixes conservatively - minimum version bumps only
- Document everything you change
- If a fix might break things, note it but still apply if it's Critical/High
- Keep report concise (<100 lines)
"""

    conversation.send_message(prompt)
    conversation.run()

    return "Report and fixes generated by agent"


def main():
    """Main entry point."""
    repo_root = Path.cwd()
    logger.info(f"Scanning repository for CVEs: {repo_root}")

    # Ensure reports directory exists
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Install grype if needed
    if not install_grype():
        logger.error("Failed to install grype, cannot scan for CVEs")
        sys.exit(1)

    # Run CVE scan
    scan_data = run_grype_scan(repo_root)
    if not scan_data:
        logger.error("Failed to run CVE scan")
        sys.exit(1)

    # Summarize findings
    summary = summarize_cves(scan_data)
    logger.info(f"CVE summary: {summary['total_cves']} vulnerabilities found")
    logger.info(f"  Critical: {summary['by_severity'].get('Critical', 0)}")
    logger.info(f"  High: {summary['by_severity'].get('High', 0)}")
    logger.info(f"  Medium: {summary['by_severity'].get('Medium', 0)}")
    logger.info(f"  Low: {summary['by_severity'].get('Low', 0)}")

    # Generate report and apply fixes
    report_path = reports_dir / f"cve-{datetime.now().strftime('%Y-%m-%d')}.md"
    api_key = os.getenv("LLM_API_KEY")

    if api_key:
        logger.info("Using OpenHands agent to analyze CVEs, apply fixes, and generate report...")
        try:
            generate_report_and_fix(repo_root, summary)
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
        logger.warning("LLM_API_KEY not set, generating basic report only (no auto-fix)")
        report = generate_basic_report(repo_root, summary)
        report_path.write_text(report)

    # Print summary
    print(f"\n{'='*60}")
    print(f"CVE SCAN & FIX COMPLETE")
    print(f"  Vulnerabilities found: {summary['total_cves']}")
    print(f"  Critical: {summary['by_severity'].get('Critical', 0)}")
    print(f"  High: {summary['by_severity'].get('High', 0)}")
    print(f"  Report: {report_path}")
    print(f"{'='*60}\n")

    # Exit with error if critical vulnerabilities found (useful for CI gates)
    critical_count = summary['by_severity'].get('Critical', 0)
    if critical_count > 0 and os.getenv("CVE_FAIL_ON_CRITICAL", "false").lower() == "true":
        logger.error(f"Failing build: {critical_count} critical vulnerabilities found")
        sys.exit(1)


if __name__ == "__main__":
    main()
