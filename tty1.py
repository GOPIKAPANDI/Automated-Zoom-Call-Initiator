import requests
import webbrowser
import subprocess
import time
import os
 
def close_edge():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], 
                       check=True, 
                       stdout=subprocess.DEVNULL, 
                       stderr=subprocess.DEVNULL)
        print("Microsoft Edge closed successfully.")
    except subprocess.CalledProcessError:
        print("Microsoft Edge was not running or couldn't be closed.")
    time.sleep(2)
 
def join_meeting(meeting_url, wait_time=5):  # Default wait time is 180 seconds (3 minutes)
    close_edge()
    print(f'Joining meeting at: {meeting_url}')
    
    edge_path = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    if os.path.exists(edge_path):
        webbrowser.register('edge', None, webbrowser.BackgroundBrowser(edge_path))
        webbrowser.get('edge').open(meeting_url)
    else:
        print("Microsoft Edge not found. Opening in default browser.")
        webbrowser.open(meeting_url)
    print(f"Waiting for {wait_time} seconds before closing the browser...")
    time.sleep(wait_time)
    print("Closing the browser...")
    close_edge()
 
def get_meeting_url_from_server():
    server_ip = '10.74.140.49'
    response = requests.get(f'http://{server_ip}:5000/get_meeting_url', timeout=10)
    response.raise_for_status()
    data = response.json()
      
 
if __name__ == '__main__':
    meeting_url = get_meeting_url_from_server()
    if meeting_url:
        join_meeting(meeting_url)  # Use default 3 minutes wait time
        # Or specify a custom wait time in seconds:
        # join_meeting(meeting_url, wait_time=120)  # Wait for 2 minutes
    else:
        print('Failed to retrieve meeting URL')
