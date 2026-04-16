# Screenshots

Add your proof-of-execution screenshots here after running the demo.

## Required Screenshots

1. **controller_startup.png** – Ryu controller starting up
2. **switch_connected.png** – Switch connecting to controller in log
3. **pingall_output.png** – `pingall` showing 0% packet loss
4. **flow_stats_log.png** – Controller showing the flow stats table
5. **iperf_tcp.png** – iperf TCP throughput test result
6. **iperf_udp.png** – iperf UDP throughput test result
7. **ovs_dump_flows_s1.png** – Flow table from switch s1
8. **ovs_dump_flows_s2.png** – Flow table from switch s2
9. **traffic_report_csv.png** – Contents of traffic_report.csv
10. **report_output.png** – Output of generate_report.py

## How to Take Screenshots

In the terminal:
```bash
# Redirect output to a file for proof
sudo python3 topology/custom_topology.py 2>&1 | tee mininet_output.log
```

Or use the `screenshot` tool on your VM desktop.
