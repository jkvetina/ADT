query_version_apex = r"""
SELECT
    a.version_no AS version
FROM apex_release a;
"""

query_version_db = """
SELECT
    p.version_full || ' | ' ||
    REGEXP_REPLACE(SYS_CONTEXT('USERENV', 'DB_NAME'), '^[^_]+_', '') AS version
FROM product_component_version p
"""

# get database version for older systems
query_version_db_old = """
SELECT p.version
FROM product_component_version p
WHERE p.product LIKE 'Oracle Database%'
"""

