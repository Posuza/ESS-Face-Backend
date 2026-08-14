ESS MO standalone MySQL migration
=================================

This folder contains the complete migration bundle. It creates all 23 model
tables and imports 373 selected employee and MO rows.

1. Copy this entire jsons folder to the Windows MySQL machine.

2. Open PowerShell in the copied folder and install the only dependency:

   py -m pip install -r requirements.txt

3. Open import_to_mysql.py and update the MYSQL_* values at the top if needed.
   The defaults are:

   host:     127.0.0.1
   port:     3306
   user:     root
   password: empty
   database: pbac_db

4. Run the migration:

   py .\import_to_mysql.py

The script creates the database and schema, refuses to import into non-empty
selected tables, verifies bundle checksums, and verifies all imported counts.

After migration, configure the backend service DB_* settings to use the same
database, then start the backend service.
