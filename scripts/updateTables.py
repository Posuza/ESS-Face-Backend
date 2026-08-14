"""
Script to drop a specific table and recreate all tables from models.
Usage: python updateTables.py <table_name_to_drop>
"""

import sys
import os
from sqlalchemy import inspect

# Ensure project root is on sys.path so `app` package imports work when
# running this script from the `scripts/` directory.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
	sys.path.insert(0, project_root)

from app.core.orm import engine, Base
import importlib
import pkgutil

# Dynamically import every module in app.models so new model files are
# automatically picked up without editing this script.
models_pkg = "app.models"
models_path = os.path.join(project_root, "app", "models")
for finder, name, ispkg in pkgutil.iter_modules([models_path]):
	if name == "__init__":
		continue
	importlib.import_module(f"{models_pkg}.{name}")

def drop_tables(names: list[str]):
	inspector = inspect(engine)
	existing_db_tables = set(inspector.get_table_names())

	# Determine which metadata-known tables we should attempt to drop
	if len(names) == 1 and names[0].lower() == "all":
		candidates = [t for t in Base.metadata.tables.keys() if t in existing_db_tables]
	else:
		candidates = [t for t in names if t in Base.metadata.tables and t in existing_db_tables]

	if not candidates:
		print("No matching tables found in the database to drop.")
		return

	dialect = engine.dialect.name.lower()
	from sqlalchemy import text

	print(f"Dropping tables: {candidates}")

	# Build dependency graph from metadata: edge child -> parent (child depends on parent)
	# We'll perform a topological sort so children are dropped before parents.
	tables_in_db = {t for t in Base.metadata.tables.keys() if t in existing_db_tables}

	# Build adjacency and indegree for Kahn's algorithm
	adj: dict[str, set[str]] = {t: set() for t in tables_in_db}
	indeg: dict[str, int] = {t: 0 for t in tables_in_db}

	for tbl_name in list(tables_in_db):
		tbl = Base.metadata.tables.get(tbl_name)
		if tbl is None:
			continue
		for col in tbl.columns:
			for fk in col.foreign_keys:
				try:
					ref_table = fk.column.table.name
				except Exception:
					ref_table = None
				if ref_table and ref_table in tables_in_db:
					# edge: tbl_name -> ref_table
					if ref_table not in adj[tbl_name]:
						adj[tbl_name].add(ref_table)
						indeg[ref_table] = indeg.get(ref_table, 0) + 1

	# Kahn's algorithm
	from collections import deque

	q = deque([n for n, d in indeg.items() if d == 0])
	topo: list[str] = []
	while q:
		n = q.popleft()
		topo.append(n)
		for m in list(adj.get(n, [])):
			indeg[m] -= 1
			if indeg[m] == 0:
				q.append(m)

	if len(topo) != len(tables_in_db):
		print("Cycle detected in table foreign-key graph; falling back to FK-toggle drop.")
		# fallback: original behavior
		try:
			with engine.begin() as conn:
				if dialect in ("mysql", "mariadb", "mysqlconnector", "pymysql"):
					conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
				elif dialect == "sqlite":
					conn.execute(text("PRAGMA foreign_keys=OFF;"))

				for name in candidates:
					try:
						conn.execute(text(f"DROP TABLE IF EXISTS `{name}`;"))
						print(f"Dropped {name}")
					except Exception as e:
						print(f"Failed to drop {name}: {e}")

				if dialect in ("mysql", "mariadb", "mysqlconnector", "pymysql"):
					conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
				elif dialect == "sqlite":
					conn.execute(text("PRAGMA foreign_keys=ON;"))
		except Exception as e:
			print(f"Error while dropping tables (fallback): {e}")
		return

	# topo is an order where children appear before parents.
	drop_order = [t for t in topo if t in candidates]

	# Perform drops in topological order; if any drop fails due to external refs, fall back.
	try:
		with engine.begin() as conn:
			for name in drop_order:
				try:
					conn.execute(text(f"DROP TABLE IF EXISTS `{name}`;"))
					print(f"Dropped {name}")
				except Exception as e:
					print(f"Failed to drop {name}: {e}")
					raise
	except Exception as e:
		print(f"Topological drop failed: {e}\nFalling back to FK-toggle drop.")
		try:
			with engine.begin() as conn:
				if dialect in ("mysql", "mariadb", "mysqlconnector", "pymysql"):
					conn.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
				elif dialect == "sqlite":
					conn.execute(text("PRAGMA foreign_keys=OFF;"))

				for name in candidates:
					try:
						conn.execute(text(f"DROP TABLE IF EXISTS `{name}`;"))
						print(f"Dropped {name}")
					except Exception as e2:
						print(f"Failed to drop {name} in fallback: {e2}")

				if dialect in ("mysql", "mariadb", "mysqlconnector", "pymysql"):
					conn.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
				elif dialect == "sqlite":
					conn.execute(text("PRAGMA foreign_keys=ON;"))
		except Exception as e3:
			print(f"Error while dropping tables (final fallback): {e3}")


