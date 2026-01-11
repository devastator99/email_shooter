import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///email_shooter.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MailerSend Configuration
    MAILERSEND_API_KEY = os.environ.get('MAILERSEND_API_KEY')
    FROM_EMAIL = os.environ.get('FROM_EMAIL')
    FROM_NAME = os.environ.get('FROM_NAME', 'Email Shooter')
    
    # Email Configuration
    EMAIL_BATCH_SIZE = int(os.environ.get('EMAIL_BATCH_SIZE', 100))
    EMAIL_RATE_LIMIT = int(os.environ.get('EMAIL_RATE_LIMIT', 1))
    UNSUBSCRIBE_URL = os.environ.get('UNSUBSCRIBE_URL', 'http://localhost:5000/unsubscribe')
    
    # Scheduler Configuration
    SCHEDULER_ENABLED = os.environ.get('SCHEDULER_ENABLED', 'true').lower() == 'true'
    
    # Testing mode
    TESTING = os.environ.get('FLASK_ENV') == 'testing'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
