#!/usr/bin/env python3
"""
NYC Transit Recovery - Full Analysis Pipeline

This script runs the complete analysis pipeline:
1. Downloads data (if not already present)
2. Processes and cleans data
3. Runs recovery analysis (clustering + regression)
4. Generates visualizations

Usage:
    python run_pipeline.py [--skip-download] [--skip-analysis]
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / 'src'
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'
OUTPUT_DIR = PROJECT_ROOT / 'output'


def run_step(description: str, script_path: Path, required_output: Path = None):
    """Run a pipeline step with status reporting."""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")

    # Check if output already exists
    if required_output and required_output.exists():
        print(f"  [SKIP] Output already exists: {required_output}")
        return True

    # Run the script
    print(f"  Running: {script_path}")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        capture_output=False
    )

    if result.returncode != 0:
        print(f"  [ERROR] Script failed with return code {result.returncode}")
        return False

    print(f"  [SUCCESS] {description} completed")
    return True


def check_data_status():
    """Check which data files are present."""
    print("\n" + "="*60)
    print("DATA STATUS CHECK")
    print("="*60)

    required_files = {
        'MTA Ridership': DATA_PROCESSED / 'nta_ridership_monthly.parquet',
        'NTA Boundaries': PROJECT_ROOT / 'data' / 'external' / 'nta_boundaries_2020.geojson',
    }

    optional_files = {
        'Building Permits': DATA_RAW / 'dob_permit_issuance.csv',
        '311 Complaints': DATA_RAW / '311_complaints_2020_present.csv',
        'PLUTO': DATA_RAW / 'pluto_2020.csv',
    }

    all_present = True

    print("\nRequired files:")
    for name, path in required_files.items():
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK] {name}: {size_mb:.1f} MB")
        else:
            print(f"  [MISSING] {name}: {path}")
            all_present = False

    print("\nOptional files:")
    for name, path in optional_files.items():
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK] {name}: {size_mb:.1f} MB")
        else:
            print(f"  [MISSING] {name} (optional)")

    return all_present


def main():
    parser = argparse.ArgumentParser(description='Run NYC Transit Recovery Analysis Pipeline')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip data download step')
    parser.add_argument('--skip-analysis', action='store_true',
                        help='Skip analysis (only process data)')
    parser.add_argument('--dashboard-only', action='store_true',
                        help='Only launch the dashboard (requires processed data)')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("NYC TRANSIT RECOVERY - ANALYSIS PIPELINE")
    print("="*60)

    # Check data status
    data_ready = check_data_status()

    if args.dashboard_only:
        # Just launch dashboard
        print("\nLaunching dashboard...")
        subprocess.run([sys.executable, str(SRC_DIR / 'visualization' / 'apple_dashboard.py')])
        return

    # Step 1: Download data
    if not args.skip_download and not data_ready:
        success = run_step(
            "Download Data",
            SRC_DIR / 'data' / 'download_all.py'
        )
        if not success:
            print("\n[WARNING] Data download had issues. Checking if we can proceed...")
            data_ready = check_data_status()
            if not data_ready:
                print("[ERROR] Cannot proceed without required data files.")
                print("Try running: python src/data/download_all.py")
                sys.exit(1)

    # Step 2: Process data
    success = run_step(
        "Process Data",
        SRC_DIR / 'data' / 'process_data.py',
        required_output=DATA_PROCESSED / 'nta_analysis_ready.geojson'
    )
    if not success:
        print("[ERROR] Data processing failed")
        sys.exit(1)

    # Step 3: Run analysis
    if not args.skip_analysis:
        success = run_step(
            "Recovery Analysis",
            SRC_DIR / 'analysis' / 'recovery_analysis.py',
            required_output=OUTPUT_DIR / 'tables' / 'cluster_summary.csv'
        )
        if not success:
            print("[WARNING] Analysis had issues but may have partial results")

    # Step 4: Generate dashboard
    success = run_step(
        "Generate Visualization Dashboard",
        SRC_DIR / 'visualization' / 'apple_dashboard.py'
    )

    # Summary
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)

    print("\nGenerated outputs:")

    # List output files
    if OUTPUT_DIR.exists():
        for subdir in ['figures', 'tables']:
            output_path = OUTPUT_DIR / subdir
            if output_path.exists():
                files = list(output_path.glob('*'))
                if files:
                    print(f"\n  {subdir}/")
                    for f in files[:10]:  # Show first 10
                        print(f"    - {f.name}")
                    if len(files) > 10:
                        print(f"    ... and {len(files) - 10} more files")

    print("\nNext steps:")
    print("  1. Review outputs in output/figures/ and output/tables/")
    print("  2. Run interactive dashboard: python run_pipeline.py --dashboard-only")
    print("  3. Convert docs/proposal.md to PDF for submission")


if __name__ == '__main__':
    main()
