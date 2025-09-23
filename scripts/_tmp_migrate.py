import sys
try:
    from app.database import ensure_database_schema
    ensure_database_schema('head')
    print('migrated-to-head')
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
