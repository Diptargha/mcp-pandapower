# Pandapower MCP Server

MCP server for [pandapower](https://pandapower.readthedocs.io/en/latest/) transmission system analysis.

## Requirements

- Python 3.10+
- pandapower, mcp, openpyxl

```bash
pip install -r requirements.txt
```

## Usage

Run the MCP server:

```bash
python panda_mcp.py
```

Configure in Cursor (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "pandapower": {
      "command": "/path/to/mcp_pandapower/.venv/bin/python",
      "args": ["/path/to/mcp_pandapower/panda_mcp.py"]
    }
  }
}
```

Restart the MCP server in Cursor after code changes.

## Available Tools (28)

### Network I/O
- `create_empty_network()` — create blank network
- `load_network(file_path)` — load `.json`, `.p`, `.xlsx`, `.sqlite`
- `save_network(file_path, include_results)` — save current network
- `load_example_network(network_name)` — load benchmark/test networks (case14, mv_oberrhein, …)
- `get_network_info()` — bus/line/trafo statistics and data

### Power Flow
- `run_power_flow(...)` — AC or DC power flow with extended options
- `run_power_flow_3ph(...)` — three-phase power flow
- `run_diagnostic(report_style, warnings_only)` — convergence diagnostics

### Analysis
- `run_contingency_analysis(...)` — N-1 contingency via native pandapower API
- `run_opf(init, verbose)` — AC optimal power flow
- `run_dc_opf(verbose)` — DC optimal power flow
- `check_opf_setup()` — validate OPF configuration
- `run_short_circuit(...)` — short-circuit calculation
- `run_state_estimation(...)` — weighted least-squares state estimation
- `create_measurement(...)` — add SE measurement
- `remove_bad_measurements(...)` — bad-data removal
- `run_grid_equivalent(...)` — ward/rei/xward equivalents
- `run_timeseries(time_steps, load_scale_profile, sgen_scale_profile)` — scaled time-series PF

### Topology
- `find_unsupplied_buses(respect_switches)`
- `find_connected_components(respect_switches)`
- `calc_distance_to_bus(source_bus, respect_switches)`
- `find_stubs(roots)`
- `get_admittance_matrix(run_power_flow_first, matrix_type)` — Y-bus export

### Build & Convert
- `create_element(element_type, parameters)`
- `modify_element(element_type, index, parameters)`
- `delete_element(element_type, index)`
- `import_matpower(mpc_file_path, f_hz)`
- `export_pypower(calculate_voltage_angles)`

## Tests

```bash
python test_mcp_tools.py
```

## Project Structure

```
mcp_pandapower/
  panda_mcp.py          # entry point
  network_state.py      # shared state and helpers
  tools/
    io.py               # load/save/example networks
    power_flow.py       # power flow and diagnostics
    analysis.py         # contingency, OPF, SC, SE, equivalent, timeseries
    topology.py         # topology searches and Y-bus
    build.py            # element CRUD and converters
```
