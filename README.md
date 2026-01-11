# Email Shooter Application

A comprehensive email marketing application built with Python, Flask, and SendGrid for sending automated, templated emails to opted-in subscribers.

## Features

- **Subscriber Management**: Import subscribers from CSV, manage opt-in lists
- **Email Templates**: Create and manage HTML/text templates with Jinja2
- **Campaign Management**: Create, schedule, and track email campaigns
- **Personalization**: Dynamic content insertion using template variables
- **Scheduling**: Automatic email sending with APScheduler
- **Analytics**: Track delivery, open, click, and unsubscribe rates
- **Webhooks**: Handle SendGrid events for real-time tracking
- **Compliance**: CAN-SPAM compliant with unsubscribe links
- **CLI Interface**: Command-line tools for campaign management
- **Docker Support**: Containerized deployment ready

## Installation

### Prerequisites

- Python 3.8+
- SendGrid API key
- PostgreSQL (optional, SQLite supported)

### Quick Start

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd email_shooter
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Initialize database:**
   ```bash
   python cli.py init --setup
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

Visit `http://localhost:5000` to access the web dashboard.

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=sqlite:///email_shooter.db
# For PostgreSQL: postgresql://username:password@localhost/dbname

# SendGrid
SENDGRID_API_KEY=your_sendgrid_api_key
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Your Company Name

# Flask
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# Email Settings
EMAIL_BATCH_SIZE=100
EMAIL_RATE_LIMIT=1
UNSUBSCRIBE_URL=http://localhost:5000/unsubscribe

# Scheduler
SCHEDULER_ENABLED=true
```

### SendGrid Setup

1. Create a SendGrid account
2. Generate an API key
3. Configure sender authentication
4. Set up webhook endpoints at `/webhook/sendgrid`

## Usage

### Web Dashboard

The web interface provides:
- Dashboard with campaign statistics
- Campaign creation and management
- Subscriber import and management
- Template editor
- Email logs and analytics

### CLI Interface

```bash
# Initialize database
python cli.py init --setup

# Import subscribers from CSV
python cli.py subscribers --file subscribers.csv

# List campaigns
python cli.py campaigns --list

# Send a campaign
python cli.py send --campaign-id 1

# Send test email
python cli.py test --email test@example.com --campaign-id 1

# Show system status
python cli.py status
```

### CSV Import Format

```csv
email,name,custom_message
john@example.com,John Doe,Welcome to our newsletter!
jane@example.com,Jane Smith,Special offer just for you!
```

Required columns:
- `email` (required)
- `name` (optional)
- `custom_message` (optional)

### Template Variables

Use these variables in your email templates:

- `{{ name }}` - Subscriber name
- `{{ email }}` - Subscriber email
- `{{ subject }}` - Campaign subject
- `{{ custom_message }}` - Custom message
- `{{ from_name }}` - From name
- `{{ unsubscribe_url }}` - Unsubscribe link

## API Endpoints

### Webhook Endpoints

- `POST /webhook/sendgrid` - Receive SendGrid events

### API Endpoints

- `GET /api/template/<id>/preview` - Preview email template
- `POST /api/send-test` - Send test email

## Deployment

### Docker Deployment

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Environment setup:**
   Create a `.env` file with your production settings

3. **Database migration:**
   ```bash
   docker-compose exec email_shooter python cli.py init --setup
   ```

### Manual Deployment

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up production database:**
   ```bash
   export DATABASE_URL=postgresql://user:pass@host/db
   ```

3. **Run with Gunicorn:**
   ```bash
   gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
   ```

## Security and Compliance

### CAN-SPAM Compliance

- All emails include unsubscribe links
- Unsubscribe requests are processed immediately
- Physical address included in emails
- No misleading subject lines

### Email Deliverability

- Configure SPF, DKIM, and DMARC records
- Use dedicated IP addresses for high volume
- Monitor bounce rates and sender reputation
- Implement list hygiene practices

### Security Best Practices

- Environment variables for sensitive data
- CSRF protection enabled
- Input validation and sanitization
- Rate limiting on email sending
- Secure webhook handling

## Monitoring and Analytics

### Campaign Metrics

- Delivery rate
- Open rate
- Click rate
- Bounce rate
- Unsubscribe rate

### System Monitoring

- Database connection health
- SendGrid API status
- Email queue status
- Error tracking

## Troubleshooting

### Common Issues

1. **SendGrid API errors:**
   - Check API key validity
   - Verify sender authentication
   - Check rate limits

2. **Database connection issues:**
   - Verify DATABASE_URL format
   - Check database server status
   - Ensure proper permissions

3. **Template rendering errors:**
   - Validate Jinja2 syntax
   - Check variable names
   - Test with sample data

### Logging

Check application logs for:
- Email sending errors
- Database connection issues
- Webhook processing errors
- Template rendering problems

## Development

### Running Tests

```bash
# Set testing environment
export FLASK_ENV=testing

# Run application in test mode
python app.py
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Check the troubleshooting section
- Review the documentation
- Open an issue on GitHub

## Changelog

### Version 1.0.0
- Initial release
- Basic campaign management
- SendGrid integration
- Web dashboard
- CLI interface
- Docker support
