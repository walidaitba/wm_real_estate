{
    'name': 'WebMania',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'gestionnaire immobilier',
    'description': """
        This module allows you to manage:
        * Projects (Categories)
        * Buildings (Sub-categories)
        * Apartments (Products)
    """,
    'author': 'webmania',
    'website': 'https://www.webmania.ma/',
    'depends': [
        'base',
        'mail',
        'sale_management',  # Full sales management features
        'product',
        'stock',           # Inventory management
        'sale_stock',      # Sales and inventory integration
        'account',         # Accounting/Invoicing module
        'crm',             # CRM module for lead/opportunity management
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/server_actions.xml',
        'views/assets.xml',
        'views/project_views.xml',
        'views/building_views.xml',
        'views/apartment_views.xml',
        'views/product_views.xml',
        'views/sale_views.xml',
        'views/sale_actions.xml',
        'views/menu_views.xml',
        'views/stock_menu_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_actions.xml',
    ],
    'qweb': [],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
    'post_init_hook': 'post_init_hook',
}
