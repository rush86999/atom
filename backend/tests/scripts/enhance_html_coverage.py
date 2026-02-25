#!/usr/bin/env python3
"""
HTML Coverage Report Enhancer

Post-processes pytest-cov HTML reports to add branch coverage visualization,
color coding, and summary dashboard.

Usage:
    python backend/tests/scripts/enhance_html_coverage.py [--html-path PATH]

Examples:
    python backend/tests/scripts/enhance_html_coverage.py
    python backend/tests/scripts/enhance_html_coverage.py --html-path custom/htmlcov/index.html
"""

import argparse
import re
from pathlib import Path
from typing import Optional


def enhance_html_report(html_path: Path) -> bool:
    """
    Enhance HTML coverage report with branch visualization and dashboard.

    Args:
        html_path: Path to htmlcov/index.html

    Returns:
        True if successful, False otherwise
    """
    if not html_path.exists():
        print(f"Error: HTML report not found: {html_path}")
        return False

    # Read HTML content
    with open(html_path, 'r') as f:
        html_content = f.read()

    # Enhance the HTML
    enhanced_html = add_color_coding(html_content)
    enhanced_html = add_dashboard(enhanced_html)
    enhanced_html = add_branch_toggle(enhanced_html)

    # Write enhanced version
    with open(html_path, 'w') as f:
        f.write(enhanced_html)

    print(f"Enhanced HTML report: {html_path}")
    return True


def add_color_coding(html_content: str) -> str:
    """
    Add CSS for coverage color coding.

    Args:
        html_content: Original HTML content

    Returns:
        HTML with added color coding CSS
    """
    css_injection = """
<style>
/* Enhanced Coverage Color Coding */
.coverage-excellent {
    background-color: #d4edda !important;
    color: #155724 !important;
}

.coverage-good {
    background-color: #fff3cd !important;
    color: #856404 !important;
}

.coverage-warning {
    background-color: #f8d7da !important;
    color: #721c24 !important;
}

.coverage-critical {
    background-color: #f5c6cb !important;
    color: #721c24 !important;
    font-weight: bold;
}

/* Branch coverage styling */
.branch-covered {
    background-color: #28a745;
    color: white;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
}

.branch-missing {
    background-color: #dc3545;
    color: white;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
}

.branch-partial {
    background-color: #ffc107;
    color: #212529;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
}

/* Dashboard styles */
.coverage-dashboard {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 20px;
    color: white;
}

.dashboard-badge {
    display: inline-block;
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: bold;
    margin-right: 10px;
    background-color: rgba(255, 255, 255, 0.2);
}

.metric-card {
    background-color: white;
    color: #333;
    padding: 15px;
    border-radius: 8px;
    margin: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.metric-value {
    font-size: 2em;
    font-weight: bold;
    color: #667eea;
}

.metric-label {
    font-size: 0.9em;
    color: #666;
    text-transform: uppercase;
}
</style>
"""

    # Insert CSS before closing </head> tag
    if "</head>" in html_content:
        return html_content.replace("</head>", css_injection + "</head>")
    else:
        return css_injection + html_content


def add_dashboard(html_content: str) -> str:
    """
    Add summary dashboard at top of HTML report.

    Args:
        html_content: Original HTML content

    Returns:
        HTML with added dashboard
    """
    dashboard_html = """
<div class="coverage-dashboard">
    <h2 style="margin-top: 0;">Coverage Summary Dashboard</h2>
    <div style="display: flex; flex-wrap: wrap;">
        <div class="metric-card">
            <div class="metric-label">Overall Coverage</div>
            <div class="metric-value" id="overall-coverage">Loading...</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Branch Coverage</div>
            <div class="metric-value" id="branch-coverage">Loading...</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Modules Tested</div>
            <div class="metric-value" id="modules-tested">Loading...</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Uncovered Lines</div>
            <div class="metric-value" id="uncovered-lines">Loading...</div>
        </div>
    </div>
</div>

<script>
// Extract metrics from the page
(function() {
    const tables = document.querySelectorAll('table');
    let overallCoverage = 0;
    let branchCoverage = 0;
    let modulesTested = 0;
    let uncoveredLines = 0;

    // Try to find coverage totals
    const pctRows = document.querySelectorAll('tr[data-percent-covered]');
    if (pctRows.length > 0) {
        let totalPct = 0;
        pctRows.forEach(row => {
            totalPct += parseFloat(row.getAttribute('data-percent-covered') || 0);
            modulesTested++;
        });
        overallCoverage = (totalPct / pctRows.length).toFixed(1);
    }

    // Try to find branch coverage
    const branchElements = document.querySelectorAll('[data-branch-covered]');
    if (branchElements.length > 0) {
        let totalBranch = 0;
        branchElements.forEach(el => {
            totalBranch += parseFloat(el.getAttribute('data-branch-covered') || 0);
        });
        branchCoverage = (totalBranch / branchElements.length).toFixed(1);
    }

    // Update dashboard
    document.getElementById('overall-coverage').textContent = overallCoverage + '%';
    document.getElementById('branch-coverage').textContent = branchCoverage + '%';
    document.getElementById('modules-tested').textContent = modulesTested;
    document.getElementById('uncovered-lines').textContent = 'View Details';
})();
</script>
"""

    # Insert dashboard after opening <body> tag
    if "<body>" in html_content:
        return html_content.replace("<body>", "<body>" + dashboard_html)
    elif "<body " in html_content:
        return re.sub(r'<body[^>]*>', r'\g<0>' + dashboard_html, html_content, count=1)
    else:
        return dashboard_html + html_content


def add_branch_toggle(html_content: str) -> str:
    """
    Add JavaScript for branch visibility toggle.

    Args:
        html_content: Original HTML content

    Returns:
        HTML with added branch toggle functionality
    """
    toggle_script = """
<script>
// Branch coverage toggle functionality
(function() {
    // Create toggle button
    const toggleBtn = document.createElement('button');
    toggleBtn.textContent = 'Toggle Branch Details';
    toggleBtn.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        padding: 10px 20px;
        background-color: #667eea;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-weight: bold;
    `;

    toggleBtn.onclick = function() {
        const branchElements = document.querySelectorAll('.branch-covered, .branch-missing, .branch-partial');
        branchElements.forEach(el => {
            el.style.display = el.style.display === 'none' ? 'inline' : 'none';
        });
    };

    document.body.appendChild(toggleBtn);
})();
</script>
"""

    # Insert before closing </body> tag
    if "</body>" in html_content:
        return html_content.replace("</body>", toggle_script + "</body>")
    else:
        return html_content + toggle_script


def post_process_coverage_html() -> bool:
    """
    Post-process all HTML coverage files to add enhancements.

    Returns:
        True if successful
    """
    backend_dir = Path(__file__).parent.parent
    htmlcov_dir = backend_dir / "coverage_reports" / "html"

    if not htmlcov_dir.exists():
        print(f"HTML coverage directory not found: {htmlcov_dir}")
        return False

    # Enhance index.html
    index_html = htmlcov_dir / "index.html"
    if index_html.exists():
        enhance_html_report(index_html)
    else:
        print(f"Index HTML not found: {index_html}")
        return False

    print(f"\nEnhanced coverage report available at: file://{index_html}")
    return True


def main():
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Enhance HTML coverage reports with branch visualization"
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        default=None,
        help="Path to htmlcov/index.html (default: backend/tests/coverage_reports/html/index.html)"
    )

    args = parser.parse_args()

    if args.html_path:
        # Enhance specific HTML file
        success = enhance_html_report(args.html_path)
    else:
        # Enhance default coverage report
        success = post_process_coverage_html()

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
