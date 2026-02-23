#!/usr/bin/env python3
"""
HTML Report Generator - Enhances pytest HTML reports with embedded screenshots.

Usage:
    python html_report_generator.py <report_file> [options]

Options:
    --screenshots DIR   Screenshots directory (default: artifacts/screenshots)
    --output FILE       Output HTML file (default: overwrite input)
    --embed             Embed screenshots as base64 (self-contained)
    --add-env           Add environment information to report
"""
import argparse
import base64
import os
import sys
from pathlib import Path


def embed_screenshots_in_html(report_file: str, screenshots_dir: str, output_file: str = None):
    """
    Embed screenshots directly into HTML report for self-contained viewing.

    Args:
        report_file: Path to pytest HTML report
        screenshots_dir: Directory containing screenshot files
        output_file: Output path (default: overwrite input)
    """
    report_path = Path(report_file)
    if not report_path.exists():
        print(f"Error: Report file '{report_file}' not found", file=sys.stderr)
        return False

    screenshots_path = Path(screenshots_dir)
    if not screenshots_path.exists():
        print(f"Warning: Screenshots directory '{screenshots_dir}' not found", file=sys.stderr)
        # Continue without screenshots - report still valid

    # Read HTML report
    with open(report_path, 'r') as f:
        html_content = f.read()

    # Find all screenshot references and embed them
    # Pattern: <a href="path/to/screenshot.png">
    import re

    screenshot_links = re.findall(r'<a href="([^"]+\.png)">Screenshot</a>', html_content)

    for screenshot_ref in screenshot_links:
        screenshot_path = Path(screenshot_ref)
        if not screenshot_path.exists():
            # Try relative to screenshots directory
            screenshot_path = screenshots_path / screenshot_path.name

        if screenshot_path.exists():
            # Read screenshot and convert to base64
            with open(screenshot_path, 'rb') as img_file:
                img_data = img_file.read()
                img_base64 = base64.b64encode(img_data).decode('utf-8')

            # Create data URI
            data_uri = f"data:image/png;base64,{img_base64}"

            # Replace link with embedded image
            # Replace: <a href="...">Screenshot</a>
            # With: <a href="data:..." onclick="..."><img src="data:..." ...></a>
            embedded_img = (
                f'<a href="{data_uri}" target="_blank" onclick="this.nextSibling.style.display=this.nextSibling.style.display===\'none\'?\'block\':\'none\';return false;">'
                f'View Screenshot'
                f'</a>'
                f'<div style="display:none;margin-top:10px;">'
                f'<img src="{data_uri}" style="max-width:100%;border:1px solid #ccc;" alt="Screenshot">'
                f'</div>'
            )

            html_content = html_content.replace(
                f'<a href="{screenshot_ref}">Screenshot</a>',
                embedded_img
            )

            print(f"Embedded: {screenshot_path.name}")

    # Write output
    output_path = Path(output_file) if output_file else report_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html_content)

    print(f"\nEnhanced report saved to: {output_path}")
    print(f"Embedded {len(screenshot_links)} screenshot(s)")

    return True


def add_environment_info(report_file: str, output_file: str = None):
    """Add environment information to HTML report."""
    import platform
    from datetime import datetime

    report_path = Path(report_file)
    with open(report_path, 'r') as f:
        html_content = f.read()

    # Find the summary section and add environment info
    env_info = f"""
    <div class="environment-info" style="background:#f5f5f5;padding:10px;margin:10px 0;border-radius:5px;">
        <h3>Environment Information</h3>
        <ul>
            <li>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
            <li>Platform: {platform.system()} {platform.release()}</li>
            <li>Python: {platform.python_version()}</li>
            <li>Playwright: {os.popen('playwright --version').read().strip()}</li>
        </ul>
    </div>
    """

    # Insert after the opening body tag or at start of summary
    if '<div class="summary">' in html_content:
        html_content = html_content.replace(
            '<div class="summary">',
            '<div class="summary">' + env_info
        )

    output_path = Path(output_file) if output_file else report_path
    with open(output_path, 'w') as f:
        f.write(html_content)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enhance pytest HTML reports with embedded screenshots"
    )
    parser.add_argument(
        "report_file",
        help="Path to pytest HTML report"
    )
    parser.add_argument(
        "--screenshots",
        type=str,
        default="backend/tests/e2e_ui/artifacts/screenshots",
        help="Screenshots directory"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output HTML file (default: overwrite input)"
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Embed screenshots as base64 (self-contained)"
    )
    parser.add_argument(
        "--add-env",
        action="store_true",
        help="Add environment information to report"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if args.embed:
        success = embed_screenshots_in_html(
            args.report_file,
            args.screenshots,
            args.output
        )
        if not success:
            return 2

    if args.add_env:
        add_environment_info(
            args.output if args.output else args.report_file,
            args.output
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
