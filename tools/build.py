"""Network element creation, modification, and import/export MCP tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandapower as pp
from pandapower.converter.matpower.from_mpc import from_mpc
from pandapower.converter.pypower.to_ppc import to_ppc

from network_state import error, get_network, set_network, success

logger = logging.getLogger(__name__)

CREATE_DISPATCH = {
    "bus": lambda net, params: pp.create_bus(net, **params),
    "line": lambda net, params: pp.create_line(net, **params),
    "load": lambda net, params: pp.create_load(net, **params),
    "gen": lambda net, params: pp.create_gen(net, **params),
    "sgen": lambda net, params: pp.create_sgen(net, **params),
    "ext_grid": lambda net, params: pp.create_ext_grid(net, **params),
    "trafo": lambda net, params: pp.create_transformer(net, **params),
    "shunt": lambda net, params: pp.create_shunt(net, **params),
    "switch": lambda net, params: pp.create_switch(net, **params),
    "storage": lambda net, params: pp.create_storage(net, **params),
}


def register_tools(mcp) -> None:
    @mcp.tool()
    def create_element(element_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a network element (bus, line, load, gen, sgen, ext_grid, trafo, shunt, switch, storage)."""
        logger.info("Creating element of type %s", element_type)
        if element_type not in CREATE_DISPATCH:
            return error(
                f"Unsupported element type '{element_type}'. "
                f"Supported: {sorted(CREATE_DISPATCH.keys())}"
            )
        try:
            net = get_network()
            index = CREATE_DISPATCH[element_type](net, parameters)
            return success(
                f"{element_type} created at index {index}",
                element_type=element_type,
                element_index=int(index),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to create element: {exc}")

    @mcp.tool()
    def modify_element(
        element_type: str,
        index: int,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Modify parameters of an existing network element."""
        logger.info("Modifying %s element %s", element_type, index)
        try:
            net = get_network()
            if element_type not in net:
                return error(f"Unknown element table '{element_type}'")
            if index not in net[element_type].index:
                return error(f"{element_type} index {index} not found")
            for key, value in parameters.items():
                net[element_type].at[index, key] = value
            return success(
                f"{element_type} element {index} updated",
                updated_parameters=list(parameters.keys()),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to modify element: {exc}")

    @mcp.tool()
    def delete_element(element_type: str, index: int) -> Dict[str, Any]:
        """Delete a network element by type and index."""
        logger.info("Deleting %s element %s", element_type, index)
        try:
            net = get_network()
            if element_type not in net:
                return error(f"Unknown element table '{element_type}'")
            if index not in net[element_type].index:
                return error(f"{element_type} index {index} not found")
            net[element_type].drop(index, inplace=True)
            return success(f"{element_type} element {index} deleted")
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to delete element: {exc}")

    @mcp.tool()
    def import_matpower(mpc_file_path: str, f_hz: float = 50.0) -> Dict[str, Any]:
        """Import a MATPOWER case file (.m or .mat) as the current network."""
        logger.info("Importing MATPOWER file: %s", mpc_file_path)
        try:
            net = from_mpc(mpc_file_path, f_hz=f_hz)
            set_network(net)
            return success(
                f"MATPOWER file imported from {mpc_file_path}",
                network_info={
                    "buses": len(net.bus),
                    "lines": len(net.line),
                    "trafos": len(net.trafo),
                },
            )
        except Exception as exc:
            return error(f"Failed to import MATPOWER file: {exc}")

    @mcp.tool()
    def export_pypower(calculate_voltage_angles: bool = True) -> Dict[str, Any]:
        """Export the current network as a PYPOWER case structure."""
        logger.info("Exporting PYPOWER case")
        try:
            net = get_network()
            ppc = to_ppc(net, calculate_voltage_angles=calculate_voltage_angles)
            serialized = {
                "version": ppc.get("version"),
                "baseMVA": float(ppc["baseMVA"]),
                "bus": ppc["bus"].tolist(),
                "branch": ppc["branch"].tolist(),
                "gen": ppc["gen"].tolist(),
            }
            return success("PYPOWER case exported", ppc=serialized)
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to export PYPOWER case: {exc}")
