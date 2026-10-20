"""CLI wrapper for reusable Walmart FY2027-FY2031 three-statement forecasts.

The original teaching script is retained unchanged in legacy/source/.
Run: python WMT_three_statement_model.py --export-dir outputs/three_statement
"""
from __future__ import annotations
import argparse
from pathlib import Path
from src.three_statement import export_scenario_csv, load_model_inputs, run_all_scenarios

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=Path, default=Path("outputs/three_statement"))
    args = parser.parse_args()
    for name, forecast in run_all_scenarios(load_model_inputs()).items():
        path = export_scenario_csv(forecast, args.export_dir)
        final = forecast[-1]
        print(f"{name}: FY2031 revenue ${final['total_revenue']:,.1f}m; EBIT ${final['ebit']:,.1f}m; cash ${final['cash']:,.1f}m; {path}")

if __name__ == "__main__":
    main()
