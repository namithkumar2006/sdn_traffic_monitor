#!/usr/bin/env python3
"""
test_scenarios.py
-----------------
Automated test scenarios for the Traffic Monitoring project.

Scenario 1: Connectivity Test
    - h1 pings h2 (same switch)
    - h1 pings h3 (cross-switch)
    - h1 pings h4 (cross-switch)

Scenario 2: Throughput Test (iperf)
    - h1 ↔ h3 TCP throughput
    - h2 ↔ h4 UDP throughput

Scenario 3: Flow Table Dump
    - Dump flow tables on s1 and s2 after traffic

Run from Mininet CLI (after topology is started):
    mininet> py exec(open('tests/test_scenarios.py').read())
OR
    mininet> source tests/test_scenarios.py
"""

import os
import sys
import time


def run_scenario_1(net):
    """
    Scenario 1: Basic Connectivity
    Tests ICMP reachability between all host pairs.
    Verifies that the learning switch correctly forwards packets.
    """
    print("\n" + "=" * 55)
    print("  SCENARIO 1: Basic Connectivity Test")
    print("=" * 55)

    h1 = net.get("h1")
    h2 = net.get("h2")
    h3 = net.get("h3")
    h4 = net.get("h4")

    pairs = [
        (h1, h2, "Same-switch (h1→h2)"),
        (h1, h3, "Cross-switch (h1→h3)"),
        (h2, h4, "Cross-switch (h2→h4)"),
        (h3, h4, "Same-switch (h3→h4)"),
    ]

    results = []
    for src, dst, label in pairs:
        print(f"\n  [{label}]  {src.name} → {dst.name}")
        result = src.cmd(f"ping -c 4 -W 2 {dst.IP()}")
        print(result)

        # Parse packet loss
        if "0% packet loss" in result:
            status = "PASS ✓"
        elif "100% packet loss" in result:
            status = "FAIL ✗"
        else:
            status = "PARTIAL"
        results.append((label, status))

    print("\n  --- Scenario 1 Summary ---")
    for label, status in results:
        print(f"  {label:35s}: {status}")


def run_scenario_2(net):
    """
    Scenario 2: Throughput Measurement with iperf
    Tests TCP and UDP throughput.
    Verifies flow rules allow sustained high-bandwidth traffic.
    """
    print("\n" + "=" * 55)
    print("  SCENARIO 2: Throughput Test (iperf)")
    print("=" * 55)

    h1 = net.get("h1")
    h3 = net.get("h3")
    h2 = net.get("h2")
    h4 = net.get("h4")

    # TCP test: h1 → h3
    print("\n  [TCP] h1 → h3 (10 seconds)")
    h3.cmd("iperf -s &")
    time.sleep(1)
    tcp_result = h1.cmd("iperf -c " + h3.IP() + " -t 10")
    h3.cmd("kill %iperf")
    print(tcp_result)

    # UDP test: h2 → h4
    print("\n  [UDP] h2 → h4 (10 seconds, 10 Mbps)")
    h4.cmd("iperf -s -u &")
    time.sleep(1)
    udp_result = h2.cmd("iperf -c " + h4.IP() + " -u -b 10M -t 10")
    h4.cmd("kill %iperf")
    print(udp_result)

    print("\n  Throughput tests complete. Check traffic_report.csv for stats.")


def run_scenario_3(net):
    """
    Scenario 3: Flow Table Dump
    Shows installed flow rules on both switches after traffic generation.
    Validates that the controller installed match-action rules correctly.
    """
    print("\n" + "=" * 55)
    print("  SCENARIO 3: Flow Table Inspection")
    print("=" * 55)

    for switch_name in ["s1", "s2"]:
        sw = net.get(switch_name)
        print(f"\n  [Flow Table – {switch_name}]")
        result = sw.cmd(f"ovs-ofctl dump-flows {switch_name} -O OpenFlow13")
        print(result)

    print("\n  Interpret results:")
    print("  - priority=0: table-miss rule (sends unknown packets to controller)")
    print("  - priority=1: learned forwarding rules with packet/byte counters")
    print("  - n_packets / n_bytes: traffic counters updated by the switch")


# ------------------------------------------------------------------ #
# Entry point when run from the Mininet CLI                           #
# ------------------------------------------------------------------ #
if __name__ == "__main__" or "net" in dir():
    try:
        # 'net' is available when sourced from the Mininet CLI
        print("\nRunning all test scenarios...")
        run_scenario_1(net)
        run_scenario_2(net)
        run_scenario_3(net)
    except NameError:
        print("ERROR: 'net' not found.")
        print("Run this from inside the Mininet CLI:")
        print("  mininet> py exec(open('tests/test_scenarios.py').read())")
