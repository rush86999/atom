#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Platform Coverage Dashboard Generator

Purpose: Generate HTML dashboard with matplotlib charts visualizing 30-day coverage trends
for each platform (backend, frontend, mobile, desktop) and overall coverage. Creates 
self-contained HTML with embedded base64 images.

Usage:
    python generate_cross_platform_dashboard.py [options]

Options:
    --trending-file PATH      Path to cross_platform_trend.json (default: relative path)
    --output PATH             Output HTML file path (default: coverage_trend_30d.html)
    --days INT                Number of days to include in chart (default: 30)
    --width INT               Chart width in pixels (default: 1200)
    --height INT              Chart height in pixels (default: 600)

Example:
    python generate_cross_platform_dashboard.py --days 30 --output coverage_dashboard.html
"""

import argparse
import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Matplotlib imports
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for CI/CD
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# Configure logging
from logging import basicConfig, getLogger, INFO

basicConfig(
    level=INFO,
    format='%(levelname)s: %(message)s'
)
logger = getLogger(__name__)

# Default paths
TREND_FILE = Path("tests/coverage_reports/metrics/cross_platform_trend.json")
OUTPUT_DIR = Path("tests/coverage_reports/dashboards")

# Chart colors for platforms
CHART_COLORS = {
    "backend": "#3B82F6",   # Blue
    "frontend": "#10B981",  # Green
    "mobile": "#F59E0B",    # Orange
    "desktop": "#8B5CF6",   # Purple
    "overall": "#111827"    # Dark gray
}

# Default configuration
DEFAULT_DAYS = 30
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 600
DPI = 100


def load_trending_data(trend_file: Path) -> Dict:
    """
    Load trending data from cross_platform_trend.json.

    Reuses load_trending_data() from update_cross_platform_trending.py.

    Args:
        trend_file: Path to cross_platform_trend.json

    Returns:
        Dict with history list and latest entry
    """
    # Import from update_cross_platform_trending.py
    try:
        # Add scripts directory to path
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        
        from update_cross_platform_trending import load_trending_data as load_trend
        return load_trend(trend_file)
    except ImportError:
        # Fallback to simple implementation
        default_structure = {
            "history": [],
            "latest": {},
            "platform_trends": {},
            "computed_weights": {
                "backend": 0.35,
                "frontend": 0.40,
                "mobile": 0.15,
                "desktop": 0.10
            }
        }

        if not trend_file.exists():
            logger.warning(f"Trend file not found: {trend_file}, using empty structure")
            return default_structure

        try:
            with open(trend_file, 'r') as f:
                trending_data = json.load(f)

            # Validate structure
            required_keys = ["history", "latest", "platform_trends"]
            for key in required_keys:
                if key not in trending_data:
                    logger.warning(f"Missing key '{key}', using default")
                    trending_data[key] = default_structure[key]

            return trending_data

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading trending data: {e}")
            return default_structure


def prepare_chart_data(trending_data: Dict, days: int = 30) -> Dict:
    """
    Prepare chart data by filtering history to last N days.

    Args:
        trending_data: Trending data dict with history
        days: Number of days to include (default: 30)

    Returns:
        Dict with timestamps, platforms dict, and overall list
    """
    history = trending_data.get("history", [])

    if not history:
        logger.warning("No history data available")
        return {
            "timestamps": [],
            "platforms": {},
            "overall": []
        }

    # Filter to last N entries (days parameter interpreted as entries for simplicity)
    filtered_history = history[-days:] if len(history) > days else history

    # Extract timestamps
    timestamps = []
    for entry in filtered_history:
        try:
            # Parse timestamp
            ts = entry.get("timestamp", "")
            ts_clean = ts.replace("Z", "").replace("+00:00", "")
            dt = datetime.fromisoformat(ts_clean)
            timestamps.append(dt)
        except (ValueError, KeyError):
            # Use current time if parsing fails
            timestamps.append(datetime.now())

    # Extract platform coverage values
    platforms_data = {
        "backend": [],
        "frontend": [],
        "mobile": [],
        "desktop": []
    }

    overall_data = []

    for entry in filtered_history:
        platforms = entry.get("platforms", {})
        for platform in platforms_data.keys():
            platforms_data[platform].append(platforms.get(platform, 0.0))

        overall_data.append(entry.get("overall_coverage", 0.0))

    return {
        "timestamps": timestamps,
        "platforms": platforms_data,
        "overall": overall_data
    }


def create_line_chart(
    data: Dict,
    title: str = "Coverage Trend (30 Days)",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT
) -> bytes:
    """
    Create line chart with all platforms and overall coverage.

    Args:
        data: Chart data dict with timestamps, platforms, overall
        title: Chart title
        width: Chart width in pixels
        height: Chart height in pixels

    Returns:
        Base64-encoded PNG image bytes
    """
    timestamps = data.get("timestamps", [])
    platforms = data.get("platforms", {})
    overall = data.get("overall", [])

    if not timestamps:
        logger.warning("No data available for chart")
        return b""

    # Create figure
    figsize = (width / DPI, height / DPI)
    fig, ax = plt.subplots(figsize=figsize, dpi=DPI)

    # Plot overall coverage (thick, dark line)
    if overall:
        ax.plot(timestamps, overall, color=CHART_COLORS["overall"],
                linewidth=3, label="Overall", alpha=0.8)

    # Plot each platform (thinner, colored lines)
    for platform_name, coverage_values in platforms.items():
        if coverage_values:
            ax.plot(timestamps, coverage_values,
                    color=CHART_COLORS.get(platform_name, "#000000"),
                    linewidth=1.5, label=platform_name.capitalize(),
                    alpha=0.7)

    # Add legend
    ax.legend(loc='best', framealpha=0.9)

    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)

    # Format x-axis with dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(timestamps) // 10)))
    plt.xticks(rotation=45, ha='right')

    # Set y-axis range and format
    ax.set_ylim(0, 100)
    ax.set_ylabel('Coverage %', fontsize=11)
    ax.set_xlabel('Date', fontsize=11)

    # Set title
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

    # Use tight layout to prevent clipping
    plt.tight_layout()

    # Save to BytesIO buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=DPI, bbox_inches='tight')
    buf.seek(0)

    # Get base64 encoded bytes
    image_bytes = buf.getvalue()
    base64_bytes = base64.b64encode(image_bytes)

    # Close figure to prevent memory leak
    plt.close(fig)

    return base64_bytes


def create_platform_charts(data: Dict) -> Dict[str, bytes]:
    """
    Create individual platform charts in 2x2 grid.

    Args:
        data: Chart data dict with timestamps, platforms, overall

    Returns:
        Dict mapping platform name to base64 image bytes
    """
    timestamps = data.get("timestamps", [])
    platforms = data.get("platforms", {})

    if not timestamps:
        logger.warning("No data available for platform charts")
        return {}

    # Create 2x2 subplot figure
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=DPI)
    axes = axes.flatten()

    for idx, (platform_name, coverage_values) in enumerate(platforms.items()):
        if idx >= len(axes):
            break

        ax = axes[idx]

        if not coverage_values:
            continue

        # Plot platform coverage
        ax.plot(timestamps, coverage_values,
                color=CHART_COLORS.get(platform_name, "#000000"),
                linewidth=2, label=platform_name.capitalize(),
                marker='o', markersize=4, alpha=0.8)

        # Add threshold line (70% as example)
        threshold = 70.0
        ax.axhline(y=threshold, color='red', linestyle='--',
                  linewidth=1, alpha=0.5, label=f'Threshold ({threshold}%)')

        # Color code: above threshold green, below red
        if coverage_values and coverage_values[-1] >= threshold:
            title_color = 'green'
        else:
            title_color = 'red'

        # Format subplot
        ax.set_title(f"{platform_name.capitalize()} Coverage",
                    fontsize=12, fontweight='bold', color=title_color)
        ax.set_ylim(0, 100)
        ax.set_ylabel('Coverage %', fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='best', fontsize=9)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(timestamps) // 5)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=8)

    # Adjust layout
    plt.tight_layout()

    # Save to BytesIO buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=DPI, bbox_inches='tight')
    buf.seek(0)

    # Get base64 encoded bytes
    image_bytes = buf.getvalue()
    base64_bytes = base64.b64encode(image_bytes)

    # Close figure to prevent memory leak
    plt.close(fig)

    return {"platforms": base64_bytes}


def calculate_statistics(data: Dict) -> Dict:
    """
    Calculate summary statistics for each platform.

    Args:
        data: Chart data dict with timestamps, platforms, overall

    Returns:
        Dict with statistics for each platform and overall
    """
    platforms = data.get("platforms", {})
    overall = data.get("overall", [])

    stats = {}

    # Calculate overall statistics
    if overall:
        stats["overall"] = {
            "current": round(overall[-1], 2) if overall else 0.0,
            "min": round(min(overall), 2) if overall else 0.0,
            "max": round(max(overall), 2) if overall else 0.0,
            "avg": round(sum(overall) / len(overall), 2) if overall else 0.0,
            "trend": _calculate_trend(overall)
        }

    # Calculate platform statistics
    for platform_name, coverage_values in platforms.items():
        if coverage_values:
            stats[platform_name] = {
                "current": round(coverage_values[-1], 2),
                "min": round(min(coverage_values), 2),
                "max": round(max(coverage_values), 2),
                "avg": round(sum(coverage_values) / len(coverage_values), 2),
                "trend": _calculate_trend(coverage_values)
            }

    return stats


def _calculate_trend(values: List[float]) -> str:
    """
    Calculate trend direction (up/down/stable).

    Args:
        values: List of coverage values

    Returns:
        "up", "down", or "stable"
    """
    if len(values) < 2:
        return "stable"

    first = values[0]
    last = values[-1]
    delta = last - first

    if delta > 1.0:
        return "up"
    elif delta < -1.0:
        return "down"
    else:
        return "stable"


def _get_trend_indicator(trend: str) -> str:
    """Get trend indicator symbol."""
    if trend == "up":
        return "↑"
    elif trend == "down":
        return "↓"
    else:
        return "→"


def generate_html_template(
    chart_base64: str,
    platform_charts: Dict[str, str],
    data: Dict,
    statistics: Dict
) -> str:
    """
    Generate self-contained HTML dashboard.

    Args:
        chart_base64: Base64-encoded main chart image
        platform_charts: Dict with platform chart base64 images
        data: Chart data dict
        statistics: Statistics dict

    Returns:
        Complete HTML string
    """
    # Convert base64 bytes to string
    main_chart_src = f"data:image/png;base64,{chart_base64.decode('utf-8')}" if isinstance(chart_base64, bytes) else chart_base64

    platforms_chart_src = ""
    if "platforms" in platform_charts:
        platforms_chart_bytes = platform_charts["platforms"]
        if isinstance(platforms_chart_bytes, bytes):
            platforms_chart_src = f"data:image/png;base64,{platforms_chart_bytes.decode('utf-8')}"
        else:
            platforms_chart_src = platforms_chart_bytes

    # Get generation time
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Generate statistics table rows
    stats_rows = ""
    for name, stats_data in statistics.items():
        trend_indicator = _get_trend_indicator(stats_data.get("trend", "stable"))
        trend_color = "green" if stats_data.get("trend") == "up" else "red" if stats_data.get("trend") == "down" else "gray"

        stats_rows += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{name.capitalize()}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{stats_data.get('current', 0):.2f}%</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{stats_data.get('min', 0):.2f}%</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{stats_data.get('max', 0):.2f}%</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{stats_data.get('avg', 0):.2f}%</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; color: {trend_color}; font-weight: bold;">{trend_indicator}</td>
        </tr>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coverage Trend Dashboard (30 Days)</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: #f9fafb;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
            font-weight: 700;
        }}

        .header p {{
            font-size: 14px;
            opacity: 0.9;
        }}

        .content {{
            padding: 30px;
        }}

        .chart-section {{
            margin-bottom: 40px;
        }}

        .chart-section h2 {{
            font-size: 24px;
            margin-bottom: 20px;
            color: #111827;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 10px;
        }}

        .chart-container {{
            text-align: center;
            margin: 20px 0;
        }}

        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            cursor: pointer;
            transition: transform 0.2s;
        }}

        .chart-container img:hover {{
            transform: scale(1.02);
        }}

        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}

        .stats-table th {{
            background: #374151;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.5px;
        }}

        .stats-table td {{
            padding: 12px;
            border-bottom: 1px solid #e5e7eb;
        }}

        .stats-table tr:hover {{
            background: #f9fafb;
        }}

        .legend {{
            background: #f3f4f6;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 14px;
        }}

        .legend h3 {{
            margin-bottom: 10px;
            color: #374151;
        }}

        .legend ul {{
            list-style: none;
            padding-left: 0;
        }}

        .legend li {{
            margin: 5px 0;
            padding-left: 20px;
            position: relative;
        }}

        .legend li::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: #6b7280;
            font-weight: bold;
        }}

        .footer {{
            background: #f3f4f6;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #e5e7eb;
        }}

        @media (max-width: 768px) {{
            .content {{
                padding: 15px;
            }}

            .header h1 {{
                font-size: 24px;
            }}

            .stats-table {{
                font-size: 12px;
            }}

            .stats-table th, .stats-table td {{
                padding: 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Cross-Platform Coverage Trend Dashboard</h1>
            <p>Last 30 days of coverage metrics across all platforms</p>
        </div>

        <div class="content">
            <div class="chart-section">
                <h2>Overall Coverage Trend</h2>
                <div class="chart-container">
                    <img src="{main_chart_src}" alt="Overall Coverage Trend Chart" title="Click to zoom">
                </div>
            </div>

            <div class="chart-section">
                <h2>Platform-Specific Trends</h2>
                <div class="chart-container">
                    <img src="{platforms_chart_src}" alt="Platform-Specific Coverage Charts" title="Click to zoom">
                </div>
            </div>

            <div class="chart-section">
                <h2>Summary Statistics</h2>
                <table class="stats-table">
                    <thead>
                        <tr>
                            <th>Platform</th>
                            <th>Current (%)</th>
                            <th>Min (%)</th>
                            <th>Max (%)</th>
                            <th>Average (%)</th>
                            <th>Trend</th>
                        </tr>
                    </thead>
                    <tbody>
                        {stats_rows}
                    </tbody>
                </table>
            </div>

            <div class="legend">
                <h3>Trend Indicators</h3>
                <ul>
                    <li>↑ Improved (>1% increase from start of period)</li>
                    <li>↓ Regressed (>1% decrease from start of period)</li>
                    <li>→ Stable (within ±1% from start of period)</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            <p>Generated on {generation_time}</p>
            <p>Coverage Dashboard Generator | Atom Quality Infrastructure</p>
        </div>
    </div>
</body>
</html>"""

    return html_template


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate HTML cross-platform coverage dashboard with matplotlib charts"
    )

    parser.add_argument(
        "--trending-file",
        type=Path,
        default=TREND_FILE,
        help="Path to cross_platform_trend.json"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "coverage_trend_30d.html",
        help="Output HTML file path"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Number of days to include in chart (default: {DEFAULT_DAYS})"
    )

    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"Chart width in pixels (default: {DEFAULT_WIDTH})"
    )

    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help=f"Chart height in pixels (default: {DEFAULT_HEIGHT})"
    )

    args = parser.parse_args()

    # Load trend data
    logger.info(f"Loading trend data from: {args.trending_file}")
    trending_data = load_trending_data(args.trending_file)

    # Prepare chart data
    logger.info(f"Preparing chart data (last {args.days} entries)")
    chart_data = prepare_chart_data(trending_data, days=args.days)

    if not chart_data.get("timestamps"):
        logger.error("No data available for chart generation")
        sys.exit(1)

    # Generate main chart
    logger.info("Generating main coverage trend chart")
    main_chart_base64 = create_line_chart(
        chart_data,
        title=f"Coverage Trend (Last {len(chart_data['timestamps'])} Entries)",
        width=args.width,
        height=args.height
    )

    # Generate platform charts
    logger.info("Generating platform-specific charts")
    platform_charts = create_platform_charts(chart_data)

    # Calculate statistics
    logger.info("Calculating summary statistics")
    statistics = calculate_statistics(chart_data)

    # Generate HTML
    logger.info("Generating HTML dashboard")
    html_content = generate_html_template(
        main_chart_base64,
        platform_charts,
        chart_data,
        statistics
    )

    # Write output file
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(html_content)

    logger.info(f"Dashboard generated: {output_path}")
    logger.info(f"  File size: {output_path.stat().st_size / 1024:.2f} KB")
    logger.info(f"  Data points: {len(chart_data['timestamps'])}")
    logger.info(f"  Platforms: {', '.join(chart_data['platforms'].keys())}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
