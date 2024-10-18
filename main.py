from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import RPi.GPIO as GPIO
import threading
import time
from datetime import datetime, time as dtime
import logging
import os
from werkzeug.security import generate_password_hash, check_password_hash

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)
app.secret_key = '9e5181fbf05a858e6ce4351da2d32215e1fa2a4ecf086144'  # Change this to a secure random key

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class
class User(UserMixin):
    def __init__(self, id):
        self.id = id
        # Change this to your desired username and password
        self.username = "root"
        self.password_hash = generate_password_hash("root")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Single user instance
user = User(1)

@login_manager.user_loader
def load_user(user_id):
    if int(user_id) == 1:
        return user
    return None

# [Keep your existing GPIO setup and pin definitions]

class ACController:
    def __init__(self):
        self.current_mode = 'OFF'
        self.is_running = False
        self.cycle_thread = None
        self.schedule_thread = None
        self.operation_lock = threading.Lock()
        self.last_operation_time = 0
        self.start_time = None
        self.end_time = None
        self.schedule_enabled = False
        self.cycle_fan_speed = 'MED'  # Default cycle fan speed
        self.cycle_mode = 'COOL'      # Default cycle mode (COOL or FAN)

    # [Keep your existing methods]

    def run_cycle(self):
        """Run 30-minute on, 30-minute off cycle with configurable fan speed"""
        while self.is_running:
            logger.info(f"Starting cycle with {self.cycle_mode} mode at {self.cycle_fan_speed} speed")
            if self.cycle_mode == 'COOL':
                self.set_cooling_mode(self.cycle_fan_speed)
            else:
                self.set_fan_mode(self.cycle_fan_speed)
            time.sleep(1800)  # 30 minutes
            
            if self.is_running:
                logger.info("Starting rest cycle")
                self.turn_off()
                time.sleep(1800)  # 30 minutes

    def set_cycle_settings(self, mode, speed):
        """Set the mode and fan speed for the cycle"""
        self.cycle_mode = mode
        self.cycle_fan_speed = speed
        logger.info(f"Cycle settings updated: {mode} mode at {speed} speed")

# Initialize AC Controller
ac = ACController()

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == user.username and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Protected routes
@app.route('/')
@login_required
def home():
    try:
        return render_template('index.html', 
                             current_mode=ac.current_mode,
                             start_time=ac.start_time or "20:00",
                             end_time=ac.end_time or "06:00",
                             schedule_enabled=ac.schedule_enabled,
                             cycle_mode=ac.cycle_mode,
                             cycle_fan_speed=ac.cycle_fan_speed)
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        return f"Error loading page: {str(e)}", 500

# Add new route for cycle settings
@app.route('/api/cycle/settings', methods=['POST'])
@login_required
def set_cycle_settings():
    try:
        data = request.get_json()
        mode = data.get('mode', 'COOL')
        speed = data.get('speed', 'MED')
        ac.set_cycle_settings(mode, speed)
        return jsonify({
            'status': 'success',
            'cycle_mode': ac.cycle_mode,
            'cycle_fan_speed': ac.cycle_fan_speed
        })
    except Exception as e:
        logger.error(f"Error setting cycle settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add @login_required to all existing API routes
@app.route('/api/fan', methods=['POST'])
@login_required
def set_fan():
    # [Keep existing implementation]

@app.route('/api/cool', methods=['POST'])
@login_required
def set_cooling():
    # [Keep existing implementation]

@app.route('/api/off', methods=['POST'])
@login_required
def turn_off():
    # [Keep existing implementation]

@app.route('/api/cycle/start', methods=['POST'])
@login_required
def start_cycle():
    # [Keep existing implementation]

@app.route('/api/cycle/stop', methods=['POST'])
@login_required
def stop_cycle():
    # [Keep existing implementation]

@app.route('/api/status', methods=['GET'])
@login_required
def get_status():
    # [Keep existing implementation]

@app.route('/api/schedule', methods=['POST'])
@login_required
def set_schedule():
    # [Keep existing implementation]

# [Keep your main block]
