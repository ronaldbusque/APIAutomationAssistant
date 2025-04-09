"""
Admin API - Endpoints for administrative functions.

This module provides API endpoints for administrative functions
such as viewing audit logs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any
import logging
from pathlib import Path
from .auth import verify_admin_token  # Import the admin verification dependency

# Create logger
logger = logging.getLogger(__name__)

# Get audit logger and determine its file path
audit_logger = logging.getLogger("audit")
audit_log_file_path = None
for handler in audit_logger.handlers:
    if isinstance(handler, logging.FileHandler):
        audit_log_file_path = Path(handler.baseFilename)
        break

if not audit_log_file_path:
    # Fallback or raise configuration error
    audit_log_file_path = Path.cwd() / "logs/audit.log"
    logging.error("Could not determine audit log file path from handler. Falling back.")

# Create router with admin authentication
router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_token)]  # Apply admin auth to all routes in this router
)

@router.get("/audit-log", response_model=Dict[str, Any])
async def get_audit_log(
    limit: int = Query(100, ge=1, le=1000, description="Number of log entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
) -> Dict[str, Any]:
    """
    Retrieves entries from the audit log file with pagination.
    Requires admin authentication.
    """
    if not audit_log_file_path or not audit_log_file_path.exists():
        raise HTTPException(status_code=404, detail="Audit log file not found or not configured.")

    try:
        with open(audit_log_file_path, 'r', encoding='utf-8') as f:
            # Read lines efficiently, especially for large files
            # This reads all lines, consider more efficient ways for huge files
            lines = f.readlines()

        total_lines = len(lines)
        # Apply pagination using slicing (note: reads whole file first)
        paginated_lines = lines[offset : offset + limit]
        # Strip newline characters
        logs = [line.strip() for line in paginated_lines]

        return {
            "logs": logs,
            "total": total_lines,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logging.error(f"Error reading audit log file: {e}")
        raise HTTPException(status_code=500, detail=f"Could not read audit log file: {e}") 