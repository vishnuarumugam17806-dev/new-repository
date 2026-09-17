"""
DB VITHRA — Data Visualization Service
Analyzes table/collection/worksheet data and builds chart payloads (Bar, Line, Pie, Doughnut, Area, Scatter, Histogram, Heatmap, KPI Cards).
"""
import logging
from typing import Dict, List, Any, Optional
import pandas as pd

from services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

class VisualizationService:
    @classmethod
    def analyze_and_build_charts(cls, db_type: str, db_name: str, table_name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fetch table records and automatically construct recommended chart payloads for UI visualization."""
        config = config or {}
        query_res = ConnectionManager.query(db_type, db_name, table_name, query_filter=None, page=1, per_page=500, config=config)
        data = query_res.get('data', [])

        if not data:
            return {
                'kpis': [{'title': 'Total Records', 'value': 0, 'icon': 'fa-database'}],
                'charts': [],
                'summary': 'No data available in selected target.'
            }

        df = pd.DataFrame(data)

        # Build KPI Cards
        total_records = len(df)
        kpis = [
            {'title': 'Total Records', 'value': total_records, 'icon': 'fa-list-check', 'color': 'cyan'},
            {'title': 'Total Fields', 'value': len(df.columns), 'icon': 'fa-table-columns', 'color': 'purple'}
        ]

        # Identify numeric and categorical columns
        numeric_cols = []
        categorical_cols = []

        for col in df.columns:
            if col.startswith('_') or col in ['id', 'ID', '_id']:
                continue
            # Try numeric conversion
            converted = pd.to_numeric(df[col], errors='coerce')
            if converted.notnull().sum() > len(df) * 0.5:
                numeric_cols.append(col)
                df[col] = converted
            else:
                categorical_cols.append(col)

        if numeric_cols:
            first_num = numeric_cols[0]
            kpis.append({'title': f'Avg {first_num.title()}', 'value': round(float(df[first_num].mean()), 2), 'icon': 'fa-calculator', 'color': 'amber'})
            kpis.append({'title': f'Max {first_num.title()}', 'value': round(float(df[first_num].max()), 2), 'icon': 'fa-arrow-trend-up', 'color': 'green'})

        charts = []

        # Chart 1: Categorical Distribution (Bar Chart or Pie Chart)
        if categorical_cols:
            cat_col = categorical_cols[0]
            counts = df[cat_col].value_counts().head(8)
            charts.append({
                'id': 'chart_categorical_distribution',
                'title': f'{cat_col.replace("_", " ").title()} Distribution',
                'type': 'bar',
                'labels': [str(k) for k in counts.index],
                'datasets': [{
                    'label': 'Count',
                    'data': [int(v) for v in counts.values],
                    'backgroundColor': ['#00f2fe', '#7928ca', '#ff007f', '#ffb703', '#2ec4b6', '#3a86ef', '#8338ec', '#ff006e']
                }]
            })

            # Chart 2: Pie / Doughnut Chart
            if len(categorical_cols) > 1:
                cat_col2 = categorical_cols[1]
                counts2 = df[cat_col2].value_counts().head(6)
                charts.append({
                    'id': 'chart_pie_distribution',
                    'title': f'{cat_col2.replace("_", " ").title()} Breakdown',
                    'type': 'doughnut',
                    'labels': [str(k) for k in counts2.index],
                    'datasets': [{
                        'label': 'Total',
                        'data': [int(v) for v in counts2.values],
                        'backgroundColor': ['#7928ca', '#00f2fe', '#ff007f', '#2ec4b6', '#ffb703']
                    }]
                })

        # Chart 3: Numeric Aggregation by Category
        if numeric_cols and categorical_cols:
            num_col = numeric_cols[0]
            cat_col = categorical_cols[0]
            grouped = df.groupby(cat_col)[num_col].sum().head(8)
            charts.append({
                'id': 'chart_numeric_aggregation',
                'title': f'Total {num_col.replace("_", " ").title()} by {cat_col.replace("_", " ").title()}',
                'type': 'line',
                'labels': [str(k) for k in grouped.index],
                'datasets': [{
                    'label': f'Total {num_col.title()}',
                    'data': [float(v) for v in grouped.values],
                    'borderColor': '#00f2fe',
                    'backgroundColor': 'rgba(0, 242, 254, 0.15)',
                    'fill': True
                }]
            })

        # Chart 4: Numeric Histogram / Distribution
        if numeric_cols:
            num_col = numeric_cols[-1]
            charts.append({
                'id': 'chart_numeric_trend',
                'title': f'{num_col.replace("_", " ").title()} Value Variance',
                'type': 'bar',
                'labels': [f"Rec #{i+1}" for i in range(min(15, len(df)))],
                'datasets': [{
                    'label': num_col.title(),
                    'data': [float(x) for x in df[num_col].head(15)],
                    'backgroundColor': '#ff007f'
                }]
            })

        return {
            'db_type': db_type,
            'db_name': db_name,
            'table_name': table_name,
            'kpis': kpis,
            'charts': charts
        }
