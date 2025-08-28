# Unipile Connect - Dynamic Authentication & Dashboard

A dynamic FastAPI application that provides user authentication and a dashboard for managing Unipile account connections.

## ✨ Features

- **🔐 Production-Ready Authentication System**

  - User registration and login
  - Secure password hashing with bcrypt
  - Session management with database storage
  - Role-based access control (Admin/User)
  - Profile management and password changes

- **🗄️ Database Integration**

  - SQLAlchemy ORM with PostgreSQL/SQLite support
  - User management and account tracking
  - Session persistence and cleanup
  - Data validation with Pydantic schemas

- **📊 Real-time Dashboard**

  - Live account connection status
  - Dynamic account management
  - Real-time updates via API
  - Account disconnection functionality
  - User-specific account views

- **👥 User Management**

  - Self-service user registration
  - Admin user creation and management
  - User profile editing
  - Account activation/deactivation

- **🔗 Unipile Integration**
  - LinkedIn connection via Unipile
  - Webhook notifications
  - Account status tracking
  - Error handling for API issues
  - Multi-user account isolation

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
# OR
source .venv/bin/activate     # Linux/Mac

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the root directory:

### 3. Initialize Database

```bash
# Initialize database and create admin user
python init_db.py
```

```env
# Unipile Configuration
UNIPILE_API_BASE=https://api8.unipile.com:13816/api/v1
UNIPILE_API_HOST=https://api8.unipile.com:13816
UNIPILE_API_KEY=your-actual-unipile-api-key

# App Configuration
APP_BASE_URL=http://127.0.0.1:8000

# Database Configuration
DATABASE_URL=sqlite:///./unipile_connect.db

# Authentication
SECRET_KEY=your-secret-key-change-this-in-production
```

### 4. Run the Application

**Option 1: Using the startup script (Recommended)**

```bash
python run.py
```

**Option 2: Using uvicorn directly**

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Access the Application

- **Homepage**: http://127.0.0.1:8000
- **Login**: http://127.0.0.1:8000/login
- **Dashboard**: http://127.0.0.1:8000/dashboard

**Default credentials**: `admin` / `admin123`

## 🔧 How It Works

### Authentication Flow

1. **Login**: User enters credentials → Session created → Redirected to dashboard
2. **Session Management**: 24-hour session cookies with secure settings
3. **Protected Routes**: All sensitive endpoints check authentication
4. **Logout**: Session destroyed → Cookie removed → Redirected to home

### Dashboard Features

1. **Real-time Updates**: Auto-refresh every 30 seconds
2. **Dynamic Account Management**:
   - View connection status
   - Disconnect accounts
   - View detailed account information
3. **Error Handling**: User-friendly error messages for Unipile API issues
4. **Responsive Design**: Works on all device sizes

### API Endpoints

- `GET /` - Homepage (public)
- `GET /login` - Login page (public)
- `POST /login` - Authentication (public)
- `GET /users/register` - User registration page (public)
- `POST /users/register` - User registration (public)
- `GET /users/profile` - User profile page (protected)
- `POST /users/profile` - Update profile (protected)
- `POST /users/change-password` - Change password (protected)
- `GET /users/admin` - Admin dashboard (admin only)
- `POST /users/admin/create` - Create user (admin only)
- `POST /users/admin/update/{user_id}` - Update user (admin only)
- `POST /users/admin/delete/{user_id}` - Delete user (admin only)
- `GET /dashboard` - User dashboard (protected)
- `GET /logout` - Logout (protected)
- `GET /connect/linkedin` - Start LinkedIn connection (protected)
- `POST /disconnect/{account_id}` - Disconnect account (protected)
- `GET /api/accounts` - Get accounts data (protected)
- `GET /api/me` - Get current user info (protected)
- `GET /api/users` - Get all users (admin only)
- `POST /unipile/notify` - Webhook for Unipile notifications (public)

## 🎯 Dynamic Features

### Real-time Account Updates

- **Auto-refresh**: Dashboard updates every 30 seconds
- **Live Status**: See connection status changes immediately
- **Dynamic UI**: Account list updates without page reload

### Interactive Account Management

- **Disconnect**: Remove accounts with confirmation
- **Details Modal**: View full account information
- **Status Indicators**: Visual connection status

### Smart Error Handling

- **API Errors**: Graceful handling of Unipile API issues
- **User Feedback**: Clear error messages and suggestions
- **Fallback Behavior**: Application continues working even with API issues

## 🔒 Security Features

- **Session-based Authentication**: Secure cookie-based sessions
- **Protected Routes**: Authentication required for sensitive endpoints
- **CSRF Protection**: Form-based authentication with proper tokens
- **Secure Cookies**: HttpOnly, SameSite, and configurable security flags

## 📱 User Experience

### For End Users

1. **Simple Login**: Clean, intuitive login interface
2. **Dashboard Overview**: Clear view of all connected accounts
3. **Easy Management**: One-click account disconnection
4. **Real-time Updates**: Always see current status

### For Administrators

1. **User Management**: Track user sessions and connections
2. **Account Monitoring**: Real-time view of all connections
3. **Error Tracking**: Monitor Unipile API health
4. **Audit Trail**: Track account connections/disconnections

## 🚨 Troubleshooting

### Common Issues

1. **"No module named uvicorn"**

   - Activate virtual environment: `.\.venv\Scripts\Activate.ps1`
   - Install packages: `pip install -r requirements.txt`

2. **"Form data requires python-multipart"**

   - Install missing package: `pip install python-multipart`

3. **Unipile API errors**

   - Check your `.env` file configuration
   - Verify API key is valid
   - Check network connectivity

4. **Session not working**
   - Clear browser cookies
   - Check browser security settings
   - Verify cookie settings in code

### Debug Mode

Enable debug logging by setting environment variable:

```bash
set PYTHONPATH=.
python -m uvicorn app.main:app --reload --log-level debug
```

## 🔮 Future Enhancements

- **Database Integration**: Replace in-memory storage with PostgreSQL
- **User Registration**: Allow users to create accounts
- **Multi-tenant Support**: Separate dashboards for different organizations
- **Advanced Analytics**: Connection metrics and usage statistics
- **Webhook Management**: Configure custom webhook endpoints
- **API Rate Limiting**: Protect against abuse
- **Audit Logging**: Track all user actions

## 📄 License

This project is for demonstration purposes. Please ensure compliance with Unipile's terms of service and implement proper security measures for production use.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Built with ❤️ using FastAPI, Jinja2, and modern web technologies**
