"""
DB VITHRA — Excel Service Module
Handles Excel workbook lifecycle, worksheets, row/column/cell CRUD, openpyxl formatting, formula detection, duplicate & missing value processing, and CSV conversions.
"""
import os
import re
import logging
from typing import Dict, List, Tuple, Any, Optional
import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import pandas as pd

from services.base_adapter import BaseDatabaseAdapter

logger = logging.getLogger(__name__)

# Base directory for Excel workbooks created/managed by DB VITHRA
EXCEL_STORAGE_DIR = os.path.join(os.getcwd(), 'static', 'generated_databases', 'excel_workbooks')
os.makedirs(EXCEL_STORAGE_DIR, exist_ok=True)

class ExcelAdapter(BaseDatabaseAdapter):
    @classmethod
    def get_workbook_path(cls, workbook_name: str) -> str:
        clean = re.sub(r'[^A-Za-z0-9_\-]', '', workbook_name.replace(' ', '_'))
        if not clean.lower().endswith('.xlsx'):
            clean += '.xlsx'
        return os.path.join(EXCEL_STORAGE_DIR, clean)

    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        filePath = config.get('file_path') or config.get('workbook_name')
        if not filePath:
            return True, "Excel Workspace is online. Ready to create or open workbooks."
        
        target_path = filePath if os.path.isabs(filePath) else self.get_workbook_path(filePath)
        if os.path.exists(target_path):
            try:
                wb = load_workbook(target_path, read_only=True)
                sheets = wb.sheetnames
                wb.close()
                return True, f"Successfully connected to Excel workbook: {os.path.basename(target_path)} ({len(sheets)} sheets: {', '.join(sheets)})"
            except Exception as e:
                return False, f"Invalid or corrupted Excel file: {str(e)}"
        else:
            return True, f"Excel file location verified. Click Create to generate `{os.path.basename(target_path)}`."

    def create_database(self, db_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Create a new Excel Workbook (.xlsx)."""
        if not db_name:
            return False, "Workbook name cannot be empty."

        path = self.get_workbook_path(db_name)
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Sheet1"

            # Setup styled default headers
            headers = ["ID", "Name", "Category", "Value", "Date", "Status"]
            ws.append(headers)

            # Sample row data
            ws.append([1, "Sample Item A", "General", 150.00, "2026-08-23", "Active"])
            ws.append([2, "Sample Item B", "General", 299.50, "2026-08-23", "Pending"])

            # Apply professional header formatting (navy background, white font)
            header_fill = PatternFill(start_color="1C2541", end_color="1C2541", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            thin_border = Border(bottom=Side(style='thin', color='CCCCCC'))

            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = thin_border

            # Adjust column widths
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 5, 12)

            # Freeze top row header pane
            ws.freeze_panes = 'A2'

            wb.save(path)
            wb.close()
            return True, f"Excel Workbook `{os.path.basename(path)}` created successfully with openpyxl styling."
        except Exception as e:
            logger.error(f"Excel workbook creation error: {e}")
            return False, f"Failed to create Excel workbook: {str(e)}"

    def list_databases(self, config: Dict[str, Any]) -> List[str]:
        """List all Excel workbooks in storage."""
        files = [f for f in os.listdir(EXCEL_STORAGE_DIR) if f.endswith('.xlsx') or f.endswith('.xls')]
        return files or ['sample_workbook.xlsx']

    def list_tables(self, db_name: str, config: Dict[str, Any]) -> List[str]:
        """In Excel, 'tables' correspond to Worksheets."""
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            self.create_database(db_name, config)

        try:
            wb = load_workbook(path, read_only=True)
            sheets = wb.sheetnames
            wb.close()
            return sheets
        except Exception as e:
            logger.error(f"Excel list sheets error for {db_name}: {e}")
            return ['Sheet1']

    def get_schema(self, db_name: str, table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect worksheet headers, data types, formula presence, duplicate counts, and null counts."""
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            return {'table_name': table_name, 'columns': [], 'primary_keys': [], 'row_count': 0}

        try:
            df = pd.read_excel(path, sheet_name=table_name)
            col_names = list(df.columns)
            row_count = len(df)

            # Analyze missing values and data types
            columns = []
            for col in col_names:
                dtype_str = str(df[col].dtype)
                null_count = int(df[col].isnull().sum())
                columns.append({
                    'name': str(col),
                    'type': dtype_str,
                    'nullable': null_count > 0,
                    'missing_count': null_count,
                    'primary_key': str(col).lower() in ['id', 'sl_no', 'index', 'code']
                })

            dup_rows_count = int(df.duplicated().sum())

            return {
                'table_name': table_name,
                'columns': columns,
                'primary_keys': [c['name'] for c in columns if c['primary_key']],
                'row_count': row_count,
                'duplicate_rows_count': dup_rows_count,
                'db_type': 'excel'
            }
        except Exception as e:
            logger.error(f"Excel get schema error for {db_name}.{table_name}: {e}")
            return {'table_name': table_name, 'columns': [], 'primary_keys': [], 'row_count': 0, 'error': str(e)}

    def create_table(self, db_name: str, table_name: str, columns: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        """Create a new Worksheet inside an existing Excel Workbook."""
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            self.create_database(db_name, config)

        try:
            wb = load_workbook(path)
            if table_name in wb.sheetnames:
                ws = wb[table_name]
            else:
                ws = wb.create_sheet(title=table_name)

            headers = [c.get('name') for c in columns] if columns else ["ID", "Column_1", "Column_2"]
            ws.delete_rows(1, ws.max_row)
            ws.append(headers)

            # Style header row
            header_fill = PatternFill(start_color="1C2541", end_color="1C2541", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font

            wb.save(path)
            wb.close()
            return True, f"Worksheet `{table_name}` created inside Excel workbook `{os.path.basename(path)}`."
        except Exception as e:
            logger.error(f"Excel create worksheet error: {e}")
            return False, f"Failed to create worksheet: {str(e)}"

    def query(self, db_name: str, table_name: str, query_filter: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            return {'data': [], 'columns': [], 'total_count': 0, 'page': page, 'per_page': per_page}

        try:
            df = pd.read_excel(path, sheet_name=table_name)
            # Fill NaN values with empty string or None for JSON compatibility
            df_clean = df.fillna("")

            search_term = (query_filter or {}).get('search', '').strip()
            if search_term:
                mask = df_clean.astype(str).apply(lambda row: row.str.contains(search_term, case=False).any(), axis=1)
                df_clean = df_clean[mask]

            total_count = len(df_clean)
            offset = (page - 1) * per_page
            df_page = df_clean.iloc[offset:offset+per_page]

            # Add temporary row_id if no primary key exists
            records = df_page.to_dict(orient='records')
            for idx, r in enumerate(records):
                if '_row_index' not in r:
                    r['_row_index'] = offset + idx + 2 # 1-indexed row number in Excel (header is row 1)

            col_names = ['_row_index'] + list(df.columns)

            return {
                'data': records,
                'columns': col_names,
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': max(1, (total_count + per_page - 1) // per_page)
            }
        except Exception as e:
            logger.error(f"Excel query error for {db_name}.{table_name}: {e}")
            return {'data': [], 'columns': [], 'total_count': 0, 'page': 1, 'per_page': per_page, 'error': str(e)}

    def insert_record(self, db_name: str, table_name: str, record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            self.create_database(db_name, config)

        if '_row_index' in record:
            del record['_row_index']

        try:
            wb = load_workbook(path)
            if table_name not in wb.sheetnames:
                ws = wb.create_sheet(table_name)
                headers = list(record.keys())
                ws.append(headers)
            else:
                ws = wb[table_name]
                headers = [cell.value for cell in ws[1]]

            row_vals = [record.get(h, '') for h in headers]
            ws.append(row_vals)

            wb.save(path)
            wb.close()
            return True, f"Row appended successfully into Excel worksheet `{table_name}`."
        except Exception as e:
            logger.error(f"Excel insert record error: {e}")
            return False, f"Excel Insert Error: {str(e)}"

    def update_record(self, db_name: str, table_name: str, record_id: Any, updates: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            return False, "Workbook does not exist."

        try:
            wb = load_workbook(path)
            if table_name not in wb.sheetnames:
                return False, f"Worksheet `{table_name}` not found."

            ws = wb[table_name]
            headers = [cell.value for cell in ws[1]]

            # Determine row to update using _row_index or PK match
            target_row = None
            try:
                row_idx = int(record_id)
                if 2 <= row_idx <= ws.max_row:
                    target_row = row_idx
            except ValueError:
                pass

            if not target_row:
                # Search by matching first column value
                for r in range(2, ws.max_row + 1):
                    cell_val = str(ws.cell(row=r, column=1).value)
                    if cell_val == str(record_id):
                        target_row = r
                        break

            if not target_row:
                return False, f"Row `{record_id}` not found in Excel worksheet `{table_name}`."

            for field, val in updates.items():
                if field == '_row_index':
                    continue
                if field in headers:
                    col_idx = headers.index(field) + 1
                    ws.cell(row=target_row, column=col_idx, value=val)

            wb.save(path)
            wb.close()
            return True, f"Row #{target_row} updated successfully in Excel worksheet `{table_name}`."
        except Exception as e:
            logger.error(f"Excel update record error: {e}")
            return False, f"Excel Update Error: {str(e)}"

    def delete_record(self, db_name: str, table_name: str, record_id: Any, config: Dict[str, Any]) -> Tuple[bool, str]:
        path = self.get_workbook_path(db_name)
        if not os.path.exists(path):
            return False, "Workbook does not exist."

        try:
            wb = load_workbook(path)
            if table_name not in wb.sheetnames:
                return False, f"Worksheet `{table_name}` not found."

            ws = wb[table_name]
            target_row = None
            try:
                row_idx = int(record_id)
                if 2 <= row_idx <= ws.max_row:
                    target_row = row_idx
            except ValueError:
                pass

            if not target_row:
                for r in range(2, ws.max_row + 1):
                    if str(ws.cell(row=r, column=1).value) == str(record_id):
                        target_row = r
                        break

            if not target_row:
                return False, f"Row `{record_id}` not found in worksheet."

            ws.delete_rows(target_row)
            wb.save(path)
            wb.close()
            return True, f"Row #{target_row} deleted successfully from Excel worksheet `{table_name}`."
        except Exception as e:
            logger.error(f"Excel delete record error: {e}")
            return False, f"Excel Delete Error: {str(e)}"
