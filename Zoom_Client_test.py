import subprocess
import time
import wmi
import paramiko
import winrm
from winrm.protocol import Protocol

def execute_remote_command_with_psexec(host, username, password, command, timeout=60):
    psexec_command = [
        "psexec", "-i", "1", f"\\\\{host}", "-u", username, "-p", password, "cmd.exe", "/c", command
    ]
    print(f"Executing command on {host} with PsExec: {' '.join(psexec_command)}")
    try:
        result = subprocess.run(psexec_command, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"Timeout occurred while executing command on {host} with PsExec")
        return 1, "", f"Timeout occurred after {timeout} seconds"

def execute_remote_command_with_wmi(host, username, password, command):
    try:
        c = wmi.WMI(server=host, user=username, password=password)
        process = c.Win32_Process.Create(CommandLine=command)
        if process:
            return 0, f"Process created with ID {process[0]}", ""
        else:
            return 1, "", "Failed to create process"
    except Exception as e:
        return 1, "", str(e)

def execute_remote_command_with_scheduled_task(host, username, password, command):
    task_name = "RemoteCommandTask"
    create_task = f"schtasks /create /tn {task_name} /tr \"{command}\" /sc once /st 00:00 /f"
    run_task = f"schtasks /run /tn {task_name}"
    delete_task = f"schtasks /delete /tn {task_name} /f"
    try:
        subprocess.run(create_task, shell=True, check=True)
        subprocess.run(run_task, shell=True, check=True)
        return 0, "Task executed successfully", ""
    except subprocess.CalledProcessError as e:
        return 1, "", str(e)
    finally:
        subprocess.run(delete_task, shell=True, check=True)

def run_command_via_ssh(ip, command, username, password):
    """Execute a command on a remote machine using SSH with Paramiko."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password)
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout_data = stdout.read().decode()
        stderr_data = stderr.read().decode()
        ssh.close()
        if stdout.channel.recv_exit_status() == 0:
            return 0, stdout_data, stderr_data
        else:
            return 1, stdout_data, stderr_data
    except Exception as e:
        return 1, "", str(e)

def execute_remote_command_with_winrm(host, username, password, command):
    try:
        protocol = Protocol(
            endpoint=f'http://{host}:5985/wsman',
            transport='ntlm',
            username=username,
            password=password
        )
        session = winrm.Session(host, auth=(username, password), transport='ntlm')
        result = session.run_cmd(command)
        return result.status_code, result.std_out.decode(), result.std_err.decode()
    except Exception as e:
        return 1, "", str(e)

def execute_remote_command_with_dcom(host, username, password, command):
    # This is a placeholder as DCOM setup is more complex and usually requires specific configuration
    # You might use pywinrm for similar functionality if not using native DCOM
    return 1, "", "DCOM not implemented"

def execute_remote_command(host, username, password, command):
    methods = [
        execute_remote_command_with_psexec,
        execute_remote_command_with_wmi,
        execute_remote_command_with_scheduled_task,
        run_command_via_ssh,
        execute_remote_command_with_winrm,
        execute_remote_command_with_dcom
    ]
    
    for method in methods:
        returncode, output, error = method(host, username, password, command)
        if returncode == 0:
            return output, error
        print(f"Method {method.__name__} failed with error:\n{error}")
    
    return "", "All methods failed"

def main():
    hosts = [
        {"hostname": "10.74.143.44", "username": "it", "password": "ruckus"}
    ]

    # Command to execute the Python script on the remote machine
    python_command = "python C:\\SCRIPTS\\client.py"

    for host in hosts:
        print(f"\nAttempting to execute on {host['hostname']}:")
        start_time = time.time()
        output, error = execute_remote_command(
            host["hostname"], host["username"], host["password"], python_command
        )
        end_time = time.time()

        print(f"Execution time for {host['hostname']}: {end_time - start_time:.2f} seconds")

        if output:
            print(f"Output from {host['hostname']}:\n{output}")
        if error:
            print(f"Error from {host['hostname']}:\n{error}")

        print(f"Finished processing {host['hostname']}")

if __name__ == "__main__":
    main()
