"""Contingency, OPF, short-circuit, state estimation, grid equivalent, and timeseries tools."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

import pandapower as pp
import pandapower.contingency as contingency
from pandapower.estimation import estimate, remove_bad_data
from pandapower.grid_equivalents.get_equivalent import get_equivalent
from pandapower.shortcircuit.calc_sc import calc_sc
from pandapower.toolbox.result_info import opf_task

from network_state import (
    build_nminus1_cases,
    collect_pf_results,
    error,
    get_network,
    require_converged_pf,
    serialize_dataframe,
    set_network,
    success,
)

logger = logging.getLogger(__name__)


def register_tools(mcp) -> None:
    @mcp.tool()
    def run_contingency_analysis(
        element_types: Optional[List[str]] = None,
        element_indices: Optional[Dict[str, List[int]]] = None,
        use_lightsim2g: bool = False,
        write_to_net: bool = True,
    ) -> Dict[str, Any]:
        """Run N-1 contingency analysis using pandapower's native contingency API."""
        logger.info("Running contingency analysis")
        try:
            net = get_network()
            working_net = deepcopy(net)
            if element_types is None:
                element_types = ["line", "trafo", "trafo3w"]
            nminus1_cases = build_nminus1_cases(
                working_net, element_types, element_indices
            )
            if not nminus1_cases:
                return error("No in-service elements found for contingency analysis")

            if use_lightsim2g:
                results = contingency.run_contingency_ls2g(
                    working_net, nminus1_cases, write_to_net=write_to_net
                )
            else:
                results = contingency.run_contingency(
                    working_net, nminus1_cases, write_to_net=write_to_net
                )

            if write_to_net:
                set_network(working_net)
            net = working_net

            limits = contingency.get_element_limits(net)
            within_limits = None
            check_results: Dict[str, Any] = {}
            if limits:
                check_results = {
                    element: results[element]
                    for element in results
                    if element in limits
                }
                if check_results:
                    within_limits = contingency.check_elements_within_limits(
                        limits, check_results, nminus1=True
                    )

            return success(
                "Contingency analysis completed",
                results=_serialize_contingency_results(results),
                within_limits=within_limits,
                res_bus=serialize_dataframe(net.res_bus),
                res_line=serialize_dataframe(net.res_line),
                res_trafo=serialize_dataframe(net.res_trafo),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Contingency analysis failed: {exc}")

    @mcp.tool()
    def run_opf(
        init: str = "flat",
        verbose: bool = False,
        calculate_voltage_angles: bool = True,
    ) -> Dict[str, Any]:
        """Run AC optimal power flow on the current network."""
        logger.info("Running AC optimal power flow")
        try:
            net = get_network()
            pp.runopp(
                net,
                init=init,
                verbose=verbose,
                calculate_voltage_angles=calculate_voltage_angles,
            )
            return success(
                "AC OPF completed successfully"
                if net.converged
                else "AC OPF did not converge",
                results=collect_pf_results(net),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"AC OPF failed: {exc}")

    @mcp.tool()
    def run_dc_opf(verbose: bool = False) -> Dict[str, Any]:
        """Run DC optimal power flow on the current network."""
        logger.info("Running DC optimal power flow")
        try:
            net = get_network()
            pp.rundcopp(net, verbose=verbose)
            return success(
                "DC OPF completed successfully"
                if net.converged
                else "DC OPF did not converge",
                results=collect_pf_results(net),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"DC OPF failed: {exc}")

    @mcp.tool()
    def check_opf_setup() -> Dict[str, Any]:
        """Check whether the current network is suitable for optimal power flow."""
        logger.info("Checking OPF setup")
        try:
            net = get_network()
            task = opf_task(net, keep=True, log=False)
            return success("OPF setup check completed", opf_task=_serialize_opf_task(task))
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"OPF setup check failed: {exc}")

    @mcp.tool()
    def run_short_circuit(
        bus: Optional[List[int]] = None,
        fault: str = "3ph",
        case: str = "max",
        ip: bool = False,
        ith: bool = False,
        tk_s: float = 1.0,
        branch_results: bool = False,
    ) -> Dict[str, Any]:
        """Run short-circuit analysis on the current network."""
        logger.info("Running short-circuit analysis")
        try:
            net = get_network()
            if net.ext_grid.empty:
                return error("Short-circuit analysis requires at least one external grid")
            missing = [
                col
                for col in ("s_sc_max_mva", "s_sc_min_mva")
                if col not in net.ext_grid.columns
                or net.ext_grid[col].isna().all()
            ]
            if missing:
                return error(
                    "External grid is missing short-circuit data. "
                    "Set s_sc_max_mva and s_sc_min_mva on net.ext_grid first."
                )
            _prepare_short_circuit_net(net)
            pp.runpp(net)
            calc_sc(
                net,
                bus=bus,
                fault=fault,
                case=case,
                ip=ip,
                ith=ith,
                tk_s=tk_s,
                branch_results=branch_results,
            )
            results = {"bus_results": serialize_dataframe(net.res_bus_sc)}
            if branch_results and hasattr(net, "res_line_sc"):
                results["line_results"] = serialize_dataframe(net.res_line_sc)
            return success("Short-circuit analysis completed", results=results)
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Short-circuit analysis failed: {exc}")

    @mcp.tool()
    def create_measurement(
        meas_type: str,
        element_type: str,
        value: float,
        std_dev: float,
        element: int,
        side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a measurement on the current network for state estimation."""
        logger.info("Creating measurement")
        try:
            net = get_network()
            idx = pp.create_measurement(
                net,
                meas_type=meas_type,
                element_type=element_type,
                value=value,
                std_dev=std_dev,
                element=element,
                side=side,
            )
            return success(
                f"Measurement created at index {idx}",
                measurement_index=int(idx),
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Failed to create measurement: {exc}")

    @mcp.tool()
    def run_state_estimation(
        algorithm: str = "wls",
        init: str = "flat",
        tolerance: float = 1e-6,
        maximum_iterations: int = 50,
    ) -> Dict[str, Any]:
        """Run weighted least-squares state estimation on the current network."""
        logger.info("Running state estimation")
        try:
            net = get_network()
            converged = estimate(
                net,
                algorithm=algorithm,
                init=init,
                tolerance=tolerance,
                maximum_iterations=maximum_iterations,
            )
            return success(
                "State estimation completed successfully"
                if converged
                else "State estimation did not converge",
                converged=bool(converged),
                results={
                    "res_bus_est": serialize_dataframe(net.res_bus_est),
                    "res_line_est": serialize_dataframe(net.res_line_est),
                },
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"State estimation failed: {exc}")

    @mcp.tool()
    def remove_bad_measurements(
        init: str = "flat",
        tolerance: float = 1e-6,
        maximum_iterations: int = 10,
        rn_max_threshold: float = 3.0,
    ) -> Dict[str, Any]:
        """Run state estimation with bad-data removal."""
        logger.info("Running bad-data removal")
        try:
            net = get_network()
            converged = remove_bad_data(
                net,
                init=init,
                tolerance=tolerance,
                maximum_iterations=maximum_iterations,
                rn_max_threshold=rn_max_threshold,
            )
            return success(
                "Bad-data removal completed successfully"
                if converged
                else "Bad-data removal did not converge",
                converged=bool(converged),
                results={"res_bus_est": serialize_dataframe(net.res_bus_est)},
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Bad-data removal failed: {exc}")

    @mcp.tool()
    def run_grid_equivalent(
        eq_type: str,
        boundary_buses: List[int],
        internal_buses: List[int],
        return_internal: bool = True,
        ward_type: str = "ward_injection",
        replace_current_network: bool = False,
    ) -> Dict[str, Any]:
        """Calculate a grid equivalent (rei, ward, or xward) for the current network."""
        logger.info("Running grid equivalent calculation")
        try:
            net = get_network()
            require_converged_pf(net)
            eq_net = get_equivalent(
                net,
                eq_type=eq_type,
                boundary_buses=boundary_buses,
                internal_buses=internal_buses,
                return_internal=return_internal,
                ward_type=ward_type,
            )
            if replace_current_network:
                set_network(eq_net)
            return success(
                "Grid equivalent calculation completed",
                network_info={
                    "buses": len(eq_net.bus),
                    "lines": len(eq_net.line),
                    "trafos": len(eq_net.trafo),
                },
                replaced_current_network=replace_current_network,
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Grid equivalent calculation failed: {exc}")

    @mcp.tool()
    def run_timeseries(
        time_steps: List[int],
        load_scale_profile: Optional[List[float]] = None,
        sgen_scale_profile: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Run a simplified time-series power flow by scaling loads and sgens per step."""
        logger.info("Running simplified time-series analysis")
        try:
            net = get_network()
            base_net = deepcopy(net)
            load_scales = load_scale_profile or [1.0] * len(time_steps)
            sgen_scales = sgen_scale_profile or [1.0] * len(time_steps)
            if len(load_scales) != len(time_steps) or len(sgen_scales) != len(time_steps):
                return error("Scale profiles must match the length of time_steps")

            step_summaries = []
            for step, load_scale, sgen_scale in zip(time_steps, load_scales, sgen_scales):
                step_net = deepcopy(base_net)
                if not step_net.load.empty:
                    step_net.load["scaling"] = step_net.load["scaling"] * load_scale
                if not step_net.sgen.empty:
                    step_net.sgen["scaling"] = step_net.sgen["scaling"] * sgen_scale
                try:
                    pp.runpp(step_net)
                    step_summaries.append(
                        {
                            "time_step": step,
                            "converged": bool(step_net.converged),
                            "min_vm_pu": float(step_net.res_bus.vm_pu.min()),
                            "max_vm_pu": float(step_net.res_bus.vm_pu.max()),
                            "max_line_loading_percent": float(
                                step_net.res_line.loading_percent.max()
                                if not step_net.res_line.empty
                                else 0.0
                            ),
                        }
                    )
                except Exception as exc:
                    step_summaries.append(
                        {
                            "time_step": step,
                            "converged": False,
                            "error": str(exc),
                        }
                    )

            converged_steps = sum(1 for s in step_summaries if s.get("converged"))
            return success(
                f"Time-series analysis completed ({converged_steps}/{len(time_steps)} converged)",
                step_summaries=step_summaries,
            )
        except RuntimeError as exc:
            return error(str(exc))
        except Exception as exc:
            return error(f"Time-series analysis failed: {exc}")


def _serialize_opf_task(task: Dict[str, Any]) -> Dict[str, Any]:
    serialized: Dict[str, Any] = {}
    for key, value in task.items():
        if isinstance(value, dict):
            serialized[key] = {
                str(k): (v.tolist() if hasattr(v, "tolist") else v)
                for k, v in value.items()
            }
        else:
            serialized[key] = value
    return serialized


def _prepare_short_circuit_net(net) -> None:
    """Ensure required short-circuit columns exist on generators and ext_grid."""
    if not net.gen.empty:
        if "vn_kv" not in net.gen.columns:
            net.gen["vn_kv"] = net.gen["bus"].map(net.bus.vn_kv)
        defaults = {
            "sn_mva": 100.0,
            "xdss_pu": 0.2,
            "rdss_ohm": 0.0,
            "cos_phi": 0.85,
            "pg_percent": 0.0,
        }
        for col, default in defaults.items():
            if col not in net.gen.columns:
                net.gen[col] = default
        if "sn_mva" in net.gen.columns:
            net.gen["sn_mva"] = net.gen["sn_mva"].fillna(100.0)
    if not net.sgen.empty:
        if "sn_mva" not in net.sgen.columns or net.sgen["sn_mva"].isna().any():
            fill = net.sgen["p_mw"].abs().clip(lower=1.0) * 1.2
            if "sn_mva" not in net.sgen.columns:
                net.sgen["sn_mva"] = fill
            else:
                net.sgen["sn_mva"] = net.sgen["sn_mva"].fillna(fill)
        if "current_source" in net.sgen.columns:
            current_sources = net.sgen["current_source"].fillna(False)
            if current_sources.any():
                if "k" not in net.sgen.columns:
                    net.sgen["k"] = 1.0
                net.sgen.loc[current_sources, "k"] = net.sgen.loc[
                    current_sources, "k"
                ].fillna(1.0)
                if "kappa" not in net.sgen.columns:
                    net.sgen["kappa"] = 1.0
                net.sgen.loc[current_sources, "kappa"] = net.sgen.loc[
                    current_sources, "kappa"
                ].fillna(1.0)
    for col, default in (("rx_max", 0.1), ("rx_min", 0.1)):
        if col not in net.ext_grid.columns:
            net.ext_grid[col] = default
        net.ext_grid[col] = net.ext_grid[col].fillna(default)


def _serialize_contingency_results(results: Dict[str, Any]) -> Dict[str, Any]:
    serialized: Dict[str, Any] = {}
    for element_type, element_results in results.items():
        serialized[element_type] = {}
        for key, values in element_results.items():
            if hasattr(values, "tolist"):
                serialized[element_type][key] = values.tolist()
            else:
                serialized[element_type][key] = values
    return serialized
