def migrate(cr, version):
    if not version:
        return

    # Migrate existing CIN data to function field
    cr.execute("""
        UPDATE res_partner
        SET function = cin
        WHERE cin IS NOT NULL 
        AND cin != ''
        AND (function IS NULL OR function = '')
    """)

    # Drop the cin column from res_partner
    cr.execute("""
        ALTER TABLE res_partner
        DROP COLUMN IF EXISTS cin
    """)
