---
name: openbb-widget-spec
description: The `openbb-widget-spec` skill is designed to generate a comprehensive widget specification from a provided URL. This widget specification serves as a blueprint for creating interactive widgets on the OpenBB Workspace dashboard. The process involves retrieving a JSON data structure from the specified URL and generating a specification that defines how this JSON data should be rendered, formatted, and interacted with within the widget.
---

# OpenBB Widget Specification Generator

## Overview

The `openbb-widget-spec` skill generates comprehensive widget specifications for the OpenBB Workspace dashboard. By analyzing JSON data from a provided URL, it creates a structured configuration that defines how the data should be visualized and interacted with in a widget.

## Widget Specification Structure

A widget specification is defined in a `widgets.json` file with the following key components:

### Basic Information
- **name**: Display name of the widget
- **description**: Brief description of the widget's functionality
- **endpoint**: Backend API endpoint for data retrieval
- **wsEndpoint**: Optional WebSocket endpoint for live data updates

### Metadata
- **category**: Category for widget organization
- **subCategory**: Secondary category for refined search
- **imgUrl**: Image URL for widget preview

### Display Settings
- **type**: Default visualization type (chart, table, markdown, etc.)
- **raw**: Boolean for Plotly chart/raw data toggle
- **runButton**: Boolean for run button instead of refresh
- **exportable**: Boolean for data export capability
- **gridData**: Widget dimensions and constraints (width, height, min/max values)

### Data Configuration
- **data**: Configuration for AgGrid Table widgets
  - **dataKey**: Key to identify data within the widget
  - **wsRowIdColumn**: Column for identifying rows in live data
  - **table**: Table-specific settings
    - **enableCharts**: Enable chart visualization
    - **showAll**: Display all available data
    - **transpose**: Transpose table data
    - **enableAdvanced**: Enable advanced table features
    - **enableFormulas**: Enable table formulas
    - **formatterFn**: Default formatting function
    - **chartView**: Chart-specific settings
  - **columnsDefs**: Column-level configurations

### Parameters
- **params**: List of parameters for widget customization
  - **type**: Parameter type (date, text, ticker, number, boolean, etc.)
  - **paramName**: Parameter name in URL
  - **value**: Default parameter value
  - **label**: UI display label
  - **options**: Dropdown options for parameter
  - **multiSelect**: Allow multiple selections
  - **show**: Display parameter in UI
  - **description**: Parameter description

### Advanced Settings
- **source**: Data source(s) for the widget
- **mcp_tool**: Configuration for MCP tool matching
- **refetchInterval**: Data refresh interval in milliseconds
- **staleTime**: Time before data is considered stale

## Supported Widget Types

- `chart`: Interactive charts
- `table`: Data tables
- `table_ssrm`: Server-side rendered tables
- `markdown`: Markdown content
- `metric`: Key performance indicators
- `note`: Text notes
- `multi_file_viewer`: File viewing
- `live_grid`: Real-time data grids
- `newsfeed`: News feeds
- `advanced-chart`: Advanced charting
- `chart-highcharts`: Highcharts integration
- `youtube`: YouTube videos

## Example Widget Configuration

```json
{
  "custom_widget": {
    "id": "user-data-widget",
    "name": "Custom Widget Example",
    "description": "A widget to demonstrate custom configuration",
    "endpoint": "custom-endpoint",
    "runButton": false,
    "exportable": false,
    "data": {
      "dataKey": "customDataKey",
      "table": {
        "enableCharts": true,
        "showAll": true,
        "enableAdvanced": true,
        "enableFormulas": true,
        "chartView": {
          "enabled": true,
          "chartType": "column",
          "cellRangeCols": {
            "line": ["ticker", "weight"]
          }
        },
        "columnsDefs": [
          {
            "field": "column1",
            "headerName": "Column 1",
            "chartDataType": "category",
            "cellDataType": "text",
            "formatterFn": "none",
            "renderFn": "titleCase",
            "width": 100
          },
          {
            "field": "column2",
            "headerName": "Column 2",
            "chartDataType": "series",
            "cellDataType": "number",
            "formatterFn": "int",
            "decimalPlaces": 2,
            "renderFn": "greenRed",
            "width": 150
          }
        ]
      }
    },
    "params": [
      {
        "type": "date",
        "paramName": "startDate",
        "value": "2024-01-01",
        "label": "Start Date",
        "show": true,
        "description": "The start date for the data"
      },
      {
        "type": "text",
        "paramName": "ticker",
        "value": "AAPL",
        "label": "Ticker",
        "show": true,
        "description": "Stock ticker symbol"
      }
    ],
    "source": ["My First API"],
    "refetchInterval": 900000,
    "staleTime": 300000
  }
}
```

## How It Works

1. **Data Retrieval**: The skill fetches JSON data from the provided URL
2. **Structure Analysis**: It analyzes the JSON structure to identify data types and relationships
3. **Specification Generation**: It generates a widget specification based on the analyzed data
4. **Configuration Optimization**: It optimizes the configuration for the most appropriate visualization type
5. **Output**: It returns the complete widget specification ready for use in OpenBB Workspace

## Use Cases

- **API Integration**: Create widgets for custom API endpoints
- **Data Visualization**: Generate visualizations for structured data sources
- **Dashboard Creation**: Build comprehensive dashboards with multiple widgets
- **Real-time Data**: Configure live data widgets with WebSocket support

## Best Practices

- **Clear Naming**: Use descriptive names and descriptions for widgets
- **Appropriate Visualization**: Select the right widget type for your data
- **Parameter Configuration**: Define meaningful parameters for user customization
- **Performance Optimization**: Set appropriate refresh intervals and stale times
- **Responsive Design**: Configure grid dimensions for optimal dashboard layout

## Output Format

The skill returns a JSON object representing the complete widget specification, ready to be added to a `widgets.json` file in your OpenBB extension or backend.

### Reference Widget Configurations

The following reference widget configurations are available:

- [User Data Widget](references/user-data-widget.json) - Reference implementation showing:
  - Basic widget structure with id, name, description
  - Table widget type configuration
  - Select, boolean, and number parameter types
  - Grid data dimensions
  - External API endpoint integration

**Reference Pattern**: When generating widget specs, use the user-data-widget.json structure as a template for simple table widgets with filter parameters.
