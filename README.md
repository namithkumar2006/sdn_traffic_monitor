<<<<<<< HEAD
# SDN Traffic Monitoring and Statistics Collector

> **Orange SDN Mininet Project** – Individual submission  
> Framework: Ryu (OpenFlow 1.3) | Network: Mininet

---

## Problem Statement

Modern networks generate massive volumes of traffic that must be monitored in real-time for capacity planning, anomaly detection, and SLA enforcement. Traditional networks lack the flexibility to collect per-flow statistics without dedicated hardware. 

This project implements an **SDN-based Traffic Monitoring and Statistics Collector** using a Ryu OpenFlow controller and a Mininet virtual network. The controller:
- Learns MAC addresses and installs forwarding rules (learning switch)
- Periodically polls each connected switch for per-flow byte and packet counts
- Displays a live statistics dashboard in the controller log
- Saves cumulative traffic data to a CSV report for further analysis

---

## Project Structure

```
sdn_traffic_monitor/
├── controller/
│   └── traffic_monitor.py     # Ryu controller (main logic)
├── topology/
│   └── custom_topology.py     # Mininet topology (2 switches, 4 hosts)
├── tests/
│   └── test_scenarios.py      # Automated test scenarios
├── generate_report.py         # Reads CSV and prints formatted report
├── run.sh                     # One-command controller launcher
└── README.md
```

---

## Topology

```
  h1 (10.0.0.1) ──┐
                   ├── [s1] ══════════ [s2] ──┬── h3 (10.0.0.3)
  h2 (10.0.0.2) ──┘   OpenFlow13  OpenFlow13  └── h4 (10.0.0.4)

  Controller: Ryu @ 127.0.0.1:6633 (TCP)
```

- **s1** and **s2** are OVS switches running OpenFlow 1.3
- Links: host–switch = 100 Mbps / 2 ms; switch–switch = 1 Gbps / 5 ms
- All switches connect to a single remote Ryu controller

---

## Prerequisites

Install the following on an Ubuntu 20.04 / 22.04 machine (VM recommended):

```bash
sudo apt update
sudo apt install -y mininet python3-pip wireshark iperf net-tools
pip3 install ryu eventlet==0.30.2
```

> **Note:** `eventlet 0.30.2` is required for Ryu compatibility with Python 3.8+.

---

## Setup and Execution

### Step 1 – Clone the Repository

```bash
git clone https://github.com/<your-username>/sdn-traffic-monitor.git
cd sdn-traffic-monitor
```

### Step 2 – Start the Ryu Controller (Terminal 1)

```bash
bash run.sh
```

Or manually:
```bash
ryu-manager controller/traffic_monitor.py --ofp-tcp-listen-port 6633 --verbose
```

You should see:
```
Traffic Monitor & Statistics Collector - STARTED
Stats interval: 10 seconds
Report file:    traffic_report.csv
```

### Step 3 – Start the Mininet Topology (Terminal 2)

```bash
sudo python3 topology/custom_topology.py
```

You will see the Mininet CLI prompt:
```
mininet>
```

### Step 4 – Run Test Scenarios

**Scenario 1: Ping test (connectivity)**
```
mininet> h1 ping h3 -c 5
mininet> h2 ping h4 -c 5
mininet> pingall
```

**Scenario 2: Throughput test (iperf)**
```
mininet> iperf h1 h3
mininet> h4 iperf -s -u &
mininet> h2 iperf -c 10.0.0.4 -u -b 10M -t 10
```

**Scenario 3: Flow table inspection**
```
mininet> sh ovs-ofctl dump-flows s1 -O OpenFlow13
mininet> sh ovs-ofctl dump-flows s2 -O OpenFlow13
```

**Run all automated test scenarios at once:**
```
mininet> py exec(open('tests/test_scenarios.py').read())
```

### Step 5 – Generate Traffic Report

