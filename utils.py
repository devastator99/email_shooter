import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
import pandas as pd

def allowed_file(filename, allowed_extensions={'csv'}):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, upload_folder):
    """Save uploaded file and return file path"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to prevent filename conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return file_path
    return None

def validate_csv_structure(file_path):
    """Validate CSV file structure for subscriber import"""
    try:
        df = pd.read_csv(file_path)
        
        # Check for required columns
        required_columns = ['email']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                'valid': False,
                'error': f"Missing required columns: {', '.join(missing_columns)}"
            }
        
        # Check for empty emails
        empty_emails = df['email'].isnull().sum()
        if empty_emails > 0:
            return {
                'valid': False,
                'error': f"Found {empty_emails} rows with empty email addresses"
            }
        
        # Check for duplicate emails
        duplicate_emails = df['email'].duplicated().sum()
        if duplicate_emails > 0:
            return {
                'valid': False,
                'error': f"Found {duplicate_emails} duplicate email addresses"
            }
        
        return {
            'valid': True,
            'total_rows': len(df),
            'columns': list(df.columns)
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f"Error reading CSV file: {str(e)}"
        }

def generate_unsubscribe_token():
    """Generate unique unsubscribe token"""
    return str(uuid.uuid4())

def format_datetime(dt):
    """Format datetime for display"""
    if dt is None:
        return 'N/A'
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def calculate_campaign_progress(campaign):
    """Calculate campaign progress percentage"""
    if campaign.total_recipients == 0:
        return 0
    return (campaign.emails_sent / campaign.total_recipients) * 100

def get_status_color(status):
    """Get Bootstrap color class for status"""
    status_colors = {
        'draft': 'secondary',
        'scheduled': 'info',
        'sending': 'primary',
        'completed': 'success',
        'completed_with_errors': 'warning',
        'failed': 'danger',
        'pending': 'secondary',
        'sent': 'info',
        'delivered': 'success',
        'opened': 'primary',
        'clicked': 'success',
        'bounced': 'danger',
        'unsubscribed': 'warning'
    }
    return status_colors.get(status, 'secondary')

def clean_email_address(email):
    """Clean and validate email address"""
    if not email:
        return None
    
    email = str(email).strip().lower()
    
    # Basic email validation
    if '@' not in email or '.' not in email.split('@')[-1]:
        return None
    
    return email

def paginate_query(query, page, per_page=20):
    """Paginate SQLAlchemy query"""
    return query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

def get_file_size(file_path):
    """Get human readable file size"""
    if not os.path.exists(file_path):
        return '0 bytes'
    
    size = os.path.getsize(file_path)
    for unit in ['bytes', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def sanitize_html(html_content):
    """Basic HTML sanitization (in production, use proper library like bleach)"""
    # This is a basic implementation - in production, use a proper HTML sanitizer
    dangerous_tags = ['<script>', '</script>', '<iframe>', '</iframe>', '<object>', '</object>']
    dangerous_attrs = ['onclick', 'onload', 'onerror', 'javascript:']
    
    sanitized = html_content
    
    # Remove dangerous tags
    for tag in dangerous_tags:
        sanitized = sanitized.replace(tag, '')
    
    # Remove dangerous attributes
    for attr in dangerous_attrs:
        sanitized = sanitized.replace(attr, '')
    
    return sanitized

def validate_email_template(template_content):
    """Validate Jinja2 email template"""
    try:
        from jinja2 import Template, TemplateSyntaxError
        Template(template_content)
        return {'valid': True}
    except TemplateSyntaxError as e:
        return {
            'valid': False,
            'error': f"Template syntax error: {str(e)}"
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f"Template validation error: {str(e)}"
        }
