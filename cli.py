#!/usr/bin/env python3
"""
Email Shooter CLI Interface
Command-line interface for managing email campaigns and subscribers.
"""

import click
import os
import sys
from datetime import datetime
from flask import Flask

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Subscriber, Campaign, EmailLog, EmailTemplate
from mailer import send_campaign_email, send_test_email
from database import import_subscribers_from_csv
from config import config

def get_app():
    """Get Flask app instance"""
    return create_app(os.getenv('FLASK_ENV', 'development'))

@click.group()
def cli():
    """Email Shooter CLI - Manage email campaigns and subscribers"""
    pass

@cli.command()
@click.option('--campaign-id', '-c', type=int, help='Campaign ID to send')
@click.option('--test', is_flag=True, help='Send test emails only (3 recipients)')
@click.option('--dry-run', is_flag=True, help='Preview campaign without sending')
def send(campaign_id, test, dry_run):
    """Send an email campaign"""
    app = get_app()
    
    with app.app_context():
        if campaign_id:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                click.echo(f"Campaign with ID {campaign_id} not found", err=True)
                return
            
            if dry_run:
                click.echo(f"Dry run for campaign: {campaign.name}")
                click.echo(f"Subject: {campaign.subject}")
                click.echo(f"Total recipients: {Subscriber.query.filter_by(is_active=True).count()}")
                click.echo(f"Template preview: {campaign.template_html[:100]}...")
                return
            
            click.echo(f"Sending campaign: {campaign.name}")
            try:
                result = send_campaign_email(campaign_id, test_mode=test)
                click.echo(f"✓ Campaign sent successfully!")
                click.echo(f"  Sent: {result['sent']}")
                click.echo(f"  Failed: {result['failed']}")
                click.echo(f"  Total: {result['total']}")
            except Exception as e:
                click.echo(f"✗ Error sending campaign: {str(e)}", err=True)
        else:
            # List available campaigns
            campaigns = Campaign.query.filter(Campaign.status.in_(['draft', 'scheduled'])).all()
            if not campaigns:
                click.echo("No campaigns available to send")
                return
            
            click.echo("Available campaigns:")
            for campaign in campaigns:
                click.echo(f"  {campaign.id}: {campaign.name} ({campaign.status})")

@cli.command()
@click.option('--file', '-f', type=click.Path(exists=True), help='CSV file to import')
@click.option('--list', is_flag=True, help='List all subscribers')
@click.option('--count', is_flag=True, help='Count total subscribers')
def subscribers(file, list, count):
    """Manage subscribers"""
    app = get_app()
    
    with app.app_context():
        if file:
            click.echo(f"Importing subscribers from {file}...")
            result = import_subscribers_from_csv(file)
            
            if result['success']:
                click.echo(f"✓ Import successful!")
                click.echo(f"  New subscribers: {result['imported']}")
                click.echo(f"  Updated: {result['updated']}")
                click.echo(f"  Total processed: {result['total']}")
            else:
                click.echo(f"✗ Import failed: {result['error']}", err=True)
        
        elif list:
            subscribers = Subscriber.query.filter_by(is_active=True).all()
            if not subscribers:
                click.echo("No subscribers found")
                return
            
            click.echo(f"Total subscribers: {len(subscribers)}")
            click.echo("ID\tEmail\t\t\tName")
            click.echo("-" * 50)
            for sub in subscribers:
                name = sub.name or 'N/A'
                click.echo(f"{sub.id}\t{sub.email[:20]:20}\t{name[:20]}")
        
        elif count:
            total = Subscriber.query.filter_by(is_active=True).count()
            click.echo(f"Total active subscribers: {total}")
        
        else:
            click.echo("Use --file to import, --list to list, or --count to count subscribers")

