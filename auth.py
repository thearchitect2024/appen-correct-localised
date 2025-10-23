"""
Simple authentication system for AppenCorrect admin pages.
Requires @appen.com email addresses for access.
"""

import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, render_template_string
import re
import hashlib

# Simple in-memory session store (in production, use Redis or database)
active_sessions = {}

# Database for user accounts
DB_PATH = 'appencorrect_users.db'

def generate_session_token():
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)

def init_users_db():
    """Initialize the users database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active BOOLEAN DEFAULT 1,
                reset_token TEXT,
                reset_token_expires TEXT
            )
        ''')
        
        # Add reset token columns if they don't exist (for existing databases)
        try:
            conn.execute('ALTER TABLE users ADD COLUMN reset_token TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            conn.execute('ALTER TABLE users ADD COLUMN reset_token_expires TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing users database: {e}")

def hash_password(password):
    """Hash a password with salt."""
    salt = secrets.token_hex(32)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password, stored_hash):
    """Verify a password against its hash."""
    try:
        salt, password_hash = stored_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
    except:
        return False

def create_user(email, password):
    """Create a new user account."""
    if not is_appen_email(email):
        return False, "Only @appen.com email addresses are allowed"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    try:
        init_users_db()
        conn = sqlite3.connect(DB_PATH)
        
        # Check if user already exists
        cursor = conn.execute('SELECT id FROM users WHERE email = ?', (email.lower(),))
        if cursor.fetchone():
            conn.close()
            return False, "User already exists"
        
        # Create new user
        password_hash = hash_password(password)
        conn.execute('''
            INSERT INTO users (email, password_hash, created_at)
            VALUES (?, ?, ?)
        ''', (email.lower(), password_hash, datetime.utcnow().isoformat()))
        
        conn.commit()
        conn.close()
        return True, "Account created successfully"
        
    except Exception as e:
        return False, f"Error creating account: {str(e)}"

def get_user(email):
    """Get user by email."""
    try:
        init_users_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute('SELECT * FROM users WHERE email = ? AND is_active = 1', (email.lower(),))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception:
        return None

def generate_password_reset_token(email):
    """Generate a password reset token for a user."""
    if not is_appen_email(email):
        return False, "Only @appen.com email addresses are allowed"
    
    user = get_user(email)
    if not user:
        return False, "User not found"
    
    try:
        # Generate secure reset token
        reset_token = secrets.token_urlsafe(32)
        # Token expires in 1 hour
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        init_users_db()
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            UPDATE users 
            SET reset_token = ?, reset_token_expires = ?
            WHERE email = ?
        ''', (reset_token, expires_at, email.lower()))
        
        conn.commit()
        conn.close()
        
        return True, reset_token
        
    except Exception as e:
        return False, f"Error generating reset token: {str(e)}"

def verify_reset_token(token):
    """Verify a password reset token and return user email if valid."""
    if not token:
        return None
    
    try:
        init_users_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute('''
            SELECT email, reset_token_expires 
            FROM users 
            WHERE reset_token = ? AND is_active = 1
        ''', (token,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        # Check if token has expired
        expires_at = datetime.fromisoformat(result['reset_token_expires'])
        if datetime.utcnow() > expires_at:
            return None
        
        return result['email']
        
    except Exception:
        return None

def reset_password_with_token(token, new_password):
    """Reset password using a valid reset token."""
    email = verify_reset_token(token)
    if not email:
        return False, "Invalid or expired reset token"
    
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters long"
    
    try:
        # Hash new password
        password_hash = hash_password(new_password)
        
        init_users_db()
        conn = sqlite3.connect(DB_PATH)
        
        # Update password and clear reset token
        conn.execute('''
            UPDATE users 
            SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL
            WHERE email = ?
        ''', (password_hash, email.lower()))
        
        conn.commit()
        conn.close()
        
        return True, "Password reset successfully"
        
    except Exception as e:
        return False, f"Error resetting password: {str(e)}"

def update_last_login(email):
    """Update user's last login timestamp."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('UPDATE users SET last_login = ? WHERE email = ?', 
                    (datetime.utcnow().isoformat(), email.lower()))
        conn.commit()
        conn.close()
    except Exception:
        pass

def is_appen_email(email):
    """Check if email is from appen.com domain."""
    if not email:
        return False
    
    # Simple email validation and domain check
    email_pattern = r'^[a-zA-Z0-9._%+-]+@appen\.com$'
    return re.match(email_pattern, email.lower()) is not None

def authenticate_user(email, password=None):
    """
    Authenticate user against the database.
    """
    if not is_appen_email(email):
        return False, "Only @appen.com email addresses are allowed"
    
    if not password:
        return False, "Password is required"
    
    # Get user from database
    user = get_user(email)
    if not user:
        return False, "User not found. Please register first."
    
    # Verify password
    if verify_password(password, user['password_hash']):
        update_last_login(email)
        return True, "Authentication successful"
    else:
        return False, "Invalid password"

