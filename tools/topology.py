"""Topology search and admittance matrix MCP tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandapower as pp
import pandapower.topology as topo
from pandapower.converter.pypower.to_ppc import to_ppc
from pandapower.pypower.makeYbus import makeYbus
from pandapower.topology.create_graph import create_nxgraph

from network_state import error, get_network, serialize_series, serialize_sparse_matrix, success

logger = logging.getLogger(__name__)


def register_tools(mcp) -> None:
    @mcp.tool()
    def find_unsupplied_buses(respect_switches: bool = True) -> Dict[str, Any]:
        """Find buses that are not electrically connected to an external grid."""
        logger.info("Finding unsupplied buses")
        try:
            net = get_network()
            unsupplied = topo.unsupplied_buses(net, respect_switches=respect_switches)
            return success(
                "Unsupplied buses identified",
                unsupplied_buses=sorted(int(b) for b in unsupplied),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to find unsupplied buses: {exc}")

    @mcp.tool()
    def find_connected_components(
        respect_switches: bool = True,
    ) -> Dict[str, Any]:
        """Find all electrically connected bus components in the network."""
        logger.info("Finding connected components")
        try:
            net = get_network()
            graph = create_nxgraph(net, respect_switches=respect_switches)
            components = [
                sorted(int(b) for b in component)
                for component in topo.connected_components(graph)
            ]
            return success(
                f"Found {len(components)} connected components",
                components=components,
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to find connected components: {exc}")

    @mcp.tool()
    def calc_distance_to_bus(
        source_bus: int,
        respect_switches: bool = True,
    ) -> Dict[str, Any]:
        """Calculate shortest electrical distance from a source bus to all other buses."""
        logger.info("Calculating distance to bus %s", source_bus)
        try:
            net = get_network()
            distances = topo.calc_distance_to_bus(
                net, source_bus, respect_switches=respect_switches
            )
            return success(
                f"Distances from bus {source_bus} calculated",
                distances_km=serialize_series(distances),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to calculate distance to bus: {exc}")

    @mcp.tool()
    def find_stubs(roots: Optional[List[int]] = None) -> Dict[str, Any]:
        """Identify stub buses and lines in the network."""
        logger.info("Finding network stubs")
        try:
            net = get_network()
            topo.determine_stubs(net, roots=roots)
            stub_buses = net.bus.index[net.bus.get("on_stub", False)].tolist()
            stub_lines = net.line.index[net.line.get("is_stub", False)].tolist()
            return success(
                "Stub analysis completed",
                stub_buses=[int(b) for b in stub_buses],
                stub_lines=[int(l) for l in stub_lines],
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to find stubs: {exc}")

    @mcp.tool()
    def get_admittance_matrix(
        run_power_flow_first: bool = True,
        matrix_type: str = "ybus",
    ) -> Dict[str, Any]:
        """Export the network admittance matrix (Y-bus) for the current network."""
        logger.info("Exporting admittance matrix")
        try:
            net = get_network()
            if run_power_flow_first:
                pp.runpp(net)
            if "_ppc" in net and "internal" in net["_ppc"]:
                ppci = net["_ppc"]["internal"]
                base_mva = float(ppci["baseMVA"])
                bus = ppci["bus"]
                branch = ppci["branch"]
            else:
                ppc = to_ppc(net, calculate_voltage_angles=True)
                base_mva = float(ppc["baseMVA"])
                bus = ppc["bus"]
                branch = ppc["branch"]
            ybus, yf, yt = makeYbus(base_mva, bus, branch)
            matrix = {"ybus": ybus, "yf": yf, "yt": yt}.get(matrix_type.lower(), ybus)
            return success(
                f"{matrix_type.upper()} matrix exported",
                base_mva=base_mva,
                matrix=serialize_sparse_matrix(matrix),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to export admittance matrix: {exc}")
