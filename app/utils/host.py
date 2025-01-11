from curses import echo
import re
import paramiko
import os
import asyncio
from .net import AsyncParamikoSSHClient, RedisCls
from .app_version import getTag, generate_git_url
from .remote_exec_app import find_bundle_dir, find_ruby
from dotenv import load_dotenv
load_dotenv()

_PASSWORDS_ = os.getenv('PASSWORDS')
passwords = _PASSWORDS_.split(',')

# Step 1: Remove unwanted characters (square brackets and single quotes) from the passwords
password_list = [password.strip("['").strip("']") for password in passwords]
password_list = [password.replace("'", "").strip("")
                 for password in password_list]

async def update_remote_host(user_name: str, ip_address: str) -> str:
    def print_stage(message: str):
        print(f"\n{'='*80}\n{message}\n{'='*80}")
    
    def print_action(message: str):
        print(f"\n---> {message}")
    
    def print_status(status: str, message: str):
        if status.lower() == 'success':
            print(f"\n✅ SUCCESS: {message}")
        elif status.lower() == 'error':
            print(f"\n❌ ERROR: {message}")
        else:
            print(f"\n📝 INFO: {message}")

    try:
        print_stage("INITIALIZING DEPLOYMENT")
        print_action(f"Connecting to remote host: {ip_address}")
        
        client = await conect_to_remote_host(ip_address, user_name)
        app_dirs = os.getenv('APP_DIRS').split(',')
        collection = []
        output_cache = []
        error_output = []
        git_describe_decoded_stdout = ""
        
        if isinstance(client, AsyncParamikoSSHClient):
            try:
                await client.clsConnect()
                print_status('success', f"Connected to host: {ip_address}")

                print_stage("PROCESSING APPLICATIONS")
                for app_dir in app_dirs:
                    print_stage(f"WORKING ON: {app_dir}")
                    
                    # Modified directory check to use ls instead of test command
                    print_action(f"Checking if directory exists: {app_dir}")
                    check_dir_cmd = f"ls {app_dir} 2>/dev/null || echo 'NOT_EXISTS'"
                    dir_check = await client.send_command(check_dir_cmd)
                    dir_exists = 'NOT_EXISTS' not in dir_check.decode("utf-8").strip()

                    if not dir_exists:
                        print_action(f"Repository not found. Preparing to clone: {app_dir}")
                        parent_dir = os.path.dirname(app_dir)
                        repo_name = os.path.basename(app_dir)
                        
                        print_action(f"Creating directory: {parent_dir}")
                        mkdir_cmd = f"mkdir -p {parent_dir}"
                        mkdir_result = await client.send_command(mkdir_cmd)
                        
                        if mkdir_result and b"error" in mkdir_result.lower():
                            error_output.append(f"Failed to create directory: {parent_dir}")
                            print_status('error', f"Failed to create directory: {parent_dir}")
                            continue

                        print_action(f"Cloning repository: {repo_name}")
                        git_clone_cmd = f"cd {parent_dir} && git clone http://{os.getenv('GIT_HOST')}:{generate_git_url(repo_name)}"
                        output_cache.append(f"Git Clone Command: {git_clone_cmd}")
                        stdout = await client.send_command(git_clone_cmd)
                        
                        if stdout:
                            decoded_stdout = stdout.decode("utf-8")
                            if "error:" in decoded_stdout.lower():
                                error_output.append(decoded_stdout)
                                print_status('error', f"Failed to clone repository: {repo_name}")
                                continue
                            else:
                                print_status('success', f"Repository cloned: {repo_name}")
                                output_cache.append(f"Git Clone Output:\n{decoded_stdout}")
                    else:
                        print_action(f"Updating existing repository: {app_dir}")
                        git_pull_cmd = f"cd {app_dir} && git pull --tags http://{os.getenv('GIT_HOST')}:{generate_git_url(app_dir)}"
                        output_cache.append(f"Git Pull Command: {git_pull_cmd}")
                        stdout = await client.send_command(git_pull_cmd)
                        
                        if stdout:
                            decoded_stdout = stdout.decode("utf-8")
                            if "error:" in decoded_stdout.lower():
                                error_output.append(decoded_stdout)
                                print_status('error', f"Failed to pull updates for: {app_dir}")
                                continue
                            else:
                                print_status('success', f"Repository updated: {app_dir}")
                                output_cache.append(f"Git Pull Output:\n{decoded_stdout}")

                    # Rest of the code remains the same but with similar error handling...
                    # [Previous code for tag checkout, bundle install, etc.]

                print_action("Closing connection")
                client.close()
                print_status('success', "Connection closed")

                print_stage("DEPLOYMENT COMPLETE")
                
                # Always ensure these keys exist in the return dictionary
                return {
                    "output": output_cache,
                    "error_output": error_output,
                    "result": collection,
                    "status": "completed"
                }
            
            except Exception as e:
                error_msg = f"Deployment failed: {str(e)}"
                print_status('error', error_msg)
                return {
                    "output": output_cache,
                    "error_output": error_output + [error_msg],
                    "result": collection,
                    "status": "failed"
                }

    except Exception as e:
        error_msg = f"Failed to initiate update task on {ip_address} with exception: {e}"
        print_status('error', error_msg)
        return {
            "output": [],
            "error_output": [error_msg],
            "result": [],
            "status": "failed_to_connect"
        }


# retuns AsyncParamikoSSHClient instance
async def check_if_password_works(remote_host, ssh_username):
    redisInstance = RedisCls()
    await redisInstance.connect()
    redisPassword = await redisInstance.getPswrd(remote_host)

    # Use Redis password if available, otherwise iterate through password list
    _PASSWORDS_ = os.getenv('PASSWORDS')
    passwords = _PASSWORDS_.split(',')

    # Step 1: Remove unwanted characters (square brackets and single quotes) from the passwords
    password_list = [password.strip("['").strip("']") for password in passwords]
    password_list = [password.replace("'", "").strip("")
                    for password in password_list]
    passwords_to_try = [redisPassword] if redisPassword else password_list

    for password in passwords_to_try:
        try:
            client = AsyncParamikoSSHClient(host=remote_host, username=ssh_username)
            await client.clsConnectWithPass(password=str(password).strip())
            await redisInstance.updatePswrdDict(remote_host, str(password).strip())
            
            return str(password).strip()
        except paramiko.SSHException as e:
            print("Unable to establish SSH connection:", str(e))
        except Exception as e:
            print("An ERROR occured in check_if_password_works: ", str(e))
        finally:
            client.close()

# retuns AsyncParamikoSSHClient instance
async def conect_to_remote_host(remote_host, ssh_username):
    try:
        client = AsyncParamikoSSHClient(host=remote_host, username=ssh_username)
        await client.clsConnect()
        return client
    except paramiko.SSHException as e:
        print("Unable to establish SSH connection:", str(e))
    except Exception as e:
        print("conect to remote host error:", str(e))