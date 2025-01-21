from flask import Flask, redirect, request, session, url_for, jsonify
import requests
import base64
import json
import socket
import webbrowser
import csv
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
from datetime import datetime

# 10.174.121.38

app = Flask(__name__)
app.secret_key = 'd9ee4ffef7b85c9a3099d755298dffb8e'

# Zoom OAuth configuration
CLIENT_ID = 'LHWCUVSaS0OLfvP6XS24HA'
CLIENT_SECRET = 'Fvl6MJ7f7zJSljWBS3368QNGQgSyvMNP'
REDIRECT_URI = 'http://localhost:5000/oauth/callback'

# OAuth URLs and scopes
SCOPES = 'dashboard:read:admin meeting:write meeting:read user:read dashboard_meetings:read:master dashboard:read:master dashboard:read:meeting_quality_score:master'
AUTH_URL = (f'https://zoom.us/oauth/authorize?response_type=code&client_id={CLIENT_ID}'
            f'&redirect_uri={REDIRECT_URI}&scope={SCOPES}')
TOKEN_URL = 'https://zoom.us/oauth/token'
MEETING_URL = 'https://api.zoom.us/v2/users/me/meetings'
MEETING_DETAILS_URL = 'https://api.zoom.us/v2/metrics/meetings/{}'
PARTICIPANTS_URL_TEMPLATE = 'https://api.zoom.us/v2/metrics/meetings/{}/participants'
QOS_URL_TEMPLATE = 'https://api.zoom.us/v2/metrics/meetings/{}/participants/{}/qos?type=live'

join_url = None  # Store the join URL globally
meeting_id = None  # Store the meeting ID globally
access_token = None  # Store the access token globally
csv_folder_path = None  # Store the CSV folder path
refresh_token = None

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        return response.json()['ip']
    except requests.exceptions.RequestException as e:
        return f"Error fetching public IP: {e}"

def get_local_ip():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except socket.error as e:
        return f"Error fetching local IP: {e}"

