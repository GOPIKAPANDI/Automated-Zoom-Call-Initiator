import subprocess
import time
import requests

def execute_remote_command_with_psexec(host, username, password, command, timeout=60):
    psexec_command = [
        "psexec", "-i", "1", f"\\\\{host}", "-u", username, "-p", password, "cmd.exe", "/c", command
    ]
    print(f"Executing command on {host}: {' '.join(psexec_command)}")  # Debug information
    try:
        result = subprocess.run(psexec_command, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        print(f"Timeout occurred while executing command on {host}")
        return "", f"Timeout occurred after {timeout} seconds", -1

def call_http_endpoint(host):
    url = f"http://{host}:8000/runYoutube/joinZoomCall"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Successfully called HTTP endpoint on {host}: {response.json()}")
            return True
        else:
            print(f"Failed to call HTTP endpoint on {host}: Status Code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Error calling HTTP endpoint on {host}: {str(e)}")
        return False

def main():
    hosts = [
        {"hostname": "ip_addr", "username": "username", "password": "pw"},
        {"hostname": "ip_addr", "username": "username", "password": "pw"},
	{"hostname": "ip_addr", "username": "username", "password": "pw"}

    ]

    # Command to execute the Python script on the remote machine
    python_command = "python C:\\SCRIPTS\\client.py"

    for host in hosts:
        print(f"\nAttempting to execute on {host['hostname']}:")
        start_time = time.time()
        output, error, returncode = execute_remote_command_with_psexec(
            host["hostname"], host["username"], host["password"], python_command
        )
        end_time = time.time()

        print(f"Execution time for {host['hostname']}: {end_time - start_time:.2f} seconds")

        if output:
            print(f"Output from {host['hostname']}:\n{output}")
        if error:
            print(f"Error from {host['hostname']}:\n{error}")

        if returncode != 0:
            print(f"PsExec failed on {host['hostname']}, attempting to call HTTP endpoint...")
            if not call_http_endpoint(host["hostname"]):
                print(f"Failed to call HTTP endpoint on {host['hostname']}.")

        print(f"Finished processing {host['hostname']}")

if __name__ == "__main__":
    main()
