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
app.secret_key = 'your-secret-key-here'  # Change this to a secure random key

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Define GPIO pins
FAN_LOW_PIN = 18
FAN_MED_PIN = 23
FAN_HIGH_PIN = 24
COMPRESSOR_PIN = 25

# Setup GPIO outputs
GPIO.setup(FAN_LOW_PIN, GPIO.OUT)
GPIO.setup(FAN_MED_PIN, GPIO.OUT)
GPIO.setup(FAN_HIGH_PIN, GPIO.OUT)
GPIO.setup(COMPRESSOR_PIN, GPIO.OUT)

# Simple User class
class User(UserMixin):
    def __init__(self, id):
        self.id = id
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
        self.cycle_fan_speed = 'MED'
        self.cycle_mode = 'COOL'

    def turn_off_all_pins(self):
        GPIO.output(FAN_LOW_PIN, GPIO.LOW)
        GPIO.output(FAN_MED_PIN, GPIO.LOW)
        GPIO.output(FAN_HIGH_PIN, GPIO.LOW)
        GPIO.output(COMPRESSOR_PIN, GPIO.LOW)

    def set_fan_mode(self, speed):
        with self.operation_lock:
            self.turn_off_all_pins()
            if speed == 'LOW':
                GPIO.output(FAN_LOW_PIN, GPIO.HIGH)
            elif speed == 'MED':
                GPIO.output(FAN_MED_PIN, GPIO.HIGH)
            elif speed == 'HIGH':
                GPIO.output(FAN_HIGH_PIN, GPIO.HIGH)
            self.current_mode = f'FAN_{speed}'

    def set_cooling_mode(self, speed):
        with self.operation_lock:
            self.turn_off_all_pins()
            GPIO.output(COMPRESSOR_PIN, GPIO.HIGH)
            if speed == 'LOW':
                GPIO.output(FAN_LOW_PIN, GPIO.HIGH)
            elif speed == 'MED':
                GPIO.output(FAN_MED_PIN, GPIO.HIGH)
            elif speed == 'HIGH':
                GPIO.output(FAN_HIGH_PIN, GPIO.HIGH)
            self.current_mode = f'COOL_{speed}'

    def turn_off(self):
        with self.operation_lock:
            self.turn_off_all_pins()
            self.current_mode = 'OFF'

    def run_cycle(self):
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

    def start_cycle(self):
        if not self.is_running:
            self.is_running = True
            self.cycle_thread = threading.Thread(target=self.run_cycle)
            self.cycle_thread.start()

    def stop_cycle(self):
        self.is_running = False
        if self.cycle_thread:
            self.cycle_thread.join()
        self.turn_off()

    def set_cycle_settings(self, mode, speed):
        self.cycle_mode = mode
        self.cycle_fan_speed = speed
        logger.info(f"Cycle settings updated: {mode} mode at {speed} speed")

# Initialize AC Controller
ac = ACController()

# Routes
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

@app.route('/api/fan', methods=['POST'])
@login_required
def set_fan():
    try:
        data = request.get_json()
        speed = data.get('speed', 'LOW')
        ac.set_fan_mode(speed)
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode
        })
    except Exception as e:
        logger.error(f"Error setting fan mode: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cool', methods=['POST'])
@login_required
def set_cooling():
    try:
        data = request.get_json()
        speed = data.get('speed', 'LOW')
        ac.set_cooling_mode(speed)
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode
        })
    except Exception as e:
        logger.error(f"Error setting cooling mode: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/off', methods=['POST'])
@login_required
def turn_off():
    try:
        ac.turn_off()
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode
        })
    except Exception as e:
        logger.error(f"Error turning off: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cycle/start', methods=['POST'])
@login_required
def start_cycle():
    try:
        ac.start_cycle()
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode
        })
    except Exception as e:
        logger.error(f"Error starting cycle: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cycle/stop', methods=['POST'])
@login_required
def stop_cycle():
    try:
        ac.stop_cycle()
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode
        })
    except Exception as e:
        logger.error(f"Error stopping cycle: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
@login_required
def get_status():
    try:
        return jsonify({
            'current_mode': ac.current_mode,
            'is_running': ac.is_running,
            'schedule_enabled': ac.schedule_enabled,
            'cycle_mode': ac.cycle_mode,
            'cycle_fan_speed': ac.cycle_fan_speed,
            'start_time': str(ac.start_time) if ac.start_time else None,
            'end_time': str(ac.end_time) if ac.end_time else None
        })
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/schedule', methods=['POST'])
@login_required
def set_schedule():
    try:
        data = request.get_json()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        enabled = data.get('enabled', False)
        
        if start_time:
            ac.start_time = datetime.strptime(start_time, '%H:%M').time()
        if end_time:
            ac.end_time = datetime.strptime(end_time, '%H:%M').time()
            
        ac.schedule_enabled = enabled
        
        return jsonify({
            'status': 'success',
            'schedule_enabled': ac.schedule_enabled,
            'start_time': str(ac.start_time),
            'end_time': str(ac.end_time)
        })
    except Exception as e:
        logger.error(f"Error setting schedule: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        GPIO.cleanup()