def fetch_meeting_details(access_token, meeting_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(MEETING_DETAILS_URL.format(meeting_id), headers=headers, params={'type': 'live'})
    if response.status_code == 200:
        return response.json()
    return None

def fetch_participants(access_token, meeting_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(PARTICIPANTS_URL_TEMPLATE.format(meeting_id), headers=headers, params={'type': 'live'})
    if response.status_code == 200:
        return response.json()
    return None

def fetch_qos_data(access_token, meeting_id, participant_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(QOS_URL_TEMPLATE.format(meeting_id, participant_id), headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def write_to_csv(file_path, data_list, fieldnames):
    try:
        with open(file_path, 'w', newline='') as csvfile:  # Open file in write mode to overwrite data
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for data in data_list:
                writer.writerow(data)
    except PermissionError as e:
        print(f"Permission error: {e}")
    except ValueError as e:
        print(f"Value error: {e}")

@app.route('/')
def home():
    return 'Welcome to the Zoom Meeting Creator! <a href="/login">Login with Zoom</a>'

@app.route('/login')
def login():
    return redirect(AUTH_URL)

@app.route('/oauth/callback')
def oauth_callback():
    global access_token, refresh_token
    code = request.args.get('code')
    if not code:
        return "Authorization code not found in the request."

    auth_header = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    token_headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        token_response = requests.post(TOKEN_URL, data=token_data, headers=token_headers)
        token_response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        return f"HTTP error during token request: {err}"

    token_json = token_response.json()
    if 'access_token' not in token_json:
        return f"Error: {token_json.get('reason', 'Unknown error')}"
    
    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(
        func=request_access_token,
        trigger=IntervalTrigger(minutes=60),
        id='Requesting access token',
        name='Fetch access token every hour',
        replace_existing=True)
    atexit.register(lambda: scheduler.shutdown())

    access_token = token_json['access_token']
    refresh_token = token_json['refresh_token']
    session['access_token'] = access_token
    return redirect(url_for('create_meeting'))

@app.route('/create_meeting')
def create_meeting():
    global join_url, meeting_id, csv_folder_path
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    test_name = datetime.now().strftime('%d_%b_%H%M')
    csv_folder_path = os.path.join('data', test_name)
    if not os.path.exists(csv_folder_path):
        os.makedirs(csv_folder_path)

    meeting_headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    meeting_data = {
        'topic': 'Test Meeting',
        'type': 1,  # Instant meeting
        'settings': {
            'host_video': True,
            'participant_video': True,
            'join_before_host': True,
            'waiting_room': False,  # Disable waiting room
            'mute_upon_entry': False
        }
    }

    try:
        meeting_response = requests.post(MEETING_URL, headers=meeting_headers, json=meeting_data)
        meeting_response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        return f"HTTP error during meeting creation: {err}"

    meeting_json = meeting_response.json()
    join_url = meeting_json['join_url']
    print(join_url)
    meeting_id = meeting_json['id']
    webbrowser.open(join_url)

    scheduler = BackgroundScheduler()
    scheduler.start()
    scheduler.add_job(
        func=fetch_and_log_meeting_data,
        trigger=IntervalTrigger(minutes=1),
        id='meeting_data_fetch_job',
        name='Fetch meeting data every minute',
        replace_existing=True)
    atexit.register(lambda: scheduler.shutdown())

    return f"Meeting created successfully! Join URL: {join_url}"

def request_access_token():
    print("Requesting access token...................")
    global refresh_token, access_token
    auth_header = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
    token_headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    try:
        token_response = requests.post(TOKEN_URL, data=token_data, headers=token_headers)
        token_response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error during token request: {err}")

    token_json = token_response.json()
    if 'access_token' not in token_json:
        print(f"Error: {token_json.get('reason', 'Unknown error')}")

    access_token = token_json['access_token']
    refresh_token = token_json['refresh_token']

@app.route('/get_meeting_url')
def get_meeting_url():
    if join_url:
        return jsonify({'join_url': join_url})
    else:
        return jsonify({'error': 'No meeting URL available'}), 404

@app.route('/dashboard_data')
def dashboard_data():
    return "Dashboard data fetch scheduled."

def fetch_and_log_meeting_data():
    global access_token, meeting_id
    if not access_token or not meeting_id:
        print("Access token or meeting ID not found.")
        return

    # try:
    meeting_details = fetch_meeting_details(access_token, meeting_id)
    if meeting_details:
        print("Meeting Details:", json.dumps(meeting_details, indent=2))
        meeting_details['date_time'] = datetime.now().isoformat()
        meeting_fieldnames = ['uuid', 'id', 'topic', 'host', 'email', 'user_type', 'start_time', 'end_time', 'duration', 'participants', 'has_pstn', 'has_archiving', 'has_voip', 'has_3rd_party_audio', 'has_video', 'has_screen_share', 'has_recording', 'has_sip', 'dept', 'has_manual_captions', 'has_automated_captions', 'date_time']
        write_to_csv(os.path.join(csv_folder_path, 'meeting_details.csv'), [meeting_details], meeting_fieldnames)

    participants_data = fetch_participants(access_token, meeting_id)
    if participants_data:
        print("Participants Data:", json.dumps(participants_data, indent=2))
        participants_list = []
        participant_fieldnames = ['id', 'user_id', 'participant_uuid', 'user_name', 'device', 'ip_address', 'internal_ip_addresses', 'location', 'network_type', 'microphone', 'speaker', 'camera', 'data_center', 'full_data_center', 'connection_type', 'join_time', 'leave_time', 'leave_reason', 'share_application', 'share_desktop', 'share_whiteboard', 'recording', 'pc_name', 'domain', 'mac_addr', 'harddisk_id', 'version', 'email', 'registrant_id', 'status', 'os', 'os_version', 'device_name', 'customer_key', 'sip_uri', 'from_sip_uri', 'role', 'participant_user_id', 'audio_call', 'date_time', 'meeting_id' ,'groupId']
        for participant in participants_data.get('participants', []):
            participant['date_time'] = datetime.now().isoformat()
            participant['meeting_id'] = meeting_id
            participants_list.append(participant)
        write_to_csv(os.path.join(csv_folder_path, 'client_details.csv'), participants_list, participant_fieldnames)

        qos_list = []
        qos_fieldnames = ['date_time', 'meeting_id', 'user_id', 'audio_input_bitrate', 'audio_input_latency', 'audio_input_jitter', 'audio_input_avg_loss', 'audio_input_max_loss', 'audio_output_bitrate', 'audio_output_latency', 'audio_output_jitter', 'audio_output_avg_loss', 'audio_output_max_loss', 'video_input_bitrate', 'video_input_latency', 'video_input_jitter', 'video_input_avg_loss', 'video_input_max_loss', 'video_input_resolution', 'video_input_frame_rate', 'video_output_bitrate', 'video_output_latency', 'video_output_jitter', 'video_output_avg_loss', 'video_output_max_loss', 'video_output_resolution', 'video_output_frame_rate', 'cpu_usage_zoom_min', 'cpu_usage_zoom_avg', 'cpu_usage_zoom_max', 'cpu_usage_system_max', 'wifi_rssi_max', 'wifi_rssi_avg', 'wifi_rssi_min']
        for participant in participants_data.get('participants', []):
            participant_id = participant.get('user_id')
            if participant_id:
                qos_data = fetch_qos_data(access_token, meeting_id, participant_id)
                if qos_data:
                    for qos_entry in qos_data.get('user_qos', []):
                        flattened_qos_entry = {
                            'date_time': qos_entry['date_time'],
                            'meeting_id': meeting_id,
                            'user_id': participant_id,
                            'audio_input_bitrate': qos_entry['audio_input'].get('bitrate'),
                            'audio_input_latency': qos_entry['audio_input'].get('latency'),
                            'audio_input_jitter': qos_entry['audio_input'].get('jitter'),
                            'audio_input_avg_loss': qos_entry['audio_input'].get('avg_loss'),
                            'audio_input_max_loss': qos_entry['audio_input'].get('max_loss'),
                            'audio_output_bitrate': qos_entry['audio_output'].get('bitrate'),
                            'audio_output_latency': qos_entry['audio_output'].get('latency'),
                            'audio_output_jitter': qos_entry['audio_output'].get('jitter'),
                            'audio_output_avg_loss': qos_entry['audio_output'].get('avg_loss'),
                            'audio_output_max_loss': qos_entry['audio_output'].get('max_loss'),
                            'video_input_bitrate': qos_entry['video_input'].get('bitrate'),
                            'video_input_latency': qos_entry['video_input'].get('latency'),
                            'video_input_jitter': qos_entry['video_input'].get('jitter'),
                            'video_input_avg_loss': qos_entry['video_input'].get('avg_loss'),
                            'video_input_max_loss': qos_entry['video_input'].get('max_loss'),
                            'video_input_resolution': qos_entry['video_input'].get('resolution'),
                            'video_input_frame_rate': qos_entry['video_input'].get('frame_rate'),
                            'video_output_bitrate': qos_entry['video_output'].get('bitrate'),
                            'video_output_latency': qos_entry['video_output'].get('latency'),
                            'video_output_jitter': qos_entry['video_output'].get('jitter'),
                            'video_output_avg_loss': qos_entry['video_output'].get('avg_loss'),
                            'video_output_max_loss': qos_entry['video_output'].get('max_loss'),
                            'video_output_resolution': qos_entry['video_output'].get('resolution'),
                            'video_output_frame_rate': qos_entry['video_output'].get('frame_rate'),
                            'cpu_usage_zoom_min': qos_entry['cpu_usage'].get('zoom_min_cpu_usage'),
                            'cpu_usage_zoom_avg': qos_entry['cpu_usage'].get('zoom_avg_cpu_usage'),
                            'cpu_usage_zoom_max': qos_entry['cpu_usage'].get('zoom_max_cpu_usage'),
                            'cpu_usage_system_max': qos_entry['cpu_usage'].get('system_max_cpu_usage'),
                            'wifi_rssi_max': qos_entry['wifi_rssi'].get('max_rssi'),
                            'wifi_rssi_avg': qos_entry['wifi_rssi'].get('avg_rssi'),
                            'wifi_rssi_min': qos_entry['wifi_rssi'].get('min_rssi')
                        }
                        qos_list.append(flattened_qos_entry)
        write_to_csv(os.path.join(csv_folder_path, 'client_qos.csv'), qos_list, qos_fieldnames)

    # except Exception as e:
    #     print(f"Error fetching or logging data: {e}")

if __name__:
    local_ip = get_local_ip()
    print(f"Starting Flask app on {local_ip}:5000")
    print(f"Please visit the following URL to authorize the application:")
    print(f"https://zoom.us/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}")
    app.run(debug=True, host='0.0.0.0', port=5000)