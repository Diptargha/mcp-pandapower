"""Power flow and diagnostic MCP tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

import pandapower as pp
from pandapower.diagnostic.diagnostic_helpers import diagnostic

from network_state import collect_pf_results, error, get_network, serialize_dataframe, success

logger = logging.getLogger(__name__)


def register_tools(mcp) -> None:
    @mcp.tool()
    def run_power_flow(
        algorithm: str = "nr",
        calculate_voltage_angles: bool = True,
        max_iteration: int = 10,
        tolerance_mva: float = 1e-8,
        init: str = "auto",
        trafo_model: str = "t",
        tdpf: bool = False,
        run_dc_power_flow: bool = False,
        run_diagnostic_on_failure: bool = False,
    ) -> Dict[str, Any]:
        """Run AC or DC power flow analysis on the current network."""
        logger.info("Running power flow analysis")
        try:
            net = get_network()
            if run_dc_power_flow:
                pp.rundcpp(net)
            else:
                pp.runpp(
                    net,
                    algorithm=algorithm,
                    calculate_voltage_angles=calculate_voltage_angles,
                    max_iteration=max_iteration,
                    tolerance_mva=tolerance_mva,
                    init=init,
                    trafo_model=trafo_model,
                    tdpf=tdpf,
                )
            results = collect_pf_results(net)
            response: Dict[str, Any] = {
                "status": "success",
                "message": (
                    "Power flow calculation completed successfully"
                    if net.converged
                    else "Power flow did not converge"
                ),
                "results": results,
            }
            if not net.converged and run_diagnostic_on_failure:
                diag = diagnostic(
                    net, report_style=None, return_result_dict=True, warnings_only=True
                )
                response["diagnostic"] = _serialize_diagnostic(diag)
            return response
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Power flow calculation failed: {exc}")

    @mcp.tool()
    def run_power_flow_3ph(
        max_iteration: int = 10,
        tolerance_mva: float = 1e-8,
    ) -> Dict[str, Any]:
        """Run asymmetric three-phase power flow on the current network."""
        logger.info("Running three-phase power flow analysis")
        try:
            net = get_network()
            pp.runpp_3ph(
                net,
                max_iteration=max_iteration,
                tolerance_mva=tolerance_mva,
            )
            results = {
                "converged": bool(net.converged),
                "res_bus_3ph": serialize_dataframe(net.res_bus_3ph),
                "res_line_3ph": serialize_dataframe(net.res_line_3ph),
            }
            if hasattr(net, "res_trafo_3ph") and not net.res_trafo_3ph.empty:
                results["res_trafo_3ph"] = serialize_dataframe(net.res_trafo_3ph)
            return success(
                "Three-phase power flow completed successfully"
                if net.converged
                else "Three-phase power flow did not converge",
                results=results,
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Three-phase power flow failed: {exc}")

    @mcp.tool()
    def run_diagnostic(
        report_style: str = "compact",
        warnings_only: bool = False,
    ) -> Dict[str, Any]:
        """Diagnose the current network for common power flow convergence issues."""
        logger.info("Running network diagnostic")
        try:
            net = get_network()
            style = None if report_style.lower() == "none" else report_style
            diag = diagnostic(
                net,
                report_style=style,
                warnings_only=warnings_only,
                return_result_dict=True,
            )
            return success(
                "Network diagnostic completed",
                diagnostic=_serialize_diagnostic(diag),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Network diagnostic failed: {exc}")


def _serialize_diagnostic(diag) -> Dict[str, Any]:
    if diag is None:
        return {}
    serialized: Dict[str, Any] = {}
    for key, value in diag.items():
        if isinstance(value, dict):
            serialized[key] = {
                str(k): (v.tolist() if hasattr(v, "tolist") else v)
                for k, v in value.items()
            }
        elif hasattr(value, "tolist"):
            serialized[key] = value.tolist()
        else:
            serialized[key] = value
    return serialized
