from flask import Flask, render_template, jsonify, request
import RPi.GPIO as GPIO
import threading
import time
from datetime import datetime, time as dtime
import logging
import os

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)
app.debug = True

# GPIO Setup
GPIO.setmode(GPIO.BCM)

# Pin Definitions
FAN_LOW = 4
FAN_MED = 17
FAN_HIGH = 22
COMPRESSOR = 18

# Setup pins as outputs
pins = [FAN_LOW, FAN_MED, FAN_HIGH, COMPRESSOR]
for pin in pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

class ACController:
    def __init__(self):
        self.current_mode = 'OFF'
        self.is_running = False
        self.cycle_thread = None
        self.schedule_thread = None
        self.operation_lock = threading.Lock()
        self.last_operation_time = 0
        self.start_time = None  # Format: "HH:MM"
        self.end_time = None    # Format: "HH:MM"
        self.schedule_enabled = False

    def safe_delay(self):
        """Enforce a 3-second delay between operations"""
        current_time = time.time()
        time_since_last = current_time - self.last_operation_time
        if time_since_last < 3:
            time.sleep(3 - time_since_last)
        self.last_operation_time = time.time()

    def turn_off_all(self):
        """Turn off all pins"""
        for pin in pins:
            GPIO.output(pin, GPIO.LOW)
        time.sleep(0.5)  # Short delay after turning everything off

    def set_fan_mode(self, mode):
        """Set fan mode without compressor"""
        with self.operation_lock:
            self.safe_delay()
            self.turn_off_all()
            
            if mode == 'LOW':
                GPIO.output(FAN_LOW, GPIO.HIGH)
            elif mode == 'MED':
                GPIO.output(FAN_MED, GPIO.HIGH)
            elif mode == 'HIGH':
                GPIO.output(FAN_HIGH, GPIO.HIGH)
            
            self.current_mode = f'FAN_{mode}'
            logger.info(f"Fan mode set to {mode}")

    def set_cooling_mode(self, mode):
        """Set cooling mode with fan and compressor"""
        with self.operation_lock:
            self.safe_delay()
            self.turn_off_all()
            
            # Set fan first
            if mode == 'LOW':
                GPIO.output(FAN_LOW, GPIO.HIGH)
            elif mode == 'MED':
                GPIO.output(FAN_MED, GPIO.HIGH)
            elif mode == 'HIGH':
                GPIO.output(FAN_HIGH, GPIO.HIGH)
            
            # Wait 2 seconds before activating compressor
            time.sleep(2)
            GPIO.output(COMPRESSOR, GPIO.HIGH)
            
            self.current_mode = f'COOL_{mode}'
            logger.info(f"Cooling mode set to {mode}")

    def turn_off(self):
        """Turn off the AC system"""
        with self.operation_lock:
            self.safe_delay()
            # Turn off compressor first
            GPIO.output(COMPRESSOR, GPIO.LOW)
            time.sleep(2)
            
            # Turn off all fans
            for pin in [FAN_LOW, FAN_MED, FAN_HIGH]:
                GPIO.output(pin, GPIO.LOW)
            
            self.current_mode = 'OFF'
            logger.info("AC system turned off")

    def run_cycle(self):
        """Run 30-minute on, 30-minute off cycle"""
        while self.is_running:
            logger.info("Starting cooling cycle")
            self.set_cooling_mode('MED')
            time.sleep(1800)  # 30 minutes
            
            if self.is_running:
                logger.info("Starting rest cycle")
                self.turn_off()
                time.sleep(1800)  # 30 minutes

    def start_cycle(self):
        """Start the cooling cycle"""
        if not self.is_running:
            self.is_running = True
            self.cycle_thread = threading.Thread(target=self.run_cycle)
            self.cycle_thread.start()
            logger.info("Cooling cycle started")

    def stop_cycle(self):
        """Stop the cooling cycle"""
        self.is_running = False
        if self.cycle_thread:
            self.cycle_thread.join()
        self.turn_off()
        logger.info("Cooling cycle stopped")

    def check_schedule(self):
        """Check if AC should be running based on schedule"""
        if not self.schedule_enabled or not self.start_time or not self.end_time:
            return False

        current_time = datetime.now().time()
        start = datetime.strptime(self.start_time, "%H:%M").time()
        end = datetime.strptime(self.end_time, "%H:%M").time()

        if start <= end:
            return start <= current_time <= end
        else:  # Handles overnight schedules
            return current_time >= start or current_time <= end

    def run_scheduler(self):
        """Run the scheduler"""
        while True:
            if self.schedule_enabled:
                should_run = self.check_schedule()
                if should_run and not self.is_running:
                    self.start_cycle()
                elif not should_run and self.is_running:
                    self.stop_cycle()
            time.sleep(60)  # Check every minute

    def start_scheduler(self):
        """Start the schedule thread"""
        self.schedule_thread = threading.Thread(target=self.run_scheduler)
        self.schedule_thread.daemon = True
        self.schedule_thread.start()
        logger.info("Scheduler started")

# Initialize AC Controller
ac = ACController()

@app.route('/')
def home():
    try:
        return render_template('index.html', 
                             current_mode=ac.current_mode,
                             start_time=ac.start_time or "20:00",
                             end_time=ac.end_time or "06:00",
                             schedule_enabled=ac.schedule_enabled)
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        return f"Error loading page: {str(e)}", 500

@app.route('/api/fan', methods=['POST'])
def set_fan():
    try:
        speed = request.form.get('speed')
        ac.set_fan_mode(speed)
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode,
            'cycle_status': 'Running' if ac.is_running else 'Stopped'
        })
    except Exception as e:
        logger.error(f"Error setting fan mode: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cool', methods=['POST'])
def set_cooling():
    try:
        speed = request.form.get('speed')
        ac.set_cooling_mode(speed)
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode,
            'cycle_status': 'Running' if ac.is_running else 'Stopped'
        })
    except Exception as e:
        logger.error(f"Error setting cooling mode: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/off', methods=['POST'])
def turn_off():
    try:
        ac.turn_off()
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode,
            'cycle_status': 'Stopped'
        })
    except Exception as e:
        logger.error(f"Error turning off: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cycle/start', methods=['POST'])
def start_cycle():
    try:
        ac.start_cycle()
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode,
            'cycle_status': 'Running'
        })
    except Exception as e:
        logger.error(f"Error starting cycle: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cycle/stop', methods=['POST'])
def stop_cycle():
    try:
        ac.stop_cycle()
        return jsonify({
            'status': 'success',
            'current_mode': ac.current_mode,
            'cycle_status': 'Stopped'
        })
    except Exception as e:
        logger.error(f"Error stopping cycle: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    try:
        return jsonify({
            'current_mode': ac.current_mode,
            'cycle_status': 'Running' if ac.is_running else 'Stopped',
            'schedule_enabled': ac.schedule_enabled,
            'start_time': ac.start_time,
            'end_time': ac.end_time
        })
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/schedule', methods=['POST'])
def set_schedule():
    try:
        data = request.get_json()
        ac.start_time = data.get('start_time')
        ac.end_time = data.get('end_time')
        ac.schedule_enabled = data.get('enabled', False)
        return jsonify({
            'status': 'success',
            'schedule_enabled': ac.schedule_enabled,
            'start_time': ac.start_time,
            'end_time': ac.end_time
        })
    except Exception as e:
        logger.error(f"Error in schedule API: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        logger.info("Starting AC Control System")
        ac.start_scheduler()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Error starting application: {str(e)}")
    finally:
        GPIO.cleanup()