@cli.command()
@click.option('--list', is_flag=True, help='List all campaigns')
@click.option('--stats', is_flag=True, help='Show campaign statistics')
@click.option('--id', type=int, help='Show details for specific campaign')
def campaigns(list, stats, id):
    """Manage campaigns"""
    app = get_app()
    
    with app.app_context():
        if id:
            campaign = Campaign.query.get(id)
            if not campaign:
                click.echo(f"Campaign with ID {id} not found", err=True)
                return
            
            click.echo(f"Campaign Details:")
            click.echo(f"  ID: {campaign.id}")
            click.echo(f"  Name: {campaign.name}")
            click.echo(f"  Subject: {campaign.subject}")
            click.echo(f"  Status: {campaign.status}")
            click.echo(f"  Created: {campaign.created_at}")
            click.echo(f"  Scheduled: {campaign.scheduled_at or 'Not scheduled'}")
            click.echo(f"  Sent: {campaign.emails_sent}")
            click.echo(f"  Failed: {campaign.emails_failed}")
            click.echo(f"  Total Recipients: {campaign.total_recipients}")
            
            # Show recent logs
            logs = EmailLog.query.filter_by(campaign_id=id).limit(10).all()
            if logs:
                click.echo(f"\nRecent Email Logs:")
                click.echo("ID\tStatus\t\tEmail")
                click.echo("-" * 50)
                for log in logs:
                    email = log.subscriber.email[:20] if log.subscriber else 'N/A'
                    click.echo(f"{log.id}\t{log.status[:12]:12}\t{email}")
        
        elif list:
            campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
            if not campaigns:
                click.echo("No campaigns found")
                return
            
            click.echo(f"Total campaigns: {len(campaigns)}")
            click.echo("ID\tName\t\t\tStatus\t\tSent")
            click.echo("-" * 70)
            for campaign in campaigns:
                name = campaign.name[:20] if campaign.name else 'N/A'
                click.echo(f"{campaign.id}\t{name[:20]:20}\t{campaign.status[:12]:12}\t{campaign.emails_sent}")
        
        elif stats:
            campaigns = Campaign.query.all()
            if not campaigns:
                click.echo("No campaigns found")
                return
            
            total_sent = sum(c.emails_sent for c in campaigns)
            total_failed = sum(c.emails_failed for c in campaigns)
            total_recipients = sum(c.total_recipients for c in campaigns)
            
            click.echo("Campaign Statistics:")
            click.echo(f"  Total campaigns: {len(campaigns)}")
            click.echo(f"  Total emails sent: {total_sent}")
            click.echo(f"  Total failed: {total_failed}")
            click.echo(f"  Total recipients: {total_recipients}")
            
            if total_sent > 0:
                success_rate = (total_sent / (total_sent + total_failed)) * 100
                click.echo(f"  Success rate: {success_rate:.1f}%")
        
        else:
            click.echo("Use --list to list, --stats for statistics, or --id for campaign details")

@cli.command()
@click.option('--email', '-e', required=True, help='Test email address')
@click.option('--campaign-id', '-c', type=int, required=True, help='Campaign ID to test')
def test(email, campaign_id):
    """Send test email"""
    app = get_app()
    
    with app.app_context():
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            click.echo(f"Campaign with ID {campaign_id} not found", err=True)
            return
        
        click.echo(f"Sending test email to {email}...")
        try:
            result = send_test_email(campaign_id, email)
            if result['success']:
                click.echo("✓ Test email sent successfully!")
                click.echo(f"  Message ID: {result.get('message_id', 'N/A')}")
            else:
                click.echo(f"✗ Failed to send test email: {result.get('error', 'Unknown error')}", err=True)
        except Exception as e:
            click.echo(f"✗ Error sending test email: {str(e)}", err=True)

@cli.command()
@click.option('--setup', is_flag=True, help='Setup database and create default data')
def init(setup):
    """Initialize database and setup default data"""
    app = get_app()
    
    with app.app_context():
        if setup:
            click.echo("Setting up database...")
            
            # Create all tables
            db.create_all()
            
            # Check if default template exists
            if not EmailTemplate.query.first():
                click.echo("Creating default email template...")
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
            <p><a href="{{ unsubscribe_url }}">Unsubscribe</a></p>
        </div>
    </div>
</body>
</html>
                    ''',
                    text_content='{{ subject }}\n\nDear {{ name }},\n\n{{ custom_message }}\n\nBest regards,\n{{ from_name }}\n\n---\nThis email was sent to {{ email }}.\nUnsubscribe: {{ unsubscribe_url }}',
                    is_default=True
                )
                db.session.add(default_template)
                db.session.commit()
                click.echo("✓ Default template created")
            
            click.echo("✓ Database setup complete!")
        
        else:
            click.echo("Database initialized")
            click.echo(f"  Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
            click.echo(f"  SendGrid configured: {'Yes' if app.config.get('SENDGRID_API_KEY') else 'No'}")

@cli.command()
def status():
    """Show system status"""
    app = get_app()
    
    with app.app_context():
        click.echo("Email Shooter Status:")
        click.echo(f"  Environment: {app.config.get('FLASK_ENV', 'development')}")
        click.echo(f"  Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        click.echo(f"  SendGrid API: {'Configured' if app.config.get('SENDGRID_API_KEY') else 'Not configured'}")
        click.echo(f"  From Email: {app.config.get('FROM_EMAIL', 'Not set')}")
        
        # Count records
        subscribers = Subscriber.query.filter_by(is_active=True).count()
        campaigns = Campaign.query.count()
        templates = EmailTemplate.query.count()
        
        click.echo(f"  Active Subscribers: {subscribers}")
        click.echo(f"  Total Campaigns: {campaigns}")
        click.echo(f"  Email Templates: {templates}")

if __name__ == '__main__':
    cli()
