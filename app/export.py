"""
Export module for Portfolio Optimizer.

This module handles all data export functionality (CSV, Excel) in isolation
from UI and business logic.
"""

from typing import Optional
from io import BytesIO
import pandas as pd
import copy

from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

from .config import EXCEL_SCALE, EXCEL_MAX_COLUMN_WIDTH, PIE_CHART_EMU_WIDTH, PIE_CHART_EMU_HEIGHT, CUMULATIVE_CHART_EMU_WIDTH, CUMULATIVE_CHART_EMU_HEIGHT


def generate_csv_holdings(holdings_display: pd.DataFrame) -> str:
    """
    Generate CSV string for holdings table.
    
    Args:
        holdings_display: Holdings DataFrame to export
    
    Returns:
        CSV-formatted string
    """
    return holdings_display.to_csv(index=False)


def generate_excel_full_page(
    comparison_df: pd.DataFrame,
    holdings_display: pd.DataFrame,
    period_days: int,
    fig_pie,
    fig_chart
) -> BytesIO:
    """
    Generate comprehensive Excel workbook with metrics, holdings, and charts.
    
    Layout:
    - Row 1: Title
    - Row 2: Period info
    - Row 3+: Summary returns table
    - Below: Holdings table
    - Bottom: Pie chart (left, 10x10) and Cumulative chart (right, 10x30) side by side
    
    Args:
        comparison_df: Performance comparison DataFrame
        holdings_display: Holdings table DataFrame
        period_days: Number of days in the analysis period
        fig_pie: Plotly pie chart figure
        fig_chart: Plotly cumulative return chart figure
    
    Returns:
        BytesIO object containing Excel workbook
    
    Raises:
        ValueError: If figures cannot be converted to images
    """
    buffer = BytesIO()
    
    try:
        # Create copies of figures to avoid modifying originals
        fig_pie_export = copy.deepcopy(fig_pie)
        fig_chart_export = copy.deepcopy(fig_chart)
        
        # Ensure background is white and colors are visible
        fig_pie_export.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='black')
        )
        
        fig_chart_export.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='black')
        )
        
        # Convert Plotly figures to PNG images in memory with proper settings
        pie_image_bytes = BytesIO(
            fig_pie_export.to_image(
                format="png",
                width=400,
                height=400,
                scale=EXCEL_SCALE
            )
        )
        pie_image_bytes.seek(0)
        
        chart_image_bytes = BytesIO(
            fig_chart_export.to_image(
                format="png",
                width=1000,
                height=500,
                scale=EXCEL_SCALE
            )
        )
        chart_image_bytes.seek(0)
        
        # Create Excel workbook
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Sheet 1: MaxSharpe with all portfolio output
            comparison_df.to_excel(
                writer,
                sheet_name='MaxSharpe',
                startrow=2,
                index=True
            )
            ws_main = writer.sheets['MaxSharpe']
            
            # Add title and period info
            ws_main['A1'] = 'Maximum Sharpe Portfolio Analysis'
            ws_main['A2'] = f'Analysis Period: {period_days} days'
            
            # Adjust column widths for summary table
            for col_idx, col in enumerate(comparison_df.columns, 1):
                max_length = len(str(col))
                col_letter = get_column_letter(col_idx + 1)  # +1 for index column
                for val in comparison_df[col]:
                    max_length = max(max_length, len(str(val)))
                ws_main.column_dimensions[col_letter].width = min(max_length + 2, EXCEL_MAX_COLUMN_WIDTH)
            
            # Calculate position for holdings table (below summary table)
            summary_last_row = 3 + len(comparison_df)
            holdings_header_row = summary_last_row + 2
            holdings_data_start_row = holdings_header_row + 1
            
            # Add holdings header
            ws_main[f'A{holdings_header_row}'] = 'Holdings'
            
            # Write holdings table to the sheet
            for col_idx, col_name in enumerate(holdings_display.columns, 1):
                ws_main.cell(row=holdings_data_start_row, column=col_idx, value=col_name)
            
            for row_idx, row_data in enumerate(holdings_display.values, holdings_data_start_row + 1):
                for col_idx, value in enumerate(row_data, 1):
                    ws_main.cell(row=row_idx, column=col_idx, value=value)
            
            # Adjust column widths for holdings table
            for col_idx, col in enumerate(holdings_display.columns, 1):
                max_length = len(str(col))
                col_letter = get_column_letter(col_idx)
                for val in holdings_display[col]:
                    max_length = max(max_length, len(str(val)))
                ws_main.column_dimensions[col_letter].width = min(max_length + 2, EXCEL_MAX_COLUMN_WIDTH)
            
            # Calculate position for charts (below holdings table)
            holdings_last_row = holdings_data_start_row + len(holdings_display)
            charts_header_row = holdings_last_row + 2
            charts_data_row = charts_header_row + 1
            
            # Add charts header
            ws_main[f'A{charts_header_row}'] = 'Portfolio Allocation & Performance'
            
            # Add pie chart on the left (column A)
            pie_img = XLImage(pie_image_bytes)
            pie_img.width = PIE_CHART_EMU_WIDTH
            pie_img.height = PIE_CHART_EMU_HEIGHT
            ws_main.add_image(pie_img, f'A{charts_data_row}')
            
            # Add cumulative chart on the right (column E, giving space for pie chart)
            chart_img = XLImage(chart_image_bytes)
            chart_img.width = CUMULATIVE_CHART_EMU_WIDTH
            chart_img.height = CUMULATIVE_CHART_EMU_HEIGHT
            ws_main.add_image(chart_img, f'E{charts_data_row}')
            
            # Sheet 2: Holdings (reference sheet)
            holdings_display.to_excel(
                writer,
                sheet_name='Holdings',
                index=False
            )
            ws_holdings = writer.sheets['Holdings']
            
            # Adjust column widths for holdings sheet
            for col_idx, col in enumerate(holdings_display.columns, 1):
                max_length = len(str(col))
                col_letter = get_column_letter(col_idx)
                for val in holdings_display[col]:
                    max_length = max(max_length, len(str(val)))
                ws_holdings.column_dimensions[col_letter].width = min(max_length + 2, EXCEL_MAX_COLUMN_WIDTH)
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        raise ValueError(f"Failed to generate Excel export: {str(e)}")
