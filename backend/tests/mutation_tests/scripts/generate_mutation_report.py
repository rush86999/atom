#!/usr/bin/env python3
"""
Mutation Test Report Generator

Generates comprehensive mutation testing reports including:
- Mutation scores by module
- Surviving mutants analysis
- Test coverage gaps
- Recommendations for improvement

Usage:
    python generate_mutation_report.py --target priority_p0_financial
    python generate_mutation_report.py --all
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import configparser


def load_targets_config():
    """Load mutation testing targets configuration."""
    config_path = Path(__file__).parent.parent / "targets" / "TARGETS.ini"
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def get_mutmut_results():
    """Get mutation testing results from mutmut."""
    try:
        result = subprocess.run(
            ["mutmut", "results"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        print(f"Error getting mutmut results: {e}")
        return None


def parse_mutmut_results(output):
    """Parse mutmut results into structured data."""
    if not output:
        return None

    results = {
        'score': 0.0,
        'killed': 0,
        'survived': 0,
        'total': 0,
        'modules': {}
    }

    lines = output.split('\n')
    for line in lines:
        if 'Mutation score:' in line:
            import re
            match = re.search(r'(\d+\.\d+)%', line)
            if match:
                results['score'] = float(match.group(1))

    return results


def generate_html_report(results, output_path):
    """Generate HTML mutation testing report."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Mutation Testing Report - Atom Platform</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 40px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .score {{
            font-size: 48px;
            font-weight: bold;
            text-align: center;
            margin: 30px 0;
        }}
        .score.good {{
            color: #28a745;
        }}
        .score.warning {{
            color: #ffc107;
        }}
        .score.danger {{
            color: #dc3545;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .status-pass {{
            color: #28a745;
            font-weight: bold;
        }}
        .status-fail {{
            color: #dc3545;
            font-weight: bold;
        }}
        .recommendation {{
            background: #f8f9fa;
            padding: 15px;
            border-left: 4px solid #007bff;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧬 Mutation Testing Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="score {'good' if results.get('score', 0) >= 90 else 'warning' if results.get('score', 0) >= 80 else 'danger'}">
            {results.get('score', 0):.2f}%
        </div>

        <h2>Results Summary</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Mutation Score</td>
                <td>{results.get('score', 0):.2f}%</td>
            </tr>
            <tr>
                <td>Killed Mutants</td>
                <td>{results.get('killed', 0)}</td>
            </tr>
            <tr>
                <td>Surviving Mutants</td>
                <td>{results.get('survived', 0)}</td>
            </tr>
            <tr>
                <td>Total Mutants</td>
                <td>{results.get('total', 0)}</td>
            </tr>
        </table>

        <h2>Quality Gates</h2>
        <table>
            <tr>
                <th>Priority</th>
                <th>Target</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>P0: Financial & Security</td>
                <td>>95%</td>
                <td class="{'status-pass' if results.get('score', 0) >= 95 else 'status-fail'}">
                    {'✅ PASS' if results.get('score', 0) >= 95 else '❌ FAIL'}
                </td>
            </tr>
            <tr>
                <td>P1: Core Business Logic</td>
                <td>>90%</td>
                <td class="{'status-pass' if results.get('score', 0) >= 90 else 'status-fail'}">
                    {'✅ PASS' if results.get('score', 0) >= 90 else '❌ FAIL'}
                </td>
            </tr>
            <tr>
                <td>P2: API & Tools</td>
                <td>>85%</td>
                <td class="{'status-pass' if results.get('score', 0) >= 85 else 'status-fail'}">
                    {'✅ PASS' if results.get('score', 0) >= 85 else '❌ FAIL'}
                </td>
            </tr>
        </table>

        <div class="recommendation">
            <h3>Recommendations</h3>
            <ul>
                <li>Add property-based tests to kill surviving mutants</li>
                <li>Focus on testing edge cases and boundary conditions</li>
                <li>Increase Hypothesis max_examples for better coverage</li>
                <li>Review test assertions for completeness</li>
            </ul>
        </div>
    </div>
</body>
</html>
    """

    with open(output_path, 'w') as f:
        f.write(html)

    print(f"HTML report generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate mutation testing report"
    )
    parser.add_argument(
        "--output",
        default="tests/mutation_tests/reports/mutation_report.html",
        help="Output path for HTML report"
    )

    args = parser.parse_args()

    # Get results
    output = get_mutmut_results()
    results = parse_mutmut_results(output) or {'score': 0.0}

    # Generate report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_html_report(results, output_path)

    print(f"\nMutation Score: {results['score']:.2f}%")


if __name__ == "__main__":
    main()
