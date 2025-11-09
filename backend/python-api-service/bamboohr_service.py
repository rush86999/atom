import os
import logging
import json
from typing import Optional, Dict, Any
from pybamboohr import PyBambooHR
from loguru import logger

logger = logging.getLogger(__name__)

async def get_bamboohr_client(user_id: str, db_conn_pool) -> Optional[PyBambooHR]:
    # This is a placeholder. In a real application, you would fetch the user's BambooHR credentials
    # from a secure database. For now, we'll use environment variables.
    # You'll need to create a table to store these credentials, similar to the Dropbox and Google Drive implementations.
    subdomain = os.environ.get("BAMBOOHR_SUBDOMAIN")
    api_key = os.environ.get("BAMBOOHR_API_KEY")

    if not all([subdomain, api_key]):
        logger.error("BambooHR credentials are not configured in environment variables.")
        return None

    try:
        client = PyBambooHR(subdomain=subdomain, api_key=api_key)
        return client
    except Exception as e:
        logger.error(f"Failed to create BambooHR client: {e}", exc_info=True)
        return None

def create_bamboohr_service(user_id: str) -> Optional[PyBambooHR]:
    """Create BambooHR service instance"""
    try:
        client = get_bamboohr_client(user_id, None)
        return BambooHRService(user_id, client)
    except Exception as e:
        logger.error(f"Failed to create BambooHR service: {e}")
        return None

class BambooHRService:
    """Enhanced BambooHR service with comprehensive HR functionality"""
    
    def __init__(self, user_id: str, client: PyBambooHR):
        self.user_id = user_id
        self.client = client
        self._initialized = False
    
    async def initialize(self, db_pool):
        """Initialize service with database pool"""
        self.db_pool = db_pool
        self._initialized = True
        logger.info(f"BambooHR service initialized for user {self.user_id}")
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("BambooHR service not initialized. Call initialize() first.")
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get HR dashboard data"""
        try:
            await self._ensure_initialized()
            
            # Get company info
            company_info = await get_company_info(self.client)
            
            # Get employee count
            employees = await get_all_employees(self.client)
            
            # Get pending time off requests
            time_off_requests = await get_time_off_requests(self.client)
            
            # Get who's out
            whos_out = await get_whos_out(self.client)
            
            return {
                "company": company_info,
                "employee_count": len(employees),
                "pending_time_off": len(time_off_requests),
                "whos_out": len(whos_out),
                "recent_hires": employees[:5] if employees else []
            }
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {"error": str(e)}
    
    async def get_employee_directory(self, limit: int = 50) -> Dict[str, Any]:
        """Get employee directory"""
        try:
            await self._ensure_initialized()
            
            employees = await get_all_employees(self.client)
            return {
                "employees": employees[:limit],
                "total": len(employees)
            }
        except Exception as e:
            logger.error(f"Failed to get employee directory: {e}")
            return {"error": str(e)}
    
    async def search_employees(self, query: str) -> Dict[str, Any]:
        """Search employees by name or email"""
        try:
            await self._ensure_initialized()
            
            employees = await get_all_employees(self.client)
            query_lower = query.lower()
            
            filtered_employees = [
                emp for emp in employees
                if query_lower in emp.get('displayName', '').lower() or
                   query_lower in emp.get('workEmail', '').lower()
            ]
            
            return {
                "employees": filtered_employees,
                "query": query,
                "total": len(filtered_employees)
            }
        except Exception as e:
            logger.error(f"Failed to search employees: {e}")
            return {"error": str(e)}

async def create_employee(client: PyBambooHR, employee_data: Dict[str, Any]) -> Dict[str, Any]:
    employee = client.add_employee(employee_data)
    return employee

async def get_employee(client: PyBambooHR, employee_id: str) -> Dict[str, Any]:
    employee = client.get_employee(employee_id)
    return employee

async def get_all_employees(client: PyBambooHR) -> List[Dict[str, Any]]:
    """Get all employees"""
    try:
        employees = client.get_employees()
        return employees if employees else []
    except Exception as e:
        logger.error(f"Failed to get employees: {e}")
        return []

async def update_employee(client: PyBambooHR, employee_id: str, employee_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update employee information"""
    try:
        employee = client.update_employee(employee_id, employee_data)
        return employee
    except Exception as e:
        logger.error(f"Failed to update employee {employee_id}: {e}")
        return {"error": str(e)}

async def add_time_off(client: PyBambooHR, employee_id: str, time_off_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add time off request"""
    try:
        time_off = client.add_time_off(employee_id, time_off_data)
        return time_off
    except Exception as e:
        logger.error(f"Failed to add time off for {employee_id}: {e}")
        return {"error": str(e)}

async def get_company_info(client: PyBambooHR) -> Dict[str, Any]:
    """Get company information"""
    try:
        company = client.get_company()
        return company
    except Exception as e:
        logger.error(f"Failed to get company info: {e}")
        return {"error": str(e)}

async def get_time_off_requests(client: PyBambooHR, employee_id: str = None) -> List[Dict[str, Any]]:
    """Get time off requests"""
    try:
        time_offs = client.get_time_off_requests(employee_id)
        return time_offs if time_offs else []
    except Exception as e:
        logger.error(f"Failed to get time off requests: {e}")
        return []

async def approve_time_off(client: PyBambooHR, request_id: str) -> Dict[str, Any]:
    """Approve time off request"""
    try:
        result = client.approve_time_off(request_id)
        return result
    except Exception as e:
        logger.error(f"Failed to approve time off {request_id}: {e}")
        return {"error": str(e)}

async def get_whos_out(client: PyBambooHR) -> List[Dict[str, Any]]:
    """Get who's out information"""
    try:
        whos_out = client.get_whos_out()
        return whos_out if whos_out else []
    except Exception as e:
        logger.error(f"Failed to get who's out: {e}")
        return []

async def get_payroll(client: PyBambooHR, employee_id: str = None) -> Dict[str, Any]:
    """Get payroll information"""
    try:
        payroll = client.get_payroll(employee_id)
        return payroll if payroll else {}
    except Exception as e:
        logger.error(f"Failed to get payroll: {e}")
        return {"error": str(e)}

async def run_payroll(client: PyBambooHR, payroll_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run payroll"""
    try:
        result = client.run_payroll(payroll_data)
        return result
    except Exception as e:
        logger.error(f"Failed to run payroll: {e}")
        return {"error": str(e)}

async def get_reports(client: PyBambooHR, report_type: str = None) -> Dict[str, Any]:
    """Get HR reports"""
    try:
        reports = client.get_reports()
        if report_type:
            reports = [r for r in reports if r.get('type') == report_type]
        return {"reports": reports}
    except Exception as e:
        logger.error(f"Failed to get reports: {e}")
        return {"error": str(e)}

async def get_employment_details(client: PyBambooHR, employee_id: str) -> Dict[str, Any]:
    """Get employment details for an employee"""
    try:
        details = client.get_employment_details(employee_id)
        return details
    except Exception as e:
        logger.error(f"Failed to get employment details: {e}")
        return {"error": str(e)}

async def log_hipaaudit_trail(client: PyBambooHR, audit_data: Dict[str, Any]) -> Dict[str, Any]:
    """Log HIPAA audit trail"""
    try:
        result = client.log_hipaaudit_trail(audit_data)
        return result
    except Exception as e:
        logger.error(f"Failed to log HIPAA audit: {e}")
        return {"error": str(e)}