def create_all_tables():
	from sqlalchemy import Table, Column, Integer

	def ensure_fk_targets():
		# Find referenced tables from ForeignKey strings like 'roles.role_id'
		missing = {}
		# Iterate raw metadata tables to avoid triggering SQLAlchemy's sorted_tables
		# which will attempt to resolve foreign-key referred_table and raise errors
		for tbl in list(Base.metadata.tables.values()):
			for col in tbl.columns:
				# iterate foreign_keys without accessing properties that resolve targets
				for fk in col.foreign_keys:
					target = getattr(fk, "target_fullname", None)  # e.g. 'roles.role_id'
					if not target:
						continue
					parts = target.split(".")
					if len(parts) != 2:
						continue
					tgt_table, tgt_col = parts
					if tgt_table not in Base.metadata.tables:
						missing.setdefault(tgt_table, tgt_col)

		for tbl_name, col_name in missing.items():
			if tbl_name in Base.metadata.tables:
				continue
			print(f"Adding placeholder metadata for missing referenced table: {tbl_name}({col_name})")
			Table(tbl_name, Base.metadata, Column(col_name, Integer, primary_key=True))

	print("Creating all tables from models...")
	ensure_fk_targets()
	from sqlalchemy.exc import ProgrammingError
	try:
		Base.metadata.create_all(bind=engine)
		print("All tables created.")
	except ProgrammingError as e:
		msg = str(e)
		# MySQL error 1050 = table already exists. If that happens, warn and continue.
		if "1060" in msg or "1050" in msg or "Table '" in msg and "already exists" in msg:
			print(f"Warning: create_all encountered a table-exists error: {e}")
			print("Continuing despite table-exists error.")
		else:
			raise


def create_tables(names: list[str]):
	"""Create only the metadata-known tables listed in `names`.

	This builds lightweight placeholder Table objects for any referenced
	foreign-key targets that are missing from the metadata so SQLAlchemy
	won't error when creating the selected tables.
	"""
	from sqlalchemy import Table, Column, Integer

	def ensure_fk_targets_for(selected: list[str]):
		missing = {}
		for tbl_name in selected:
			tbl = Base.metadata.tables.get(tbl_name)
			if tbl is None:
				continue
			for col in tbl.columns:
				for fk in col.foreign_keys:
					target = getattr(fk, "target_fullname", None)
					if not target:
						continue
					parts = target.split(".")
					if len(parts) != 2:
						continue
					tgt_table, tgt_col = parts
					if tgt_table not in Base.metadata.tables:
						missing.setdefault(tgt_table, tgt_col)

		for tbl_name, col_name in missing.items():
			if tbl_name in Base.metadata.tables:
				continue
			print(f"Adding placeholder metadata for missing referenced table: {tbl_name}({col_name})")
			Table(tbl_name, Base.metadata, Column(col_name, Integer, primary_key=True))

	print(f"Creating requested tables: {names}...")
	ensure_fk_targets_for(names)
	from sqlalchemy.exc import ProgrammingError

	tables = [Base.metadata.tables.get(n) for n in names if n in Base.metadata.tables]
	if not tables:
		print("No matching metadata-known tables to create.")
		return

	try:
		Base.metadata.create_all(bind=engine, tables=tables)
		print("Requested tables created.")
	except ProgrammingError as e:
		msg = str(e)
		if "1060" in msg or "1050" in msg or ("Table '" in msg and "already exists" in msg):
			print(f"Warning: create encountered a table-exists error: {e}")
			print("Continuing despite table-exists error.")
		else:
			raise


def parse_args(argv: list[str]) -> list[str]:
	# Accept multiple table names: python updateTables.py table1 table2
	# Or a single 'all' argument to drop everything known by metadata
	return argv[1:]


if __name__ == "__main__":
	args = parse_args(sys.argv)
	if not args:
		print("Usage: python updateTables.py <table_name_to_drop|all> [additional_table_names...]")
		sys.exit(1)

	drop_tables(args)
if len(args) == 1 and args[0].lower() == "all":
	create_all_tables()
else:
	create_tables(args)
