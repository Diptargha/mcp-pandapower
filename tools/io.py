"""Network I/O and example network loading tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandapower as pp
import pandapower.networks as pn

from network_state import error, network_info, set_network, success

logger = logging.getLogger(__name__)

EXAMPLE_NETWORKS = {
    "case4gs": pn.case4gs,
    "case5": pn.case5,
    "case6ww": pn.case6ww,
    "case9": pn.case9,
    "case14": pn.case14,
    "case30": pn.case30,
    "case39": pn.case39,
    "case57": pn.case57,
    "case118": pn.case118,
    "case9241pegase": pn.case9241pegase,
    "mv_oberrhein": pn.mv_oberrhein,
    "panda_four_load_branch": pn.panda_four_load_branch,
    "four_loads_with_branches_out": pn.four_loads_with_branches_out,
    "simple_four_bus_system": pn.simple_four_bus_system,
    "simple_mv_open_ring_net": pn.simple_mv_open_ring_net,
}


def register_tools(mcp) -> None:
    @mcp.tool()
    def create_empty_network() -> Dict[str, Any]:
        """Create an empty pandapower network."""
        logger.info("Creating an empty pandapower network")
        try:
            net = pp.create_empty_network()
            set_network(net)
            return success(
                "Empty network created successfully",
                network_info=network_info(net),
            )
        except Exception as exc:
            return error(f"Failed to create empty network: {exc}")

    @mcp.tool()
    def load_network(file_path: str) -> Dict[str, Any]:
        """Load a pandapower network from a file (.json, .p, .xlsx, .sqlite)."""
        logger.info("Loading network from file: %s", file_path)
        try:
            lower = file_path.lower()
            if lower.endswith(".json"):
                net = pp.from_json(file_path)
            elif lower.endswith(".p"):
                net = pp.from_pickle(file_path)
            elif lower.endswith((".xlsx", ".xls")):
                net = pp.from_excel(file_path)
            elif lower.endswith(".sqlite"):
                net = pp.from_sqlite(file_path)
            else:
                return error(
                    "Unsupported file format. Use .json, .p, .xlsx, or .sqlite files."
                )
            set_network(net)
            return success(
                f"Network loaded successfully from {file_path}",
                network_info=network_info(net),
            )
        except FileNotFoundError:
            return error(f"File not found: {file_path}")
        except Exception as exc:
            return error(f"Failed to load network: {exc}")

    @mcp.tool()
    def save_network(file_path: str, include_results: bool = True) -> Dict[str, Any]:
        """Save the current pandapower network to a file (.json or .p)."""
        from network_state import get_network

        logger.info("Saving network to file: %s", file_path)
        try:
            net = get_network()
            lower = file_path.lower()
            if lower.endswith(".json"):
                pp.to_json(net, file_path)
            elif lower.endswith(".p"):
                pp.to_pickle(net, file_path)
            elif lower.endswith((".xlsx", ".xls")):
                pp.to_excel(net, file_path, include_results=include_results)
            elif lower.endswith(".sqlite"):
                pp.to_sqlite(net, file_path, include_results=include_results)
            else:
                return error(
                    "Unsupported file format. Use .json, .p, .xlsx, or .sqlite files."
                )
            return success(f"Network saved successfully to {file_path}")
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to save network: {exc}")

    @mcp.tool()
    def load_example_network(network_name: str) -> Dict[str, Any]:
        """Load a built-in pandapower example or benchmark network by name."""
        logger.info("Loading example network: %s", network_name)
        if network_name not in EXAMPLE_NETWORKS:
            return error(
                f"Unknown network '{network_name}'. "
                f"Available: {sorted(EXAMPLE_NETWORKS.keys())}"
            )
        try:
            net = EXAMPLE_NETWORKS[network_name]()
            set_network(net)
            return success(
                f"Example network '{network_name}' loaded successfully",
                network_info=network_info(net),
            )
        except Exception as exc:
            return error(f"Failed to load example network: {exc}")

    @mcp.tool()
    def get_network_info() -> Dict[str, Any]:
        """Get statistics and element data for the current network."""
        from network_state import get_network, serialize_dataframe

        logger.info("Retrieving network information")
        try:
            net = get_network()
            info = {
                **network_info(net),
                "bus_data": serialize_dataframe(net.bus),
                "line_data": serialize_dataframe(net.line),
                "trafo_data": serialize_dataframe(net.trafo),
            }
            return success(
                "Network information retrieved successfully",
                info=info,
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to get network information: {exc}")
