#!/usr/bin/env python3
"""
Recreate the audit_logs table with correct schema.
This script drops the existing audit_logs table and recreates it.

Usage:
    python scripts/recreate_audit_log_table.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from app.core.database import engine
from app.models.audit_logs import AuditLog


def recreate_audit_log_table():
    """Drop and recreate the audit_logs table."""
    
    print("🔧 Recreating audit_logs table...")
    
    with engine.begin() as conn:
        # Drop the table if it exists
        print("   ⚠️  Dropping existing audit_logs table...")
        conn.execute(text("DROP TABLE IF EXISTS audit_logs"))
        print("   ✅ Table dropped")
        
        # Create the table with correct schema
        print("   🔨 Creating new audit_logs table...")
        conn.execute(text("""
            CREATE TABLE audit_logs (
                log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                employee_code VARCHAR(6) NULL,
                user_name VARCHAR(150) NOT NULL,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(512) NOT NULL,
                action TEXT NOT NULL,
                INDEX idx_employee_code (employee_code),
                INDEX idx_timestamp (timestamp),
                CONSTRAINT fk_audit_employee 
                    FOREIGN KEY (employee_code) 
                    REFERENCES employees(employee_code)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        print("   ✅ Table created successfully")
    
    print("✅ Audit log table recreated successfully!")
    print()
    print("📋 Table Schema:")
    print("   - log_id: BIGINT AUTO_INCREMENT PRIMARY KEY")
    print("   - employee_code: VARCHAR(6) NULL (FK to employees)")
    print("   - user_name: VARCHAR(150) NOT NULL")
    print("   - timestamp: DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    print("   - ip_address: VARCHAR(255) NOT NULL")
    print("   - action: TEXT NOT NULL")
    print()
    print("📝 Audit Log Format:")
    print("   Regular action: [ACT_KEY]ACTION_NAME | message")
    print("   Action with error: [ACT_KEY]ACTION_NAME | message | ERR_KEY | ERROR_TYPE | ERROR_MESSAGE")
    print()


if __name__ == "__main__":
    try:
        recreate_audit_log_table()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
