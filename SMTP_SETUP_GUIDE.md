# 📧 SMTP Setup Guide for Password Reset Emails

## Overview

This guide will help you configure SMTP for sending password reset emails in your Unipile Connect application. The system now supports beautiful HTML emails with proper error handling and logging.

## ✅ What's Been Implemented

- **Enhanced SMTP Email Service**: Professional HTML emails with fallback text version
- **Improved Error Handling**: Specific error types (authentication, recipients refused, etc.)
- **Admin Test Endpoints**: Test SMTP configuration without triggering password reset
- **Configuration Status**: Check SMTP setup status via API
- **Better Logging**: Detailed logs for debugging email issues

## 🔧 Environment Configuration

Create a `.env` file in your project root with the following SMTP settings:

### Gmail Configuration (Recommended)

```bash
# SMTP Configuration for Gmail
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here
SMTP_FROM=your-email@gmail.com
SMTP_USE_TLS=true
```

**Important for Gmail:**

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password (not your regular password)
3. Use the App Password in `SMTP_PASSWORD`

### Other Email Providers

#### Outlook/Hotmail

```bash
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
SMTP_FROM=your-email@outlook.com
SMTP_USE_TLS=true
```

#### Yahoo Mail

```bash
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@yahoo.com
SMTP_USE_TLS=true
```

#### Custom SMTP Server

```bash
SMTP_HOST=your-smtp-server.com
SMTP_PORT=587  # or 465 for SSL, 25 for non-encrypted
SMTP_USER=your-username
SMTP_PASSWORD=your-password
SMTP_FROM=no-reply@yourdomain.com
SMTP_USE_TLS=true  # false for non-TLS connections
```

### Development Settings

```bash
# Show reset link on page for development/testing
SHOW_RESET_LINK_ON_PAGE=true
```

## 🚀 Setup Steps

### 1. Create Environment File

Copy the appropriate configuration above into a `.env` file in your project root.

### 2. Configure Your Email Provider

#### For Gmail:

1. Go to your [Google Account settings](https://myaccount.google.com/)
2. Navigate to Security → 2-Step Verification (enable if not already)
3. Go to Security → App passwords
4. Generate a new app password for "Mail"
5. Use this app password in your `.env` file

#### For Other Providers:

Follow your email provider's documentation for SMTP access.

### 3. Test Your Configuration

Once configured, you can test your SMTP setup using the admin endpoints:

```bash
# Check SMTP status
GET /users/admin/smtp-status

# Send test email (requires admin access)
POST /users/admin/test-smtp
Content-Type: application/x-www-form-urlencoded

test_email=your-test@email.com
```

## 🧪 Testing the Implementation

### 1. Via Admin Panel

1. Log in as an admin user
2. Visit `/users/admin/smtp-status` to check configuration
3. Use `/users/admin/test-smtp` to send a test email

### 2. Via Password Reset

1. Go to `/users/forgot-password`
2. Enter an email address of an existing user
3. Check your email for the reset link

### 3. Development Mode

Set `SHOW_RESET_LINK_ON_PAGE=true` in your `.env` file to see reset links directly on the webpage during development.

## 🔍 Troubleshooting

### Common Issues

#### 1. Authentication Failed

- **Gmail**: Make sure you're using an App Password, not your regular password
- **Other providers**: Verify username and password are correct
- Check if 2FA is required for your email provider

#### 2. Connection Timeout

- Verify `SMTP_HOST` and `SMTP_PORT` are correct
- Check firewall settings
- Try different ports (587 for TLS, 465 for SSL)

#### 3. Recipients Refused

- Verify the sender email (`SMTP_FROM`) is authorized
- Some providers require the FROM address to match the authenticated user

#### 4. TLS/SSL Issues

- Try toggling `SMTP_USE_TLS` between `true` and `false`
- For port 465, you might need SSL instead of TLS

### Checking Logs

The application logs detailed information about email sending:

```bash
# Successful email
INFO:app.users:Password reset email sent successfully to user@example.com

# Failed email with reason
ERROR:app.users:SMTP Authentication failed for user@example.com: (535, '5.7.8 Username and Password not accepted')
```

### Debug Mode

Enable debug logging by setting `SHOW_RESET_LINK_ON_PAGE=true` to see reset URLs in the console and on the webpage.

## 📋 Email Template Features

The new email implementation includes:

- **Professional HTML Design**: Branded email with proper styling
- **Mobile Responsive**: Looks great on all devices
- **Security Warnings**: Clear expiration and security information
- **Fallback Text**: Plain text version for email clients that don't support HTML
- **Personalization**: Uses user's full name or username
- **Clear Call-to-Action**: Prominent reset button and backup link

## 🔒 Security Considerations

1. **Environment Variables**: Never commit your `.env` file to version control
2. **App Passwords**: Use app-specific passwords instead of main account passwords
3. **Token Expiration**: Reset tokens expire in 30 minutes
4. **One-time Use**: Each reset token can only be used once
5. **HTTPS**: Use HTTPS in production for secure token transmission

## 📞 Support

If you encounter issues:

1. Check the application logs for specific error messages
2. Use the admin SMTP status endpoint to verify configuration
3. Test with the admin test email endpoint
4. Verify your email provider's SMTP settings and requirements

## 🎯 Next Steps

1. **Production Setup**: Configure with your production email service
2. **Monitoring**: Set up email delivery monitoring
3. **Templates**: Customize the email template design if needed
4. **Backup**: Consider multiple SMTP providers for redundancy

---

Your SMTP implementation is now ready! The system will automatically send professional-looking password reset emails when users request them.
