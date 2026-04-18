"""
VPS Panel — Application Entry Point
"""
import os
from dotenv import load_dotenv

# Load environment variables before anything else
load_dotenv()

from app import create_app

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    port = int(os.environ.get('PANEL_PORT', 6000))
    # Force disable secure cookies when running standalone, otherwise HTTP logins will loop
    app.config['SESSION_COOKIE_SECURE'] = False
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))
