from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
import logging
from flask import current_app

from mailer import send_campaign_email
from models import db, Campaign

# Configure logging
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.INFO)

# Create scheduler instance
scheduler = BackgroundScheduler()

def init_scheduler(app):
    """Initialize scheduler with Flask app context"""
    try:
        scheduler.configure(job_defaults={'coalesce': False, 'max_instances': 3})
    except:
        # Scheduler already configured, ignore
        pass
    
    def scheduled_job_wrapper(campaign_id):
        """Wrapper for scheduled jobs to run within app context"""
        with app.app_context():
            try:
                campaign = Campaign.query.get(campaign_id)
                if campaign and campaign.status == 'scheduled':
                    print(f"Executing scheduled campaign: {campaign.name}")
                    result = send_campaign_email(campaign_id)
                    print(f"Campaign execution result: {result}")
                else:
                    print(f"Campaign {campaign_id} not found or not in scheduled status")
            except Exception as e:
                print(f"Error executing scheduled campaign {campaign_id}: {str(e)}")
                # Update campaign status to failed
                try:
                    campaign = Campaign.query.get(campaign_id)
                    if campaign:
                        campaign.status = 'failed'
                        db.session.commit()
                except:
                    pass
    
    # Add the wrapper to scheduler's job store
    scheduler.app_context = app
    scheduler.job_wrapper = scheduled_job_wrapper

def schedule_campaign(campaign_id, scheduled_time):
    """Schedule a campaign to be sent at a specific time"""
    try:
        scheduler.add_job(
            func=scheduler.job_wrapper,
            trigger=DateTrigger(run_date=scheduled_time),
            args=[campaign_id],
            id=f'campaign_{campaign_id}',
            replace_existing=True
        )
        return True
    except Exception as e:
        print(f"Error scheduling campaign {campaign_id}: {str(e)}")
        return False

def cancel_scheduled_campaign(campaign_id):
    """Cancel a scheduled campaign"""
    try:
        scheduler.remove_job(f'campaign_{campaign_id}')
        return True
    except Exception as e:
        print(f"Error canceling scheduled campaign {campaign_id}: {str(e)}")
        return False

def get_scheduled_jobs():
    """Get all scheduled jobs"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'next_run_time': job.next_run_time,
            'args': job.args
        })
    return jobs

def setup_recurring_jobs():
    """Setup any recurring jobs (like cleanup tasks)"""
    # Example: Clean up old webhook events daily
    def cleanup_old_webhook_events():
        with scheduler.app_context.app_context():
            try:
                from models import WebhookEvent
                from datetime import timedelta
                
                # Delete webhook events older than 30 days
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                old_events = WebhookEvent.query.filter(WebhookEvent.created_at < cutoff_date).all()
                
                for event in old_events:
                    db.session.delete(event)
                
                db.session.commit()
                print(f"Cleaned up {len(old_events)} old webhook events")
            except Exception as e:
                print(f"Error cleaning up old webhook events: {str(e)}")
    
    # Schedule daily cleanup at 2 AM
    scheduler.add_job(
        func=cleanup_old_webhook_events,
        trigger=CronTrigger(hour=2, minute=0),
        id='daily_cleanup',
        replace_existing=True
    )

# Initialize scheduler when module is imported
def start_scheduler():
    """Start the scheduler"""
    if not scheduler.running:
        scheduler.start()
        print("Scheduler started")

def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        print("Scheduler stopped")
