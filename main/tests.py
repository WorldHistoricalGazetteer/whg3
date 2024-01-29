from django.test import TestCase

from django.conf import settings 
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content

def send_test_email():
    sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    from_email = Email(settings.DEFAULT_FROM_EMAIL)
    to_email = To(settings.EMAIL_TO_ADMINS[0])  # Adjust as needed for test
    subject = "WHG v3 SendGrid Test"
    content = Content("text/plain", "This is a test email from WHG v3.")
    mail = Mail(from_email, to_email, subject, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    return response.status_code, response.body, response.headers
