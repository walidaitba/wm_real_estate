from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Create index on function field for better performance
    cr.execute("""
        CREATE INDEX IF NOT EXISTS res_partner_function_index
        ON res_partner (function)
    """)
