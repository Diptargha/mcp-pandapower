"""Shared network state and helper utilities for the pandapower MCP server."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import pandapower as pp

_current_net: Optional[pp.pandapowerNet] = None


def get_network() -> pp.pandapowerNet:
    if _current_net is None:
        raise RuntimeError(
            "No pandapower network is currently loaded. Please create or load a network first."
        )
    return _current_net


def set_network(net: pp.pandapowerNet) -> None:
    global _current_net
    _current_net = net


def network_info(net: pp.pandapowerNet) -> Dict[str, int]:
    return {
        "buses": len(net.bus),
        "lines": len(net.line),
        "trafos": len(net.trafo),
        "generators": len(net.gen),
        "loads": len(net.load),
        "switches": len(net.switch),
    }


def success(message: str, **payload: Any) -> Dict[str, Any]:
    return {"status": "success", "message": message, **payload}


def error(message: str) -> Dict[str, Any]:
    return {"status": "error", "message": message}


def serialize_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {}
    serialized = df.copy()
    serialized.index = serialized.index.astype(str)
    return serialized.to_dict()


def serialize_series(series: pd.Series) -> Dict[str, Any]:
    if series is None or series.empty:
        return {}
    return {str(k): v for k, v in series.to_dict().items()}


def serialize_sparse_matrix(matrix) -> Dict[str, Any]:
    coo = matrix.tocoo()
    return {
        "n_rows": int(matrix.shape[0]),
        "n_cols": int(matrix.shape[1]),
        "rows": coo.row.tolist(),
        "cols": coo.col.tolist(),
        "data_real": np.real(coo.data).tolist(),
        "data_imag": np.imag(coo.data).tolist(),
    }


def collect_pf_results(net: pp.pandapowerNet) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "bus_results": serialize_dataframe(net.res_bus),
        "line_results": serialize_dataframe(net.res_line),
        "trafo_results": serialize_dataframe(net.res_trafo),
        "converged": bool(net.converged),
    }
    for table in ("res_load", "res_gen", "res_sgen", "res_ext_grid", "res_trafo3w"):
        if hasattr(net, table):
            df = getattr(net, table)
            if not df.empty:
                results[table] = serialize_dataframe(df)
    return results


def require_converged_pf(net: pp.pandapowerNet) -> None:
    if not getattr(net, "converged", False):
        raise RuntimeError(
            "A converged power flow is required. Run run_power_flow first."
        )


def build_nminus1_cases(
    net: pp.pandapowerNet,
    element_types: List[str],
    element_indices: Optional[Dict[str, List[int]]] = None,
) -> Dict[str, Dict[str, List[int]]]:
    cases: Dict[str, Dict[str, List[int]]] = {}
    for element_type in element_types:
        if element_type not in net or net[element_type].empty:
            continue
        if element_indices and element_type in element_indices:
            indices = element_indices[element_type]
        else:
            indices = net[element_type].index[
                net[element_type]["in_service"]
            ].tolist()
        if indices:
            cases[element_type] = {"index": indices}
    return cases
