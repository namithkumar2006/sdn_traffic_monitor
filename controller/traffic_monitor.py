"""
Traffic Monitoring and Statistics Collector
SDN Controller using Ryu Framework with OpenFlow 1.3

Features:
- Learning switch with MAC table
- Packet_in event handling
- Periodic flow statistics polling (every 10 seconds)
- Packet and byte count display
- Simple traffic report generation saved to CSV
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, tcp, udp
from ryu.lib import hub

import datetime
import csv
import os

REPORT_FILE = "traffic_report.csv"
STATS_INTERVAL = 10  # seconds between stats polls


class TrafficMonitor(app_manager.RyuApp):
    """
    Ryu application that implements:
      1. A MAC-learning switch (installs flow rules on first packet_in)
      2. Periodic statistics collection from all connected switches
      3. CSV report generation of per-flow byte/packet counts
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TrafficMonitor, self).__init__(*args, **kwargs)

        # MAC learning table: {datapath_id: {mac_address: port}}
        self.mac_to_port = {}

        # Datapath registry: {datapath_id: datapath}
        self.datapaths = {}

        # Cumulative stats storage: {(dpid, cookie): {bytes, packets, last_seen}}
        self.flow_stats = {}

        # Ensure report file has a header
        self._init_report_file()

        # Start the background stats polling thread
        self.monitor_thread = hub.spawn(self._monitor_loop)

        self.logger.info("=" * 60)
        self.logger.info("  Traffic Monitor & Statistics Collector - STARTED")
        self.logger.info("  Stats interval: %d seconds", STATS_INTERVAL)
        self.logger.info("  Report file:    %s", REPORT_FILE)
        self.logger.info("=" * 60)

    # ------------------------------------------------------------------ #
    #  Initialisation helpers                                              #
    # ------------------------------------------------------------------ #

    def _init_report_file(self):
        """Create CSV report file with headers if it does not already exist."""
        if not os.path.exists(REPORT_FILE):
            with open(REPORT_FILE, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "datapath_id", "in_port", "eth_dst",
                    "eth_src", "out_port", "packet_count", "byte_count",
                    "duration_sec", "priority"
                ])

    # ------------------------------------------------------------------ #
    #  OpenFlow event handlers                                             #
    # ------------------------------------------------------------------ #

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Called when a switch connects and sends its features.
        Installs the default table-miss flow rule so unmatched packets
        are sent to the controller via packet_in.
        """
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Register datapath for stats polling
        self.datapaths[datapath.id] = datapath
        self.logger.info("[Switch %016x] Connected – installing table-miss rule", datapath.id)

        # Table-miss: match everything, priority 0, send to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, priority=0, match=match, actions=actions)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        """Track when datapaths come and go."""
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            self.logger.info("[Switch %016x] Entered MAIN_DISPATCHER", datapath.id)
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self.logger.info("[Switch %016x] Disconnected", datapath.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Handle packet_in messages.
        - Learn MAC → port mapping
        - Install a flow rule so future packets bypass the controller
        - Forward packet to correct port (or flood if unknown)
        """
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP frames
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst_mac = eth.dst
        src_mac = eth.src
        dpid = datapath.id

        # --- MAC learning ---
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port

        # --- Decide output port ---
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # --- Install flow rule (if not flooding) ---
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port,
                                    eth_dst=dst_mac,
                                    eth_src=src_mac)
            # idle_timeout=30: rule removed after 30 s of inactivity
            # hard_timeout=120: rule removed after 2 minutes regardless
            self._add_flow(datapath,
                           priority=1,
                           match=match,
                           actions=actions,
                           idle_timeout=30,
                           hard_timeout=120)
            self.logger.info(
                "[Switch %016x] Flow installed: %s → port %s (in_port=%s)",
                dpid, dst_mac, out_port, in_port
            )

        # --- Forward the current packet ---
        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)

    # ------------------------------------------------------------------ #
    #  Statistics request & reply                                          #
    # ------------------------------------------------------------------ #

    def _monitor_loop(self):
        """Background greenlet: request flow stats from every switch periodically."""
        while True:
            for dp in list(self.datapaths.values()):
                self._request_flow_stats(dp)
            hub.sleep(STATS_INTERVAL)

    def _request_flow_stats(self, datapath):
        """Send OFPFlowStatsRequest to a datapath."""
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        req = parser.OFPFlowStatsRequest(datapath,
                                         flags=0,
                                         table_id=ofproto.OFPTT_ALL,
                                         out_port=ofproto.OFPP_ANY,
                                         out_group=ofproto.OFPG_ANY,
                                         cookie=0,
                                         cookie_mask=0,
                                         match=parser.OFPMatch())
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """
        Receive flow stats reply from a switch.
        - Display stats in the log
        - Write a row to the CSV report
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.logger.info("")
        self.logger.info("╔══════════════════════════════════════════════════════╗")
        self.logger.info("║  FLOW STATISTICS  –  Switch %016x  ║", dpid)
        self.logger.info("║  Timestamp: %-41s║", timestamp)
        self.logger.info("╠══════╦════════════╦════════════╦══════════╦══════════╣")
        self.logger.info("║ Prio ║  In-Port   ║  Eth-Dst   ║  Pkts    ║  Bytes   ║")
        self.logger.info("╠══════╬════════════╬════════════╬══════════╬══════════╣")

        report_rows = []

        for stat in sorted(body, key=lambda s: (s.priority, s.match)):
            priority = stat.priority
            in_port  = stat.match.get("in_port", "*")
            eth_dst  = stat.match.get("eth_dst", "*")
            eth_src  = stat.match.get("eth_src", "*")
            out_port = (stat.instructions[0].actions[0].port
                        if stat.instructions else "*")

            self.logger.info(
                "║  %3d ║ %-10s ║ %-10s ║ %8d ║ %8d ║",
                priority, str(in_port), str(eth_dst),
                stat.packet_count, stat.byte_count
            )

            report_rows.append([
                timestamp, dpid, in_port, eth_dst, eth_src,
                out_port, stat.packet_count, stat.byte_count,
                stat.duration_sec, priority
            ])

        self.logger.info("╚══════╩════════════╩════════════╩══════════╩══════════╝")

        # --- Write to CSV report ---
        with open(REPORT_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(report_rows)

    # ------------------------------------------------------------------ #
    #  Helper: install a flow rule                                         #
    # ------------------------------------------------------------------ #

    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=0, hard_timeout=0):
        """
        Install an OpenFlow flow rule on a datapath.

        Args:
            datapath:      Target switch datapath object
            priority:      Rule priority (higher wins)
            match:         OFPMatch describing which packets to match
            actions:       List of OFPAction* describing what to do
            idle_timeout:  Remove rule after this many seconds of inactivity
            hard_timeout:  Remove rule unconditionally after this many seconds
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Wrap actions in an ApplyActions instruction
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
            match=match,
            instructions=inst
        )
        datapath.send_msg(mod)
