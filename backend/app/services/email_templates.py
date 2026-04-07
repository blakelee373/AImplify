"""Default message template seeding for medspas."""

import logging
from app.database import SessionLocal
from app.models.message_template import MessageTemplate

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = [
    # --- SMS ---
    {
        "name": "Appointment Reminder",
        "category": "sms",
        "description": "Text reminder sent the day before an appointment",
        "body_text_template": (
            "Hi {{client_name}}! This is a reminder about your {{service_type}} "
            "appointment tomorrow at {{appointment_time}} at {{business_name}}. "
            "Reply C to confirm or R to reschedule."
        ),
        "variables": ["client_name", "service_type", "appointment_time", "business_name"],
    },
    {
        "name": "Welcome Text",
        "category": "sms",
        "description": "Welcome message for new clients",
        "body_text_template": (
            "Welcome to {{business_name}}! We're looking forward to seeing you for "
            "your {{service_type}} on {{appointment_date}}. Reply with any questions!"
        ),
        "variables": ["business_name", "service_type", "appointment_date"],
    },
    {
        "name": "Post-Appointment Follow-Up",
        "category": "sms",
        "description": "Follow-up text after a completed appointment",
        "body_text_template": (
            "Hi {{client_name}}, thanks for visiting {{business_name}} today! "
            "We hope you love your results. If you have any questions about "
            "aftercare, just reply to this text."
        ),
        "variables": ["client_name", "business_name"],
    },
    {
        "name": "No-Show Follow-Up",
        "category": "sms",
        "description": "Text sent after a client misses their appointment",
        "body_text_template": (
            "Hi {{client_name}}, we missed you at your appointment today at "
            "{{business_name}}. Would you like to reschedule? We'd love to see you!"
        ),
        "variables": ["client_name", "business_name"],
    },
    {
        "name": "Rebooking Reminder",
        "category": "sms",
        "description": "Reminder to rebook after a period since last visit",
        "body_text_template": (
            "Hi {{client_name}}, it's been {{days_since_visit}} days since your last "
            "{{service_type}} at {{business_name}}. Ready to book your next session? "
            "Reply YES and we'll find a time that works!"
        ),
        "variables": ["client_name", "days_since_visit", "service_type", "business_name"],
    },
    {
        "name": "Review Request",
        "category": "sms",
        "description": "Ask clients for a Google review after their visit",
        "body_text_template": (
            "Hi {{client_name}}, thank you for visiting {{business_name}}! "
            "If you had a great experience, we'd love a quick Google review: "
            "{{review_link}}. It means the world to us!"
        ),
        "variables": ["client_name", "business_name", "review_link"],
    },
    # --- Email ---
    {
        "name": "Welcome Email",
        "category": "email",
        "description": "Welcome email for new clients",
        "subject_template": "Welcome to {{business_name}}!",
        "body_html_template": (
            "<p>Hi {{client_name}},</p>"
            "<p>Welcome to <strong>{{business_name}}</strong>! We're thrilled to have you.</p>"
            "<p>Your upcoming {{service_type}} is scheduled for <strong>{{appointment_date}}</strong>. "
            "If you have any questions before your visit, just reply to this email.</p>"
            "<p>See you soon!<br>The {{business_name}} Team</p>"
        ),
        "body_text_template": (
            "Hi {{client_name}},\n\nWelcome to {{business_name}}! We're thrilled to have you.\n\n"
            "Your upcoming {{service_type}} is scheduled for {{appointment_date}}. "
            "If you have any questions before your visit, just reply to this email.\n\n"
            "See you soon!\nThe {{business_name}} Team"
        ),
        "variables": ["client_name", "business_name", "service_type", "appointment_date"],
    },
    {
        "name": "Appointment Reminder Email",
        "category": "email",
        "description": "Email reminder sent 24 hours before appointment",
        "subject_template": "Reminder: Your {{service_type}} tomorrow at {{appointment_time}}",
        "body_html_template": (
            "<p>Hi {{client_name}},</p>"
            "<p>Just a friendly reminder that your <strong>{{service_type}}</strong> at "
            "{{business_name}} is coming up tomorrow at <strong>{{appointment_time}}</strong>.</p>"
            "<p>If you need to reschedule, please reply to this email or give us a call.</p>"
            "<p>See you then!<br>{{business_name}}</p>"
        ),
        "body_text_template": (
            "Hi {{client_name}},\n\nJust a friendly reminder that your {{service_type}} "
            "at {{business_name}} is coming up tomorrow at {{appointment_time}}.\n\n"
            "If you need to reschedule, please reply to this email or give us a call.\n\n"
            "See you then!\n{{business_name}}"
        ),
        "variables": ["client_name", "service_type", "business_name", "appointment_time"],
    },
]


def seed_default_templates():
    """Insert default templates if they don't exist yet."""
    db = SessionLocal()
    try:
        existing = db.query(MessageTemplate).filter(MessageTemplate.is_default == True).count()  # noqa: E712
        if existing > 0:
            return

        for tpl in DEFAULT_TEMPLATES:
            db.add(MessageTemplate(
                name=tpl["name"],
                category=tpl["category"],
                description=tpl.get("description"),
                subject_template=tpl.get("subject_template"),
                body_html_template=tpl.get("body_html_template"),
                body_text_template=tpl["body_text_template"],
                variables=tpl.get("variables"),
                is_default=True,
            ))

        db.commit()
        logger.info("Seeded %d default message templates", len(DEFAULT_TEMPLATES))
    except Exception as e:
        logger.error("Failed to seed templates: %s", e)
        db.rollback()
    finally:
        db.close()
