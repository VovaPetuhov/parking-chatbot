import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosmtplib
from email_validator import EmailNotValidError, validate_email

from config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Service for sending email notifications to admin about new reservations.
    
    Features:
    - Async SMTP using aiosmtplib
    - HTML email with reservation details
    - Graceful error handling (logs errors but doesn't crash)
    - Validation of email configuration
    """
    
    def __init__(self):
        settings = get_settings()
        self.enabled = settings.email_notifications_enabled
        self.admin_email = settings.admin_email
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.email_from = settings.email_from
        self.email_from_name = settings.email_from_name
        self.dashboard_url = settings.admin_dashboard_url
        self.app_name = settings.app_name
        self._validate_config()
    
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        if not self.enabled:
            logger.info("Email notifications are disabled")
            return False
        
        if not self.admin_email:
            logger.warning(
                "Email notifications enabled but ADMIN_EMAIL not configured. "
                "Notifications will be skipped."
            )
            return False
        
        if not self.smtp_username or not self.smtp_password:
            logger.warning(
                "Email notifications enabled but SMTP credentials not configured. "
                "Notifications will be skipped."
            )
            return False
        
        try:
            validate_email(self.admin_email)
        except EmailNotValidError as e:
            logger.error(f"Invalid admin email: {e}")
            return False
        
        logger.info(
            f"Email notifications configured: "
            f"admin={self.admin_email}, smtp={self.smtp_host}:{self.smtp_port}"
        )
        return True
    
    async def send_new_reservation_notification(
        self, 
        reservation_id: str,
        name: str,
        surname: str,
        car_plate: str,
        start_time: str,
        end_time: str,
        conversation_id: str
    ) -> bool:
        """
        Send email notification to admin about new reservation.
        Args:
            reservation_id: Unique reservation ID
            name: Customer first name
            surname: Customer last name
            car_plate: Car license plate
            start_time: Reservation start time
            end_time: Reservation end time
            conversation_id: Related conversation ID
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled or not self.admin_email:
            logger.debug("Email notifications disabled or not configured")
            return False
        
        try:
            message = self._create_email_message(
                reservation_id=reservation_id,
                name=name,
                surname=surname,
                car_plate=car_plate,
                start_time=start_time,
                end_time=end_time,
                conversation_id=conversation_id
            )
            
            await self._send_email(message)
            
            logger.info(
                f"Email notification sent to {self.admin_email} "
                f"for reservation {reservation_id}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send email notification for {reservation_id}: {e}",
                exc_info=True
            )
            return False
    
    def _create_email_message(
        self,
        reservation_id: str,
        name: str,
        surname: str,
        car_plate: str,
        start_time: str,
        end_time: str,
        conversation_id: str
    ) -> MIMEMultipart:
        """Create HTML email message"""
        message = MIMEMultipart("alternative")
        message["Subject"] = f"New Parking Reservation: {car_plate}"
        message["From"] = f"{self.email_from_name} <{self.email_from}>"
        message["To"] = self.admin_email
        text_content = f"""
            New Parking Reservation Requires Approval

            Reservation ID: {reservation_id}
            Customer: {name} {surname}
            Car Plate: {car_plate}
            Period: {start_time} - {end_time}
            Conversation ID: {conversation_id}

            Please review and approve/reject this reservation:
            {self.dashboard_url}/api/admin/reservations/{reservation_id}

            ---
            This is an automated message from {self.app_name}
        """
        
        html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background-color: #4CAF50;
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                    }}
                    .content {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-top: none;
                    }}
                    .detail-row {{
                        margin: 10px 0;
                        padding: 10px;
                        background-color: white;
                        border-left: 3px solid #4CAF50;
                    }}
                    .label {{
                        font-weight: bold;
                        color: #555;
                    }}
                    .value {{
                        color: #333;
                    }}
                    .actions {{
                        margin-top: 20px;
                        padding: 20px;
                        background-color: #fff;
                        text-align: center;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 24px;
                        margin: 5px;
                        text-decoration: none;
                        border-radius: 5px;
                        font-weight: bold;
                    }}
                    .view {{
                        background-color: #4CAF50;
                        color: white;
                    }}
                    .footer {{
                        margin-top: 20px;
                        padding: 10px;
                        text-align: center;
                        color: #888;
                        font-size: 12px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>New Parking Reservation</h1>
                    <p>Action Required</p>
                </div>
                
                <div class="content">
                    <h2>Reservation Details</h2>
                    
                    <div class="detail-row">
                        <span class="label">Reservation ID:</span>
                        <span class="value">{reservation_id}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">Customer:</span>
                        <span class="value">{name} {surname}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">Car Plate:</span>
                        <span class="value">{car_plate}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">Start Time:</span>
                        <span class="value">{start_time}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">End Time:</span>
                        <span class="value">{end_time}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="label">Conversation ID:</span>
                        <span class="value">{conversation_id}</span>
                    </div>
                </div>
                
                <div class="actions">
                    <p>Please review and take action:</p>
                    <a href="{self.dashboard_url}/api/admin/reservations/{reservation_id}" 
                    class="button view">
                        View Details
                    </a>
                </div>
                
                <div class="footer">
                    <p>This is an automated message from {self.app_name}</p>
                    <p>API Base: {self.dashboard_url}</p>
                </div>
            </body>
            </html>
        """
        
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        message.attach(part1)
        message.attach(part2)
        
        return message
    
    async def _send_email(self, message: MIMEMultipart):
        """Send email via SMTP with improved connection handling"""
        use_tls_from_start = (self.smtp_port == 465 and self.smtp_use_tls)

        smtp_client = aiosmtplib.SMTP(
            hostname=self.smtp_host,
            port=self.smtp_port,
            timeout=30,
            use_tls=use_tls_from_start
        )

        try:
            logger.debug(f"Connecting to {self.smtp_host}:{self.smtp_port}... (TLS from start: {use_tls_from_start})")
            await smtp_client.connect()
            logger.debug("Connected to SMTP server")

            if self.smtp_use_tls and self.smtp_port == 587:
                logger.debug("Starting TLS (STARTTLS)...")
                await smtp_client.starttls()
                logger.debug("TLS started")

            logger.debug(f"Logging in as {self.smtp_username}...")
            await smtp_client.login(self.smtp_username, self.smtp_password)
            logger.debug("Login successful")

            logger.debug("Sending email message...")
            await smtp_client.send_message(message)
            logger.debug(f"Email sent successfully via {self.smtp_host}:{self.smtp_port}")

        finally:
            try:
                await smtp_client.quit()
            except Exception as e:
                logger.debug(f"Error closing SMTP connection: {e}")


_notification_service: Optional[EmailNotificationService] = None


def get_notification_service() -> EmailNotificationService:
    """Get singleton notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = EmailNotificationService()
    return _notification_service
