#!/usr/bin/env python3
"""
custom_topology.py
------------------
Mininet topology for the SDN Traffic Monitoring project.

Topology (Linear – 4 hosts, 2 switches):

    h1 ──┐
    h2 ──┤ s1 ══ s2 ├── h3
              │         └── h4

Usage:
    sudo python3 topology/custom_topology.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def create_topology():
    """
    Build and start the Mininet network.
    Two switches (s1, s2) connected to each other.
    h1, h2 attached to s1; h3, h4 attached to s2.
    A RemoteController (Ryu) is expected on 127.0.0.1:6633.
    """
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True     # assigns predictable MACs: 00:00:00:00:00:01, etc.
    )

    info("*** Adding Remote Controller (Ryu on 127.0.0.1:6633)\n")
    c0 = net.addController("c0",
                           controller=RemoteController,
                           ip="127.0.0.1",
                           port=6633)

    info("*** Adding Switches\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")

    info("*** Adding Hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")

    info("*** Adding Links\n")
    # Host–switch links (100 Mbps, 2 ms delay)
    net.addLink(h1, s1, bw=100, delay="2ms")
    net.addLink(h2, s1, bw=100, delay="2ms")
    net.addLink(h3, s2, bw=100, delay="2ms")
    net.addLink(h4, s2, bw=100, delay="2ms")

    # Switch–switch link (1 Gbps, 5 ms delay)
    net.addLink(s1, s2, bw=1000, delay="5ms")

    info("*** Starting Network\n")
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])

    info("\n")
    info("=" * 55 + "\n")
    info("  Topology Ready!\n")
    info("  Hosts: h1=10.0.0.1  h2=10.0.0.2\n")
    info("         h3=10.0.0.3  h4=10.0.0.4\n")
    info("  Switches: s1 -- s2 (connected via trunk link)\n")
    info("  Controller: Ryu @ 127.0.0.1:6633\n")
    info("=" * 55 + "\n\n")
    info("  Suggested test commands inside Mininet CLI:\n")
    info("    h1 ping h3 -c 5          # cross-switch ping\n")
    info("    iperf h1 h4              # throughput test\n")
    info("    h2 ping h4 -c 3          # another cross-switch test\n")
    info("    s1 ovs-ofctl dump-flows s1 -O OpenFlow13\n")
    info("=" * 55 + "\n\n")

    CLI(net)

    info("*** Stopping Network\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
