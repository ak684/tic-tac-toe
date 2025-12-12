#!/usr/bin/env python3
"""
SBOM (Software Bill of Materials) Report Generator with CVE Scanning

Generates a comprehensive SBOM for the repository and uses AI to analyze
security implications, outdated dependencies, and license compliance.
Now includes CVE scanning via grype to ground security analysis in real data.

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


def run_cve_scan(repo_root: Path) -> dict | None:
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
        }

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
    }


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


def generate_basic_report(repo_root: Path, summary: dict, cve_summary: dict | None = None) -> str:
    """Generate a basic SBOM report without LLM analysis."""
    cve_total = cve_summary["total_cves"] if cve_summary else 0
    cve_critical = cve_summary["by_severity"].get("Critical", 0) if cve_summary else 0
    cve_high = cve_summary["by_severity"].get("High", 0) if cve_summary else 0

    report = f"""# SBOM Report

**Repository:** {repo_root.name}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
**Total Packages:** {summary['total_packages']}
**Total CVEs:** {cve_total} (Critical: {cve_critical}, High: {cve_high})

---

## Package Types

| Type | Count |
|------|-------|
"""
    for pkg_type, count in sorted(summary["by_type"].items(), key=lambda x: -x[1]):
        report += f"| {pkg_type} | {count} |\n"

    # Add CVE section if we have CVE data
    if cve_summary and cve_summary["total_cves"] > 0:
        report += """
---

## CVE Summary

| Severity | Count |
|----------|-------|
"""
        for severity in ["Critical", "High", "Medium", "Low", "Negligible"]:
            count = cve_summary["by_severity"].get(severity, 0)
            if count > 0:
                report += f"| {severity} | {count} |\n"

        # Show critical/high CVEs
        critical_high = (
            cve_summary["by_severity_details"]["Critical"] +
            cve_summary["by_severity_details"]["High"]
        )
        if critical_high:
            report += """
### Critical & High Severity Vulnerabilities

| CVE ID | Severity | Package | Version | Fix Available |
|--------|----------|---------|---------|---------------|
"""
            for cve in critical_high[:15]:
                fix = ", ".join(cve["fix_versions"][:2]) if cve["fix_versions"] else "No fix"
                report += f"| {cve['id']} | {cve['severity']} | {cve['package']} | {cve['version']} | {fix} |\n"
            if len(critical_high) > 15:
                report += f"\n*... and {len(critical_high) - 15} more critical/high vulnerabilities*\n"

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


def generate_report_with_agent(repo_root: Path, summary: dict, cve_summary: dict | None = None) -> str:
    """Use OpenHands agent to analyze SBOM and CVE data, generate detailed report."""
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

    # Prepare CVE data if available
    cve_section = ""
    cve_report_section = ""
    if cve_summary:
        critical_high = (
            cve_summary["by_severity_details"]["Critical"] +
            cve_summary["by_severity_details"]["High"]
        )[:20]
        cve_section = f"""
CVE SCAN RESULTS (from grype):
- Total Vulnerabilities: {cve_summary['total_cves']}
- Critical: {cve_summary['by_severity'].get('Critical', 0)}
- High: {cve_summary['by_severity'].get('High', 0)}
- Medium: {cve_summary['by_severity'].get('Medium', 0)}
- Low: {cve_summary['by_severity'].get('Low', 0)}

TOP CRITICAL/HIGH CVEs:
{json.dumps(critical_high, indent=2)}

VULNERABLE PACKAGES:
{json.dumps(list(cve_summary['by_package'].values())[:15], indent=2, default=str)}

RAW CVE FILE: reports/cve-raw.json (full grype scan results)
"""
        cve_report_section = f"""
## Security Vulnerabilities (CVE Scan)

| Severity | Count |
|----------|-------|
| Critical | {cve_summary['by_severity'].get('Critical', 0)} |
| High | {cve_summary['by_severity'].get('High', 0)} |
| Medium | {cve_summary['by_severity'].get('Medium', 0)} |
| Low | {cve_summary['by_severity'].get('Low', 0)} |

### Critical/High Vulnerabilities Requiring Immediate Action

| CVE ID | Package | Current Version | Fix Version | Severity |
|--------|---------|-----------------|-------------|----------|
[Fill from CVE data above - prioritize those WITH available fixes]

### Vulnerabilities Without Available Fixes
[List any critical/high CVEs that have no fix available yet - these need monitoring]
"""
    else:
        cve_section = "\nNOTE: CVE scan was not run or failed. Security observations will be based on package analysis only.\n"
        cve_report_section = """
