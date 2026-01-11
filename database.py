from flask import current_app
from models import db, Subscriber, Campaign, EmailLog, EmailTemplate, WebhookEvent
from datetime import datetime
import pandas as pd
import os

def init_db(app):
    """Initialize database with app context"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create default template if none exists
        if not EmailTemplate.query.first():
            default_template = EmailTemplate(
                name='Default Template',
                subject='Hello {{ name }}!',
                html_content='''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ subject }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        .header { background-color: #f8f9fa; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; }
        .unsubscribe { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ subject }}</h1>
        </div>
        <div class="content">
            <p>Dear {{ name }},</p>
            <p>{{ custom_message }}</p>
            <p>Best regards,<br>{{ from_name }}</p>
        </div>
        <div class="footer">
            <p>This email was sent to {{ email }}.</p>
            <p class="unsubscribe">
                <a href="{{ unsubscribe_url }}">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>
                ''',
                text_content='''
{{ subject }}

Dear {{ name }},

{{ custom_message }}

Best regards,
{{ from_name }}

---
This email was sent to {{ email }}.
Unsubscribe: {{ unsubscribe_url }}
                ''',
                is_default=True
            )
            db.session.add(default_template)
            db.session.commit()

def import_subscribers_from_csv(file_path):
    """Import subscribers from CSV file"""
    try:
        df = pd.read_csv(file_path)
        
        # Validate required columns
        required_columns = ['email']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        imported_count = 0
        updated_count = 0
        
        for index, row in df.iterrows():
            email = str(row['email']).strip().lower()
            name = row.get('name', '')
            custom_message = row.get('custom_message', '')
            
            if not email or email == 'nan':
                continue
            
            # Check if subscriber exists
            subscriber = Subscriber.query.filter_by(email=email).first()
            
            if subscriber:
                # Update existing subscriber
                if name and name != 'nan':
                    subscriber.name = name
                if custom_message and custom_message != 'nan':
                    subscriber.custom_message = custom_message
                subscriber.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Create new subscriber
                subscriber = Subscriber(
                    email=email,
                    name=name if name and name != 'nan' else None,
                    custom_message=custom_message if custom_message and custom_message != 'nan' else None
                )
                db.session.add(subscriber)
                imported_count += 1
        
        db.session.commit()
        return {
            'success': True,
            'imported': imported_count,
            'updated': updated_count,
            'total': len(df)
        }
    
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'error': str(e)
        }

def get_campaign_stats(campaign_id):
    """Get comprehensive campaign statistics"""
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return None
    
    stats = {
        'campaign': campaign,
        'total_recipients': campaign.total_recipients,
        'emails_sent': campaign.emails_sent,
        'emails_failed': campaign.emails_failed,
        'delivery_rate': 0,
        'open_rate': 0,
        'click_rate': 0,
        'bounce_rate': 0,
        'unsubscribe_rate': 0
    }
    
    if campaign.emails_sent > 0:
        delivered_count = EmailLog.query.filter_by(
            campaign_id=campaign_id, 
            status='delivered'
        ).count()
        
        opened_count = EmailLog.query.filter_by(
            campaign_id=campaign_id, 
            status='opened'
        ).count()
        
        clicked_count = EmailLog.query.filter_by(
            campaign_id=campaign_id, 
            status='clicked'
        ).count()
        
        bounced_count = EmailLog.query.filter_by(
            campaign_id=campaign_id, 
            status='bounced'
        ).count()
        
        unsubscribed_count = EmailLog.query.filter_by(
            campaign_id=campaign_id, 
            status='unsubscribed'
        ).count()
        
        stats['delivery_rate'] = (delivered_count / campaign.emails_sent) * 100
        stats['open_rate'] = (opened_count / campaign.emails_sent) * 100
        stats['click_rate'] = (clicked_count / campaign.emails_sent) * 100
        stats['bounce_rate'] = (bounced_count / campaign.emails_sent) * 100
        stats['unsubscribe_rate'] = (unsubscribed_count / campaign.emails_sent) * 100
    
    return stats
