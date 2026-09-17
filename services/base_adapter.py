"""
SMART DB — Base Database Adapter Interface
Provides standard abstract interface for SQL Server, MySQL, Oracle, MongoDB, and Excel adapters.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional

class BaseDatabaseAdapter(ABC):
    @abstractmethod
    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test database connection credentials."""
        pass

    @abstractmethod
    def create_database(self, db_name: str, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Create a new database / schema / workbook."""
        pass

    @abstractmethod
    def list_databases(self, config: Dict[str, Any]) -> List[str]:
        """List accessible databases / schema / workbooks."""
        pass

    @abstractmethod
    def list_tables(self, db_name: str, config: Dict[str, Any]) -> List[str]:
        """List tables / collections / worksheets inside a database."""
        pass

    @abstractmethod
    def get_schema(self, db_name: str, table_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Inspect structure / fields / metadata of a table / collection / worksheet."""
        pass

    @abstractmethod
    def create_table(self, db_name: str, table_name: str, columns: List[Dict[str, Any]], config: Dict[str, Any]) -> Tuple[bool, str]:
        """Create a table / collection / worksheet with defined structure."""
        pass

    @abstractmethod
    def query(self, db_name: str, table_name: str, query_filter: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 50, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Query and paginate data from a table / collection / worksheet."""
        pass

    @abstractmethod
    def insert_record(self, db_name: str, table_name: str, record: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        """Insert a single row / document into a table / collection / worksheet."""
        pass

    @abstractmethod
    def update_record(self, db_name: str, table_name: str, record_id: Any, updates: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
        """Update a row / document in a table / collection / worksheet."""
        pass

    @abstractmethod
    def delete_record(self, db_name: str, table_name: str, record_id: Any, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Delete a row / document from a table / collection / worksheet."""
        pass
