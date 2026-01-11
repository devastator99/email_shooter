from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from sqlalchemy import func

from config import config
from models import db, Subscriber, Campaign, EmailLog, EmailTemplate, WebhookEvent
from database import init_db, import_subscribers_from_csv, get_campaign_stats
from mailer import send_campaign_email, send_test_email
from scheduler import scheduler
from utils import (
    save_uploaded_file, validate_csv_structure, get_status_color,
    paginate_query, format_datetime, calculate_campaign_progress
)

# Forms
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeField, SubmitField
from wtforms.validators import DataRequired, Email, Length

# Initialize Flask app
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    csrf = CSRFProtect(app)
    
    # Initialize database
    init_db(app)
    
    # Initialize scheduler
    if app.config.get('SCHEDULER_ENABLED'):
        from scheduler import init_scheduler, start_scheduler
        init_scheduler(app)
        start_scheduler()
    
    # Template context processors
    @app.context_processor
    def inject_config():
        return {
            'config': app.config,
            'get_status_color': get_status_color,
            'format_datetime': format_datetime,
            'calculate_campaign_progress': calculate_campaign_progress
        }
    
    # Forms
    class CampaignForm(FlaskForm):
        name = StringField('Campaign Name', validators=[DataRequired(), Length(min=1, max=255)])
        subject = StringField('Subject', validators=[DataRequired(), Length(min=1, max=255)])
        template_id = SelectField('Email Template', coerce=int, validators=[DataRequired()])
        scheduled_at = DateTimeField('Schedule Send (Optional)', format='%Y-%m-%d %H:%M')
        submit = SubmitField('Create Campaign')
    
    class SubscriberForm(FlaskForm):
        name = StringField('Name', validators=[Length(max=255)])
        email = StringField('Email', validators=[DataRequired(), Email(), Length(max=255)])
        custom_message = TextAreaField('Custom Message')
        submit = SubmitField('Add Subscriber')
    
    class TemplateForm(FlaskForm):
        name = StringField('Template Name', validators=[DataRequired(), Length(min=1, max=255)])
        subject = StringField('Default Subject', validators=[DataRequired(), Length(min=1, max=255)])
        html_content = TextAreaField('HTML Content', validators=[DataRequired()])
        text_content = TextAreaField('Text Content (Optional)')
        submit = SubmitField('Save Template')
    
    # Routes
    @app.route('/')
    def dashboard():
        # Get dashboard statistics
        stats = {
            'total_subscribers': Subscriber.query.filter_by(is_active=True).count(),
            'total_campaigns': Campaign.query.count(),
            'total_emails_sent': db.session.query(func.sum(Campaign.emails_sent)).scalar() or 0,
            'avg_open_rate': 0
        }
        
        # Calculate average open rate
        total_sent = db.session.query(func.sum(Campaign.emails_sent)).scalar() or 0
        if total_sent > 0:
            total_opens = db.session.query(func.sum(EmailLog.id)).filter(
                EmailLog.status == 'opened'
            ).scalar() or 0
            stats['avg_open_rate'] = (total_opens / total_sent) * 100
        
        # Get recent campaigns
        recent_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
        
        # Add open rates to campaigns
        for campaign in recent_campaigns:
            if campaign.emails_sent > 0:
                opens = EmailLog.query.filter_by(
                    campaign_id=campaign.id, 
                    status='opened'
                ).count()
                campaign.open_rate = (opens / campaign.emails_sent) * 100
            else:
                campaign.open_rate = 0
        
        return render_template('dashboard.html', 
                             stats=stats, 
                             recent_campaigns=recent_campaigns)
    
    @app.route('/campaigns')
    def campaigns():
        page = request.args.get('page', 1, type=int)
        campaigns = paginate_query(Campaign.query.order_by(Campaign.created_at.desc()), page)
        
        # Add open rates to campaigns
        for campaign in campaigns.items:
            if campaign.emails_sent > 0:
                opens = EmailLog.query.filter_by(
                    campaign_id=campaign.id, 
                    status='opened'
                ).count()
                campaign.open_rate = (opens / campaign.emails_sent) * 100
            else:
                campaign.open_rate = 0
        
        return render_template('campaigns.html', campaigns=campaigns)
    
    @app.route('/campaigns/create', methods=['GET', 'POST'])
    def create_campaign():
        form = CampaignForm()
        form.template_id.choices = [(t.id, t.name) for t in EmailTemplate.query.all()]
        
        if form.validate_on_submit():
            template = EmailTemplate.query.get(form.template_id.data)
            
            campaign = Campaign(
                name=form.name.data,
                subject=form.subject.data,
                template_html=template.html_content,
                template_text=template.text_content,
                scheduled_at=form.scheduled_at.data
            )
            
            db.session.add(campaign)
            db.session.commit()
            
            # Schedule campaign if scheduled_at is set
            if form.scheduled_at.data:
                campaign.status = 'scheduled'
                scheduler.add_job(
                    func=send_campaign_email,
                    trigger='date',
                    run_date=form.scheduled_at.data,
                    args=[campaign.id],
                    id=f'campaign_{campaign.id}'
                )
                db.session.commit()
                flash('Campaign scheduled successfully!', 'success')
            else:
                flash('Campaign created successfully!', 'success')
            
            return redirect(url_for('campaigns'))
        
        return render_template('create_campaign.html', form=form)
    
    @app.route('/campaigns/<int:id>')
    def view_campaign(id):
        campaign = Campaign.query.get_or_404(id)
        stats = get_campaign_stats(id)
        
        # Get email logs with pagination
        page = request.args.get('page', 1, type=int)
        logs = paginate_query(
            EmailLog.query.filter_by(campaign_id=id).order_by(EmailLog.created_at.desc()),
            page
        )
        
        return render_template('view_campaign.html', campaign=campaign, stats=stats, logs=logs)
    
    @app.route('/campaigns/<int:id>/send', methods=['POST'])
    def send_campaign(id):
        campaign = Campaign.query.get_or_404(id)
        
        if campaign.status not in ['draft', 'scheduled']:
            flash('Campaign cannot be sent. Current status: ' + campaign.status, 'error')
            return redirect(url_for('view_campaign', id=id))
        
        try:
            result = send_campaign_email(id)
            if result['success']:
                flash(f'Campaign sent successfully! {result["sent"]} emails sent, {result["failed"]} failed.', 'success')
            else:
                flash('Failed to send campaign: ' + str(result.get('error', 'Unknown error')), 'error')
        except Exception as e:
            flash('Error sending campaign: ' + str(e), 'error')
        
        return redirect(url_for('view_campaign', id=id))
    
    @app.route('/campaigns/<int:id>/delete', methods=['POST'])
    def delete_campaign(id):
        campaign = Campaign.query.get_or_404(id)
        
        if campaign.status not in ['draft', 'scheduled']:
            flash('Campaign cannot be deleted. Current status: ' + campaign.status, 'error')
            return redirect(url_for('view_campaign', id=id))
        
        db.session.delete(campaign)
        db.session.commit()
        flash('Campaign deleted successfully!', 'success')
        return redirect(url_for('campaigns'))
    
    @app.route('/subscribers')
    def subscribers():
        page = request.args.get('page', 1, type=int)
        subscribers = paginate_query(
            Subscriber.query.filter_by(is_active=True).order_by(Subscriber.created_at.desc()),
            page
        )
        return render_template('subscribers.html', subscribers=subscribers)
    
    @app.route('/subscribers/import', methods=['GET', 'POST'])
    def import_subscribers():
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            if file and file.filename.endswith('.csv'):
                # Save uploaded file
                upload_folder = os.path.join(app.root_path, 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = save_uploaded_file(file, upload_folder)
                
                if file_path:
                    # Validate CSV structure
                    validation = validate_csv_structure(file_path)
                    if not validation['valid']:
                        flash('Invalid CSV format: ' + validation['error'], 'error')
                        os.remove(file_path)
                        return redirect(request.url)
                    
                    # Import subscribers
                    result = import_subscribers_from_csv(file_path)
                    os.remove(file_path)  # Clean up uploaded file
                    
                    if result['success']:
                        flash(f'Successfully imported {result["imported"]} new subscribers, updated {result["updated"]} existing.', 'success')
                    else:
                        flash('Import failed: ' + result['error'], 'error')
                else:
                    flash('Failed to save uploaded file', 'error')
            else:
                flash('Please upload a CSV file', 'error')
        
        return render_template('import_subscribers.html')
    
    @app.route('/templates')
    def templates():
        templates = EmailTemplate.query.order_by(EmailTemplate.created_at.desc()).all()
        return render_template('templates.html', templates=templates)
    
    @app.route('/logs')
    def logs():
        page = request.args.get('page', 1, type=int)
        logs = paginate_query(
            EmailLog.query.order_by(EmailLog.created_at.desc()),
            page
        )
        return render_template('logs.html', logs=logs)
    
    @app.route('/unsubscribe')
    def unsubscribe():
        token = request.args.get('token')
        if not token:
            flash('Invalid unsubscribe link', 'error')
            return redirect(url_for('dashboard'))
        
        subscriber = Subscriber.query.filter_by(unsubscribe_token=token).first()
        if not subscriber:
            flash('Invalid unsubscribe link', 'error')
            return redirect(url_for('dashboard'))
        
        subscriber.is_active = False
        db.session.commit()
        
        return render_template('unsubscribed.html', subscriber=subscriber)
    
    # API Routes
    @app.route('/api/template/<int:template_id>/preview')
    def api_template_preview(template_id):
        template = EmailTemplate.query.get_or_404(template_id)
        
        # Sample context for preview
        context = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'subject': template.subject,
            'custom_message': 'This is a sample message.',
            'from_name': 'Your Company',
            'unsubscribe_url': '#'
        }
        
        try:
            from jinja2 import Template
            html_template = Template(template.html_content)
            html_content = html_template.render(**context)
            
            return jsonify({'html': html_content})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/send-test', methods=['POST'])
    def api_send_test():
        data = request.get_json()
        
        # Create temporary campaign for testing
        template = EmailTemplate.query.get(data['template_id'])
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        campaign = Campaign(
            name=data['name'],
            subject=data['subject'],
            template_html=template.html_content,
            template_text=template.text_content
        )
        
        try:
            result = send_test_email(campaign.id, data['test_email'])
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Webhook endpoint for SendGrid
    @app.route('/webhook/sendgrid', methods=['POST'])
    def sendgrid_webhook():
        events = request.get_json()
        
        if not events:
            return jsonify({'status': 'error'}), 400
        
        for event in events:
            # Store webhook event
            webhook_event = WebhookEvent(
                event_type=event.get('event'),
                email=event.get('email'),
                sendgrid_message_id=event.get('sg_message_id'),
                event_data=event
            )
            db.session.add(webhook_event)
            
            # Update email log if message_id exists
            message_id = event.get('sg_message_id')
            if message_id:
                email_log = EmailLog.query.filter_by(sendgrid_message_id=message_id).first()
                if email_log:
                    # Update status based on event type
                    event_type = event.get('event')
                    if event_type == 'delivered':
                        email_log.status = 'delivered'
                        email_log.delivered_at = datetime.utcnow()
                    elif event_type == 'open':
                        email_log.status = 'opened'
                        email_log.opened_at = datetime.utcnow()
                    elif event_type == 'click':
                        email_log.status = 'clicked'
                        email_log.clicked_at = datetime.utcnow()
                    elif event_type == 'bounce':
                        email_log.status = 'bounced'
                        email_log.bounced_at = datetime.utcnow()
                    elif event_type == 'unsubscribe':
                        email_log.status = 'unsubscribed'
                        email_log.unsubscribed_at = datetime.utcnow()
                        
                        # Unsubscribe user
                        subscriber = Subscriber.query.get(email_log.subscriber_id)
                        if subscriber:
                            subscriber.is_active = False
        
        db.session.commit()
        return jsonify({'status': 'success'})
    
    return app

# Create app instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
