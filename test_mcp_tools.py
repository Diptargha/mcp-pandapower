"""Integration tests for pandapower MCP tools."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pandapower as pp

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from network_state import collect_pf_results, set_network
from tools.analysis import _prepare_short_circuit_net


def test_power_flow_on_test_case() -> None:
    net = pp.from_json(ROOT / "test_case.json")
    set_network(net)
    pp.runpp(net, algorithm="nr", init="auto")
    results = collect_pf_results(net)
    assert net.converged
    assert results["bus_results"]["vm_pu"]["0"] > 1.0


def test_contingency_on_test_case() -> None:
    import pandapower.contingency as contingency

    from network_state import build_nminus1_cases

    net = pp.from_json(ROOT / "test_case.json")
    cases = build_nminus1_cases(net, ["line", "trafo"])
    contingency.run_contingency(net, cases, write_to_net=True)
    assert "max_vm_pu" in net.res_bus.columns


def test_short_circuit_on_test_case() -> None:
    from pandapower.shortcircuit.calc_sc import calc_sc

    net = pp.from_json(ROOT / "test_case.json")
    net.ext_grid["s_sc_max_mva"] = 1000
    net.ext_grid["s_sc_min_mva"] = 500
    _prepare_short_circuit_net(net)
    pp.runpp(net)
    calc_sc(net, case="max")
    assert "ikss_ka" in net.res_bus_sc.columns


def test_example_network_and_topology() -> None:
    import pandapower.networks as pn
    import pandapower.topology as topo
    from pandapower.pypower.makeYbus import makeYbus
    from pandapower.topology.create_graph import create_nxgraph

    net = pn.case14()
    set_network(net)
    pp.runpp(net)
    graph = create_nxgraph(net)
    components = list(topo.connected_components(graph))
    assert len(components) >= 1
    ppci = net["_ppc"]["internal"]
    ybus, _, _ = makeYbus(ppci["baseMVA"], ppci["bus"], ppci["branch"])
    assert ybus.shape[0] > 0


def test_timeseries_scaling() -> None:
    base = pp.from_json(ROOT / "test_case.json")
    for scale in (0.8, 1.0, 1.2):
        step = deepcopy(base)
        step.load["scaling"] = step.load["scaling"] * scale
        pp.runpp(step)
        assert step.converged


def test_mcp_tool_registration() -> None:
    from panda_mcp import mcp

    tool_names = {tool.name for tool in mcp._tool_manager.list_tools()}
    expected = {
        "load_network",
        "save_network",
        "run_power_flow",
        "run_contingency_analysis",
        "run_diagnostic",
        "run_opf",
        "run_short_circuit",
        "get_admittance_matrix",
        "load_example_network",
        "create_element",
    }
    assert expected.issubset(tool_names)
    assert len(tool_names) >= 25


if __name__ == "__main__":
    test_power_flow_on_test_case()
    test_contingency_on_test_case()
    test_short_circuit_on_test_case()
    test_example_network_and_topology()
    test_timeseries_scaling()
    test_mcp_tool_registration()
    print("All MCP integration tests passed.")
