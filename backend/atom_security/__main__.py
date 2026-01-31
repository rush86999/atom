import sys
import asyncio
import argparse
from pathlib import Path
from atom_security.analyzers.static import StaticAnalyzer
from atom_security.analyzers.llm import LLMAnalyzer
from atom_security.core.models import Severity

async def run_scan(args):
    target_path = Path(args.path)
    if not target_path.exists():
        print(f"Error: Path not found: {target_path}")
        sys.exit(1)
        
    print(f"Scanning {target_path}...")
    
    findings = []
    
    # 1. Static Analysis (Always runs)
    static_analyzer = StaticAnalyzer()
    if target_path.is_file():
        findings.extend(static_analyzer.scan_file(target_path))
    else:
        result = static_analyzer.scan_directory(target_path)
        findings.extend(result.findings)
        
    # 2. LLM Analysis (Optional)
    if args.llm != "none":
        print(f"Running LLM Analysis ({args.llm} mode)...")
        llm_analyzer = LLMAnalyzer(
            mode=args.llm,
            model=args.llm_model,
            api_key=args.llm_api_key,
            provider=args.llm_provider
        )
        
        # For simplicity in CLI, we analyze the main instructions or whole folder summary
        # In a real tool, we might iterate over all files, but that's expensive.
        # We'll analyze the whole context for directory scans.
        if target_path.is_file():
            content = target_path.read_text()
            llm_findings = await llm_analyzer.analyze(target_path.name, content)
            findings.extend(llm_findings)
        else:
            # Aggregate contents for directory (limited)
            all_content = ""
            for p in target_path.rglob("*"):
                if p.is_file() and p.suffix in [".md", ".py", ".json"]:
                    all_content += f"\n--- {p.name} ---\n{p.read_text()[:1000]}"
            llm_findings = await llm_analyzer.analyze(target_path.name, all_content)
            findings.extend(llm_findings)

    # Output results
    if args.format == "text":
        print(f"\nScan Complete ({len(findings)} issues found)")
        print("=" * 60)
        
        # Group by severity
        sorted_findings = sorted(findings, key=lambda x: x.severity, reverse=True)
        
        for f in sorted_findings:
            print(f"[{f.severity.value}] {f.category} ({f.analyzer})")
            print(f"  File: {f.file_path}:{f.line_number}")
            print(f"  Msg:  {f.description}")
            if f.line_content:
                print(f"  Code: {f.line_content.strip()}")
            print("-" * 60)
            
    elif args.format == "json":
        import json
        output = [f.dict() for f in findings]
        print(json.dumps(output, indent=2, default=str))
        
    if findings:
        sys.exit(1)
    else:
        print("No issues found.")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Atom Security Scanner")
    parser.add_argument("path", help="Path to file or directory to scan")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    
    # LLM Options
    parser.add_argument("--llm", choices=["none", "local", "byok"], default="none", help="LLM analysis mode")
    parser.add_argument("--llm-provider", choices=["openai", "anthropic"], default="openai", help="LLM provider (for byok)")
    parser.add_argument("--llm-model", help="LLM model name")
    parser.add_argument("--llm-api-key", help="LLM API Key")
    
    args = parser.parse_args()
    asyncio.run(run_scan(args))

if __name__ == "__main__":
    main()
