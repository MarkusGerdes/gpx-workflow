# Power Visualization Installation Guide

## Required Dependencies

For the power visualization to work correctly, you need to install the following Python packages:

```bash
# Core packages (should already be installed)
pip install pandas numpy plotly

# Required for PNG export
pip install kaleido

# For YAML config loading
pip install pyyaml
```

## Package Descriptions

- **plotly**: For creating interactive visualizations
- **kaleido**: Required for static image export (PNG generation)
- **pyyaml**: For loading surface colors from config.yaml

## Installation Verification

Test if kaleido is working:

```python
import plotly.graph_objects as go
fig = go.Figure(go.Scatter(x=[1,2,3], y=[1,2,3]))
fig.write_image("test.png")  # Should work without errors
```

If this fails, kaleido may need additional system dependencies on Linux/WSL.

## File Integration Summary

The power visualization is now integrated into your pipeline:

1. **10b_power_processing.py** - Generates power/speed data
2. **10c_power_visualization.py** - Creates visualization (NEW)
3. **11_generate_stage_summary.py** - Includes visualization in report (UPDATED)
4. **Snakefile** - Orchestrates the workflow (UPDATED)

## Output Files

- `output/10c_{basename}_power_visualization.html` - Interactive visualization
- `output/10c_{basename}_power_visualization.png` - Static image for reports
- Power visualization is embedded in Stage Summary report

## Features

✅ Gradient-colored elevation profile (steepness visualization)
✅ Surface type background segments (your established colors)
✅ Dual Y-axis for elevation and power/speed
✅ Interactive hover information
✅ Analysis and Simulation mode support
✅ Automatic integration in Stage Summary
✅ Metadata tracking compatible with v2.0.0 system