def create_session(email):
    """Create a new session for authenticated user."""
    session_token = generate_session_token()
    session_data = {
        'email': email,
        'authenticated': True,
        'created_at': str(datetime.utcnow())
    }
    
    # Store in session
    session['auth_token'] = session_token
    session['user_email'] = email
    session['authenticated'] = True
    
    # Also store in memory (for additional validation if needed)
    active_sessions[session_token] = session_data
    
    return session_token

def is_authenticated():
    """Check if current user is authenticated."""
    return session.get('authenticated', False) and is_appen_email(session.get('user_email'))

def get_current_user():
    """Get current authenticated user email."""
    if is_authenticated():
        return session.get('user_email')
    return None

def logout_user():
    """Logout current user and clear session."""
    auth_token = session.get('auth_token')
    if auth_token and auth_token in active_sessions:
        del active_sessions[auth_token]
    
    session.clear()

def require_auth(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # Return login page for GET requests
            if request.method == 'GET':
                return redirect(url_for('login'))
            # Return JSON error for API requests
            else:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'Please login with an @appen.com email address'
                }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# Login/Registration page HTML template
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AppenCorrect - {{ mode.title() }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            width: 90%;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #333;
            margin: 0 0 10px 0;
            font-size: 2em;
        }
        .login-header p {
            color: #666;
            margin: 0;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
            box-sizing: border-box;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .login-btn {
            width: 100%;
            background: #667eea;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s;
            margin-bottom: 15px;
        }
        .login-btn:hover {
            background: #5a67d8;
        }
        .register-btn {
            width: 100%;
            background: #48bb78;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .register-btn:hover {
            background: #38a169;
        }
        .alert {
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .alert-error {
            background: #fee;
            color: #c53030;
            border: 1px solid #feb2b2;
        }
        .alert-success {
            background: #f0fff4;
            color: #22543d;
            border: 1px solid #9ae6b4;
        }
        .alert-info {
            background: #e6f3ff;
            color: #2b6cb0;
            border: 1px solid #bee3f8;
        }
        .toggle-link {
            text-align: center;
            margin-top: 20px;
        }
        .toggle-link a {
            color: #667eea;
            text-decoration: none;
        }
        .toggle-link a:hover {
            text-decoration: underline;
        }
        .back-link {
            text-align: center;
            margin-top: 15px;
            border-top: 1px solid #e0e0e0;
            padding-top: 15px;
        }
        .back-link a {
            color: #666;
            text-decoration: none;
        }
        .back-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🔐 AppenCorrect</h1>
            <p>{% if mode == 'register' %}Create Account{% else %}API Management Access{% endif %}</p>
        </div>
        
        {% if error %}
        <div class="alert alert-error">
            {{ error }}
        </div>
        {% endif %}
        
        {% if success %}
        <div class="alert alert-success">
            {{ success }}
        </div>
        {% endif %}
        
        <div class="alert alert-info">
            <strong>Restricted Access:</strong> Only @appen.com email addresses are permitted.
        </div>
        
        {% if mode == 'register' %}
        <form method="POST" action="/register">
            <div class="form-group">
                <label for="email">Appen Email Address</label>
                <input type="email" id="email" name="email" placeholder="your.name@appen.com" required>
            </div>
            
            <div class="form-group">
                <label for="password">Choose Password</label>
                <input type="password" id="password" name="password" placeholder="At least 6 characters" required>
            </div>
            
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" placeholder="Repeat your password" required>
            </div>
            
            <button type="submit" class="register-btn">✨ Create Account</button>
        </form>
        
        <div class="toggle-link">
            <a href="/login">Already have an account? Login here</a>
        </div>
        {% else %}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="email">Appen Email Address</label>
                <input type="email" id="email" name="email" placeholder="your.name@appen.com" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="Enter your password" required>
            </div>
            
            <button type="submit" class="login-btn">🚀 Login</button>
        </form>
        
        <div class="toggle-link">
            <a href="/register">New Appen employee? Register here</a>
        </div>
        
        <div class="toggle-link" style="margin-top: 10px;">
            <a href="/forgot-password">Forgot your password?</a>
        </div>
        {% endif %}
        
        <div class="back-link">
            <a href="/">← Back to Demo</a>
        </div>
    </div>
</body>
</html>
"""

# Forgot Password Template
FORGOT_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AppenCorrect - Forgot Password</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            width: 90%;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #333;
            margin: 0 0 10px 0;
            font-size: 2em;
        }
        .login-header p {
            color: #666;
            margin: 0;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
            box-sizing: border-box;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .reset-btn {
            width: 100%;
            background: #ff6b6b;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s;
            margin-bottom: 15px;
        }
        .reset-btn:hover {
            background: #ee5a52;
        }
        .alert {
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .alert-error {
            background: #fee;
            color: #c53030;
            border: 1px solid #feb2b2;
        }
        .alert-success {
            background: #f0fff4;
            color: #22543d;
            border: 1px solid #9ae6b4;
        }
        .alert-info {
            background: #e6f3ff;
            color: #2b6cb0;
            border: 1px solid #bee3f8;
        }
        .toggle-link {
            text-align: center;
            margin-top: 20px;
        }
        .toggle-link a {
            color: #667eea;
            text-decoration: none;
        }
        .toggle-link a:hover {
            text-decoration: underline;
        }
        .back-link {
            text-align: center;
            margin-top: 15px;
            border-top: 1px solid #e0e0e0;
            padding-top: 15px;
        }
        .back-link a {
            color: #666;
            text-decoration: none;
        }
        .back-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🔑 Reset Password</h1>
            <p>Enter your Appen email to reset your password</p>
        </div>
        
        {% if error %}
        <div class="alert alert-error">
            {{ error }}
        </div>
        {% endif %}
        
        {% if success %}
        <div class="alert alert-success">
            {{ success }}
        </div>
        {% endif %}
        
        {% if not success %}
        <div class="alert alert-info">
            <strong>For Appen Employees:</strong> Only @appen.com email addresses can reset passwords.
        </div>
        
        <form method="POST" action="/forgot-password">
            <div class="form-group">
                <label for="email">Your Appen Email Address</label>
                <input type="email" id="email" name="email" placeholder="your.name@appen.com" required>
            </div>
            
            <button type="submit" class="reset-btn">🔑 Generate Reset Link</button>
        </form>
        {% endif %}
        
        <div class="toggle-link">
            <a href="/login">← Back to Login</a>
        </div>
        
        <div class="back-link">
            <a href="/">← Back to Demo</a>
        </div>
    </div>
</body>
</html>
"""

# Password Reset Template
RESET_PASSWORD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AppenCorrect - Reset Password</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            width: 90%;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #333;
            margin: 0 0 10px 0;
            font-size: 2em;
        }
        .login-header p {
            color: #666;
            margin: 0;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
            box-sizing: border-box;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .reset-btn {
            width: 100%;
            background: #48bb78;
            color: white;
            border: none;
            padding: 12px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s;
            margin-bottom: 15px;
        }
        .reset-btn:hover {
            background: #38a169;
        }
        .alert {
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .alert-error {
            background: #fee;
            color: #c53030;
            border: 1px solid #feb2b2;
        }
        .alert-success {
            background: #f0fff4;
            color: #22543d;
            border: 1px solid #9ae6b4;
        }
        .toggle-link {
            text-align: center;
            margin-top: 20px;
        }
        .toggle-link a {
            color: #667eea;
            text-decoration: none;
        }
        .toggle-link a:hover {
            text-decoration: underline;
        }
        .back-link {
            text-align: center;
            margin-top: 15px;
            border-top: 1px solid #e0e0e0;
            padding-top: 15px;
        }
        .back-link a {
            color: #666;
            text-decoration: none;
        }
        .back-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🔓 Set New Password</h1>
            <p>Create a new password for {{ email }}</p>
        </div>
        
        {% if error %}
        <div class="alert alert-error">
            {{ error }}
        </div>
        {% endif %}
        
        {% if success %}
        <div class="alert alert-success">
            {{ success }}
        </div>
        {% else %}
        <form method="POST" action="/reset-password/{{ token }}">
            <div class="form-group">
                <label for="password">New Password</label>
                <input type="password" id="password" name="password" placeholder="At least 6 characters" required>
            </div>
            
            <div class="form-group">
                <label for="confirm_password">Confirm New Password</label>
                <input type="password" id="confirm_password" name="confirm_password" placeholder="Repeat your new password" required>
            </div>
            
            <button type="submit" class="reset-btn">🔓 Reset Password</button>
        </form>
        {% endif %}
        
        <div class="toggle-link">
            <a href="/login">← Back to Login</a>
        </div>
        
        <div class="back-link">
            <a href="/">← Back to Demo</a>
        </div>
    </div>
    
    <script>
        // Simple password confirmation validation
        document.querySelector('form').addEventListener('submit', function(e) {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            
            if (password !== confirmPassword) {
                e.preventDefault();
                alert('Passwords do not match. Please try again.');
                return false;
            }
        });
    </script>
</body>
</html>
"""

def render_login_page(mode='login', error=None, success=None):
    """Render the login/register page with optional error/success message."""
    from jinja2 import Template
    template = Template(LOGIN_TEMPLATE)
    return template.render(mode=mode, error=error, success=success)

def render_forgot_password_page(error=None, success=None):
    """Render the forgot password page."""
    from jinja2 import Template
    template = Template(FORGOT_PASSWORD_TEMPLATE)
    return template.render(error=error, success=success)

def render_reset_password_page(token, email, error=None, success=None):
    """Render the password reset page."""
    from jinja2 import Template
    template = Template(RESET_PASSWORD_TEMPLATE)
    return template.render(token=token, email=email, error=error, success=success)