## Security Observations
[3-5 bullet points about potential security concerns based on package analysis]
NOTE: CVE scanning was not available. Run with grype for actual vulnerability data.
"""

    prompt = f"""Generate a CONCISE SBOM security and compliance report for this repository.

IMPORTANT: You are running in a CI environment where terminal commands may timeout.
Always prefer using file_editor over terminal/bash for all file operations.

SBOM SUMMARY:
- Total Packages: {summary['total_packages']}
- Package Types: {json.dumps(summary['by_type'])}
- License Distribution: {json.dumps(dict(list(summary['by_license'].items())[:20]))}

TOP PACKAGES (first 100):
{packages_json}

RAW SBOM FILE: reports/sbom-raw.json (full details available there)
{cve_section}

ANALYSIS STEPS:
1. Review CVE scan results - prioritize Critical/High vulnerabilities with available fixes
2. Check license distribution for copyleft (GPL, AGPL) vs permissive (MIT, Apache, BSD) licenses
3. Identify any license compliance concerns for commercial use
4. Correlate SBOM packages with CVE data to identify which dependencies are most risky

REPORT FORMAT - Save to: reports/sbom-{datetime.now().strftime('%Y-%m-%d')}.md

# SBOM Report — {repo_root.name} ({datetime.now().strftime('%Y-%m-%d')})

**Total Dependencies:** {summary['total_packages']}
**Total CVEs:** {cve_summary['total_cves'] if cve_summary else 'N/A'} (Critical: {cve_summary['by_severity'].get('Critical', 0) if cve_summary else 'N/A'}, High: {cve_summary['by_severity'].get('High', 0) if cve_summary else 'N/A'})

## Executive Summary
[2-3 sentences: Overall security posture based on ACTUAL CVE data, not speculation]
{cve_report_section}

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

## Recommendations

### 1. [Top Priority - Usually a Critical CVE fix]
**Why:** [1 sentence referencing specific CVE if applicable]
**Action:** [Specific version to upgrade to]

### 2. [Second Priority]
**Why:** [1 sentence]
**Action:** [What to do]

### 3. [Third Priority]
**Why:** [1 sentence]
**Action:** [What to do]

---

IMPORTANT CONSTRAINTS:
- Keep report under 100 lines
- Base security recommendations on ACTUAL CVE data, not speculation
- Focus on actionable fixes - packages with available fix versions
- The raw SBOM JSON is in reports/sbom-raw.json, CVE data in reports/cve-raw.json
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

    # Run CVE scan with grype for real vulnerability data
    cve_summary = None
    if install_grype():
        cve_data = run_cve_scan(repo_root)
        if cve_data:
            cve_summary = summarize_cves(cve_data)
            logger.info(f"CVE scan: {cve_summary['total_cves']} vulnerabilities found")
            logger.info(f"  Critical: {cve_summary['by_severity'].get('Critical', 0)}")
            logger.info(f"  High: {cve_summary['by_severity'].get('High', 0)}")
        else:
            logger.warning("CVE scan failed, continuing without vulnerability data")
    else:
        logger.warning("Could not install grype, continuing without CVE scan")

    # Generate report
    report_path = reports_dir / f"sbom-{datetime.now().strftime('%Y-%m-%d')}.md"
    api_key = os.getenv("LLM_API_KEY")

    if api_key:
        logger.info("Using OpenHands agent for detailed analysis...")
        try:
            generate_report_with_agent(repo_root, summary, cve_summary)
            # Verify agent created the report
            if not report_path.exists():
                logger.warning("Agent didn't create report, falling back to basic")
                report = generate_basic_report(repo_root, summary, cve_summary)
                report_path.write_text(report)
        except Exception as e:
            logger.error(f"Agent failed, falling back to basic report: {e}")
            report = generate_basic_report(repo_root, summary, cve_summary)
            report_path.write_text(report)
    else:
        logger.warning("LLM_API_KEY not set, generating basic report only")
        report = generate_basic_report(repo_root, summary, cve_summary)
        report_path.write_text(report)

    # Print summary
    cve_info = ""
    if cve_summary:
        cve_info = f"\nCVEs found: {cve_summary['total_cves']} (Critical: {cve_summary['by_severity'].get('Critical', 0)}, High: {cve_summary['by_severity'].get('High', 0)})"

    print(f"\n{'='*60}")
    print(f"SBOM GENERATED: {summary['total_packages']} packages{cve_info}")
    print(f"Report saved to: {report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
