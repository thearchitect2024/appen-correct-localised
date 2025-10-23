"""
Email service for AppenCorrect using SendGrid API.
Handles password reset emails and other notifications.
"""

import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)

def send_password_reset_email(email, reset_token, base_url):
    """
    Send password reset email using SendGrid.
    
    Args:
        email: Recipient email address
        reset_token: Password reset token
        base_url: Base URL for the application
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get SendGrid configuration from environment
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('FROM_EMAIL', 'noreply@appen.com')
        from_name = os.getenv('FROM_NAME', 'AppenCorrect Team')
        
        if not sendgrid_api_key:
            logger.error("SENDGRID_API_KEY not configured")
            return False
        
        # Construct reset URL
        reset_url = f"{base_url}reset-password/{reset_token}"
        
        # Create email content
        subject = "AppenCorrect Password Reset"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Password Reset - AppenCorrect</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
                <h1 style="margin: 0; font-size: 24px;">🔑 AppenCorrect</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Password Reset Request</p>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 25px;">
                <h2 style="color: #333; margin-top: 0;">Password Reset Requested</h2>
                <p style="color: #666; line-height: 1.6;">
                    Someone (hopefully you) requested a password reset for your AppenCorrect account: <strong>{email}</strong>
                </p>
                <p style="color: #666; line-height: 1.6;">
                    Click the button below to reset your password. This link will expire in <strong>1 hour</strong>.
                </p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" 
                   style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block; font-size: 16px;">
                    🔓 Reset My Password
                </a>
            </div>
            
            <div style="background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px; border-radius: 6px; margin: 25px 0;">
                <p style="margin: 0; font-size: 14px;">
                    <strong>Security Note:</strong> If you didn't request this password reset, you can safely ignore this email. 
                    Your password will not be changed unless you click the reset link above.
                </p>
            </div>
            
            <div style="border-top: 1px solid #e9ecef; padding-top: 20px; margin-top: 30px; color: #6c757d; font-size: 12px;">
                <p>This email was sent by the AppenCorrect API Management System.</p>
                <p>Reset link: <a href="{reset_url}" style="color: #667eea;">{reset_url}</a></p>
                <p>This link expires on: <em>1 hour from now</em></p>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_content = f"""
        AppenCorrect Password Reset
        
        Someone requested a password reset for your AppenCorrect account: {email}
        
        To reset your password, visit this link:
        {reset_url}
        
        This link will expire in 1 hour.
        
        If you didn't request this reset, you can safely ignore this email.
        
        --
        AppenCorrect Team
        """
        
        # Create SendGrid email
        message = Mail(
            from_email=(from_email, from_name),
            to_emails=email,
            subject=subject,
            html_content=html_content,
            plain_text_content=text_content
        )
        
        # Send email
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        response = sg.send(message)
        
        logger.info(f"Password reset email sent to {email}, status: {response.status_code}")
        return response.status_code == 202  # SendGrid success code
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        return False

def test_email_configuration():
    """Test if SendGrid is properly configured."""
    try:
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        from_email = os.getenv('FROM_EMAIL')
        
        if not sendgrid_api_key:
            return False, "SENDGRID_API_KEY not configured"
        
        if not from_email:
            return False, "FROM_EMAIL not configured"
        
        # Test SendGrid connection (without sending email)
        sg = SendGridAPIClient(api_key=sendgrid_api_key)
        
        return True, "SendGrid configuration appears valid"
        
    except Exception as e:
        return False, f"SendGrid configuration error: {e}"
