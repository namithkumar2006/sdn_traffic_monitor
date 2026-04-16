#!/usr/bin/env python3
"""
generate_report.py
------------------
Reads traffic_report.csv produced by the Ryu controller and
prints a formatted summary report to stdout.

Usage:
    python3 generate_report.py [path_to_csv]

Default CSV path: traffic_report.csv (current directory)
"""

import csv
import sys
import os
from collections import defaultdict
from datetime import datetime


def generate_report(csv_path="traffic_report.csv"):
    if not os.path.exists(csv_path):
        print(f"ERROR: Report file '{csv_path}' not found.")
        print("Make sure the Ryu controller has been running and generating stats.")
        sys.exit(1)

    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) == 0:
        print("No data found in report file yet. Wait for at least one stats poll (10s).")
        sys.exit(0)

    # Aggregate by datapath
    dp_stats = defaultdict(lambda: {"total_packets": 0, "total_bytes": 0, "flow_count": 0})
    for row in rows:
        dpid = row["datapath_id"]
        try:
            dp_stats[dpid]["total_packets"] += int(row["packet_count"])
            dp_stats[dpid]["total_bytes"]   += int(row["byte_count"])
            dp_stats[dpid]["flow_count"]    += 1
        except (ValueError, KeyError):
            pass  # skip malformed rows

    # Print report
    print()
    print("=" * 65)
    print("   SDN TRAFFIC MONITORING REPORT")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Source:    {csv_path}")
    print(f"   Total stat entries: {len(rows)}")
    print("=" * 65)

    for dpid, stats in dp_stats.items():
        total_mb = stats["total_bytes"] / (1024 * 1024)
        print(f"\n  Switch (Datapath ID): {dpid}")
        print(f"    Flow rule entries polled : {stats['flow_count']}")
        print(f"    Total packets            : {stats['total_packets']:,}")
        print(f"    Total bytes              : {stats['total_bytes']:,} ({total_mb:.2f} MB)")

    # Top 5 flows by byte count (across all entries)
    print("\n  Top 5 Flows by Byte Count")
    print("  " + "-" * 60)
    print(f"  {'Timestamp':<20} {'DPID':<8} {'Dst MAC':<20} {'Pkts':>8} {'Bytes':>12}")
    print("  " + "-" * 60)

    sorted_rows = sorted(rows, key=lambda r: int(r.get("byte_count", 0)), reverse=True)
    for row in sorted_rows[:5]:
        try:
            print(
                f"  {row['timestamp']:<20} "
                f"{row['datapath_id']:<8} "
                f"{row['eth_dst']:<20} "
                f"{int(row['packet_count']):>8,} "
                f"{int(row['byte_count']):>12,}"
            )
        except (ValueError, KeyError):
            pass

    print("\n" + "=" * 65)
    print("  Report complete. See traffic_report.csv for full data.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "traffic_report.csv"
    generate_report(csv_path)