After traffic has been running for at least 10 seconds, in a third terminal:
```bash
python3 generate_report.py
```

Sample output:
```
=================================================================
   SDN TRAFFIC MONITORING REPORT
   Generated: 2024-11-15 14:32:05
   Source:    traffic_report.csv
   Total stat entries: 24
=================================================================

  Switch (Datapath ID): 1
    Flow rule entries polled : 12
    Total packets            : 1,234
    Total bytes              : 98,765 (0.09 MB)
```

---

## SDN Logic and Flow Rule Design

### packet_in Handling
1. Extract Ethernet source/destination MAC from the packet
2. Learn `src_mac → in_port` mapping for this switch
3. If `dst_mac` is known, install a forwarding flow rule; otherwise flood
4. Send/forward the current packet

### Flow Rule Design

| Priority | Match Fields | Action | Timeouts |
|----------|-------------|--------|----------|
| 0 | `*` (everything) | Send to controller | None (permanent) |
| 1 | `in_port, eth_src, eth_dst` | Output to specific port | idle=30s, hard=120s |

- **Table-miss rule (priority 0)**: catches any packet not matched by a specific rule and sends it to the controller for MAC learning.
- **Forwarding rule (priority 1)**: installed after MAC learning; bypasses the controller for future packets of the same flow.

### Statistics Collection
- Every **10 seconds**, the controller sends `OFPFlowStatsRequest` to all registered switches.
- The reply (`OFPFlowStatsReply`) contains per-flow packet counts, byte counts, and duration.
- These values are displayed in the controller log and appended to `traffic_report.csv`.

---

## Performance Observation

| Metric | Tool | Expected Result |
|--------|------|----------------|
| Round-trip latency (same switch) | `ping` | ~4 ms (2×2 ms link delay) |
| Round-trip latency (cross-switch) | `ping` | ~9 ms (2+5+2 ms) |
| TCP throughput (h1↔h3) | `iperf` | ~90–95 Mbps |
| UDP throughput at 10 Mbps | `iperf -u` | ~10 Mbps with <1% loss |
| Flow table entries | `ovs-ofctl` | Grows with unique flows |
| Packet counts per flow | Controller log / CSV | Increases every 10s |

---

## Validation / Regression Tests

| Test | Command | Pass Condition |
|------|---------|---------------|
| All hosts reachable | `pingall` | 0% packet loss |
| Cross-switch ping | `h1 ping h3 -c 5` | RTT ≈ 9 ms |
| Flow rule installed | `ovs-ofctl dump-flows s1` | priority=1 entries visible |
| Stats file generated | `ls -la traffic_report.csv` | File exists, size > 0 |
| Report output | `python3 generate_report.py` | Shows packet/byte counts |

---

## Expected Output Screenshots

> See `screenshots/` folder (add your own after running the demo).

Key screenshots to capture:
1. Controller terminal showing flow stats table
2. `pingall` output showing 0% packet loss
3. `iperf` throughput results
4. `ovs-ofctl dump-flows` output
5. `traffic_report.csv` contents
6. `generate_report.py` output

---

## References

1. OpenFlow 1.3 Specification – Open Networking Foundation (2013)  
   https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf

2. Ryu SDN Framework Documentation  
   https://ryu.readthedocs.io/en/latest/

3. Mininet Official Documentation  
   http://mininet.org/api/

4. Ryu Book – "Ryubook 1.0"  
   https://osrg.github.io/ryu-book/en/html/

5. Open vSwitch Project  
   https://www.openvswitch.org/

---

## Author

Student Name: _[Your Name]_  
Course: SDN and Network Virtualization  
Institution: _[Your Institution]_  
Date: _[Submission Date]_
=======
# sdn_traffic_monitor
A controller module that collects and displays traffic reports. Displays packets, byte counts and generates simple reports. Done using mininet and ryu environment.
>>>>>>> c575fb456dab02c9d71daa84e85a88090dc252b2
