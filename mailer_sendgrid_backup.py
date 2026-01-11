import os
import time
from datetime import datetime
from flask import current_app
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from jinja2 import Template
from models import db, Subscriber, Campaign, EmailLog
from config import Config

class EmailSender:
    def __init__(self):
        self.sg = SendGridAPIClient(api_key=Config.SENDGRID_API_KEY)
        self.from_email = Config.FROM_EMAIL
        self.from_name = Config.FROM_NAME
        self.batch_size = Config.EMAIL_BATCH_SIZE
        self.rate_limit = Config.EMAIL_RATE_LIMIT
    
    def render_template(self, template_content, context):
        """Render email template with context variables"""
        try:
            template = Template(template_content)
            return template.render(**context)
        except Exception as e:
            raise Exception(f"Template rendering error: {str(e)}")
    
    def create_email_message(self, subscriber, campaign):
        """Create personalized email message for subscriber"""
        # Build context for template rendering
        context = {
            'name': subscriber.name or subscriber.email.split('@')[0],
            'email': subscriber.email,
            'subject': campaign.subject,
            'custom_message': subscriber.custom_message or '',
            'from_name': self.from_name,
            'unsubscribe_url': f"{Config.UNSUBSCRIBE_URL}?token={subscriber.unsubscribe_token}",
            'campaign_name': campaign.name
        }
        
        # Render HTML and text templates
        try:
            html_content = self.render_template(campaign.template_html, context)
            text_content = self.render_template(campaign.template_text, context) if campaign.template_text else None
        except Exception as e:
            raise Exception(f"Template rendering failed for {subscriber.email}: {str(e)}")
        
        # Create SendGrid message
        message = Mail(
            from_email=(self.from_email, self.from_name),
            to_emails=subscriber.email,
            subject=campaign.subject,
            html_content=html_content,
            plain_text_content=text_content
        )
        
        # Add custom tracking
        message.custom_args = {
            'campaign_id': str(campaign.id),
            'subscriber_id': str(subscriber.id)
        }
        
        return message
    
    def send_single_email(self, subscriber, campaign):
        """Send single email to subscriber"""
        try:
            # Create email message
            message = self.create_email_message(subscriber, campaign)
            
            # Send email
            response = self.sg.send(message)
            
            # Log the send attempt
            email_log = EmailLog(
                subscriber_id=subscriber.id,
                campaign_id=campaign.id,
                sendgrid_message_id=response.headers.get('X-Message-Id'),
                status='sent',
                sent_at=datetime.utcnow()
            )
            db.session.add(email_log)
            
            # Update campaign stats
            campaign.emails_sent += 1
            
            return {
                'success': True,
                'message_id': response.headers.get('X-Message-Id'),
                'status_code': response.status_code
            }
            
        except Exception as e:
            # Log the failure
            email_log = EmailLog(
                subscriber_id=subscriber.id,
                campaign_id=campaign.id,
                status='failed',
                error_message=str(e),
                sent_at=datetime.utcnow()
            )
            db.session.add(email_log)
            
            # Update campaign stats
            campaign.emails_failed += 1
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_campaign(self, campaign_id, test_mode=False):
        """Send campaign to all active subscribers"""
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            raise Exception("Campaign not found")
        
        if campaign.status not in ['draft', 'scheduled']:
            raise Exception(f"Campaign cannot be sent. Current status: {campaign.status}")
        
        # Update campaign status
        campaign.status = 'sending'
        campaign.sent_at = datetime.utcnow()
        db.session.commit()
        
        try:
            # Get all active subscribers
            subscribers = Subscriber.query.filter_by(is_active=True).all()
            campaign.total_recipients = len(subscribers)
            db.session.commit()
            
            if test_mode:
                # In test mode, only send to first 3 subscribers
                subscribers = subscribers[:3]
            
            sent_count = 0
            failed_count = 0
            
            # Send emails in batches with rate limiting
            for i in range(0, len(subscribers), self.batch_size):
                batch = subscribers[i:i + self.batch_size]
                
                for subscriber in batch:
                    result = self.send_single_email(subscriber, campaign)
                    
                    if result['success']:
                        sent_count += 1
                        print(f"✓ Sent to {subscriber.email}")
                    else:
                        failed_count += 1
                        print(f"✗ Failed to send to {subscriber.email}: {result['error']}")
                    
                    # Rate limiting
                    time.sleep(1 / self.rate_limit)
                
                # Commit batch
                db.session.commit()
                
                # Small delay between batches
                if i + self.batch_size < len(subscribers):
                    time.sleep(2)
            
            # Update final campaign status
            if failed_count == 0:
                campaign.status = 'completed'
            else:
                campaign.status = 'completed_with_errors'
            
            db.session.commit()
            
            return {
                'success': True,
                'sent': sent_count,
                'failed': failed_count,
                'total': len(subscribers)
            }
            
        except Exception as e:
            # Update campaign status to failed
            campaign.status = 'failed'
            db.session.commit()
            raise Exception(f"Campaign sending failed: {str(e)}")
    
    def send_test_email(self, campaign_id, test_email):
        """Send test email to specified address"""
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            raise Exception("Campaign not found")
        
        # Create a temporary subscriber for testing
        test_subscriber = Subscriber(
            email=test_email,
            name="Test User",
            custom_message="This is a test message."
        )
        
        try:
            result = self.send_single_email(test_subscriber, campaign)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

def send_campaign_email(campaign_id, test_mode=False):
    """Convenience function to send campaign"""
    sender = EmailSender()
    return sender.send_campaign(campaign_id, test_mode)

def send_test_email(campaign_id, test_email):
    """Convenience function to send test email"""
    sender = EmailSender()
    return sender.send_test_email(campaign_id, test_email)
