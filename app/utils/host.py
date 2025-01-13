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
                print("##########################################")
                print(f"Connect status: {client.is_connected()}")
                print("##########################################")
                if client.is_connected() == False:
                    client.close()
                    return 
                
                print_status('success', f"Connected to host: {ip_address}")

                print_stage("PROCESSING APPLICATIONS")
                for app_dir in app_dirs:
                    print_stage(f"WORKING ON: {app_dir}")
                    
                    # Check if directory exists
                    print_action(f"Checking if directory exists: {app_dir}")
                    check_dir_cmd = f"[ -d {app_dir} ] && echo 'EXISTS' || echo 'NOT_EXISTS'"
                    dir_status = await client.send_command(check_dir_cmd)
                    dir_status = dir_status.decode("utf-8").strip()

                    if dir_status == 'NOT_EXISTS':
                        print_action(f"Repository not found. Preparing to clone: {app_dir}")
                        parent_dir = os.path.dirname(app_dir)
                        repo_name = os.path.basename(app_dir)
                        
                        print_action(f"Creating directory: {parent_dir}")
                        mkdir_cmd = f"mkdir -p {parent_dir}"
                        await client.send_command(mkdir_cmd)
                        
                        print_action(f"Cloning repository: {repo_name}")
                        git_clone_cmd = f"cd {parent_dir} && git clone http://{os.getenv('GIT_HOST')}:{generate_git_url(repo_name)}"
                        output_cache.append(f"Git Clone Command: {git_clone_cmd}")
                        stdout = await client.send_command(git_clone_cmd)
                        try:
                            if "ERRor:" in stdout:
                                error_output.append(stdout)
                                print_status('error', f"Failed to clone repository: {repo_name}")
                            else:
                                print_status('success', f"Repository cloned: {repo_name}")
                        except Exception as e:
                            decoded_stdout = stdout.decode("utf-8")
                            output_cache.append(f"Git Clone Output:\n{decoded_stdout}")
                    else:
                        print_action(f"Updating existing repository: {app_dir}")
                        git_pull_cmd = f"cd {app_dir} && git pull --tags http://{os.getenv('GIT_HOST')}:{generate_git_url(app_dir)}"
                        output_cache.append(f"Git Pull Command: {git_pull_cmd}")
                        stdout = await client.send_command(git_pull_cmd)
                        try:
                            if "ERRor:" in stdout:
                                error_output.append(stdout)
                                print_status('error', f"Failed to pull updates for: {app_dir}")
                            else:
                                print_status('success', f"Repository updated: {app_dir}")
                        except Exception as e:
                            decoded_stdout = stdout.decode("utf-8")
                            output_cache.append(f"Git Pull Output:\n{decoded_stdout}")

                    tag = getTag(app_dir=app_dir)
                    if tag:
                        print_action(f"Checking out tag: {tag}")
                        git_checkout_cmd = f"cd {app_dir} && git checkout {tag} -f"
                        output_cache.append(f"Git Checkout Command: {git_checkout_cmd}")
                        stdout = await client.send_command(git_checkout_cmd)
                        try:
                            if "ERRor:" in stdout:
                                error_output.append(stdout)
                                print_status('error', f"Failed to checkout tag: {tag}")
                            else:
                                print_status('success', f"Checked out tag: {tag}")
                        except Exception as e:
                            decoded_stdout = stdout.decode("utf-8")
                            output_cache.append(f"Git Checkout Output:\n{decoded_stdout}")

                        print_action("Updating HEAD reference")
                        git_describe_cmd = f"cd {app_dir} && git describe > HEAD"
                        stdout = await client.send_command(git_describe_cmd)
                        try:
                            if "ERRor:" in stdout:
                                error_output.append(stdout)
                                print_status('error', "Failed to update HEAD reference")
                        except Exception as e:
                            decoded_stdout = stdout.decode("utf-8")
                            output_cache.append(f"Git Describe write to head Output:\n{decoded_stdout}")

                        print_action("Getting current version")
                        git_describe_cmd = f"cd {app_dir} && git describe"
                        stdout = await client.send_command(git_describe_cmd)
                        try:
                            if "ERRor:" in stdout:
                                error_output.append(stdout)
                                print_status('error', "Failed to get current version")
                            else:
                                git_describe_decoded_stdout = stdout.decode("utf-8")
                                print_status('success', f"Current version: {git_describe_decoded_stdout.strip()}")
                        except Exception as e:
                            git_describe_decoded_stdout = stdout.decode("utf-8")
                            output_cache.append(f"Git Describe Output:\n{git_describe_decoded_stdout}")

                        if git_describe_decoded_stdout:
                            collection.append(git_describe_decoded_stdout.strip())

                        if "BHT-EMR-API" in app_dir:
                            print_stage("SETTING UP BHT-EMR-API")
                            
                            print_action("Installing bundle dependencies")
                            bundle_dirs = await find_bundle_dir(client=client)
                            for bundle_path in bundle_dirs:
                                print_action(f"Trying bundle installation with: {bundle_path}")
                                bundle_install_cmd = f"cd {app_dir} && {bundle_path} install --local"
                                stdout = await client.send_command(bundle_install_cmd)
                                try:
                                    if "ERRor:" in stdout:
                                        error_output.append(stdout)
                                        print_status('error', f"Bundle installation failed with: {bundle_path}")
                                    else:
                                        print_status('success', f"Bundle installation completed with: {bundle_path}")
                                except Exception as e:
                                    for line in stdout.decode('utf-8').splitlines():
                                        output_cache.append(line)
                                    
                            print_action("Running database migrations")
                            ruby_dirs = await find_ruby(client=client)
                            for ruby_path in ruby_dirs:
                                print_action(f"Attempting migration with: {ruby_path}")
                                migration_cmd = f"cd {app_dir} && {ruby_path} bin/rails db:migrate"
                                stdout = await client.send_command(migration_cmd)
                                try:
                                    if "ERRor:" in stdout:
                                        error_output.append(stdout)
                                        print_status('error', f"Migration failed with: {ruby_path}")
                                    else:
                                        print_status('success', f"Migration completed with: {ruby_path}")
                                except Exception as e:
                                    for line in stdout.decode('utf-8').splitlines():
                                        output_cache.append(line)
                            
                            print_action("Uploading metadata")
                            load_metadata_cmd = f"cd {app_dir} && cd bin/ && ./update_art_metadata.sh development"
                            stdout = await client.send_command(load_metadata_cmd)
                            try:
                                if "ERRor:" in stdout:
                                    error_output.append(stdout)
                                    print_status('error', "Metadata upload failed")
                                else:
                                    print_status('success', "Metadata upload completed")
                            except Exception as e:
                                for line in stdout.decode('utf-8').splitlines():
                                    output_cache.append(line)

                print_stage("MANAGING SERVICES")
                redisInstance = RedisCls()
                await redisInstance.connect()
                redisPassword = await redisInstance.getPswrd(ip_address)
                print_action("Reloading Nginx")
                reload_nginx_cmd = "systemctl reload nginx"
                reload_nginx_output = await client.send_sudo_command(redisPassword, reload_nginx_cmd)
                try:
                    if "ERRor:" in reload_nginx_output:
                        error_output.append(reload_nginx_output)
                        print_status('error', "Failed to reload Nginx")
                    else:
                        print_status('success', "Nginx reloaded")
                except Exception as e:
                    decoded_reload_nginx_output = reload_nginx_output.decode("utf-8")
                    output_cache.append(f"Nginx Reload Output:\n{decoded_reload_nginx_output}")

                print_action("Checking Nginx status")
                status_nginx_cmd = "systemctl status nginx"
                status_nginx_output = await client.send_sudo_command(redisPassword, status_nginx_cmd)
                try:
                    if "ERRor:" in status_nginx_output:
                        error_output.append(status_nginx_output)
                        print_status('error', "Failed to get Nginx status")
                    else:
                        print_status('success', "Nginx is running")
                except Exception as e:
                    decoded_status_nginx_output = status_nginx_output.decode("utf-8")
                    output_cache.append(f"Nginx Status Output:\n{decoded_status_nginx_output}")
                
                print_action("Stopping Puma")
                stop_puma_cmd = "systemctl stop puma"
                stop_puma_output = await client.send_sudo_command(redisPassword, stop_puma_cmd)
                try:
                    if "ERRor:" in stop_puma_output:
                        error_output.append(stop_puma_output)
                        print_status('error', "Failed to stop Puma")
                    else:
                        print_status('success', "Puma stopped")
                except Exception as e:
                    decoded_stop_puma_output = stop_puma_output.decode("utf-8")
                    output_cache.append(f"Puma Stop Output:\n{decoded_stop_puma_output}")
                
                print_action("Starting Puma")
                start_puma_cmd = "systemctl start puma"
                start_puma_output = await client.send_sudo_command(redisPassword, start_puma_cmd)
                try:
                    if "ERRor:" in start_puma_output:
                        error_output.append(start_puma_output)
                        print_status('error', "Failed to start Puma")
                    else:
                        print_status('success', "Puma started")
                except Exception as e:
                    decoded_start_puma_output = start_puma_output.decode("utf-8")
                    output_cache.append(f"Puma Start Output:\n{decoded_start_puma_output}")

                print_action("Checking Puma status")
                status_puma_cmd = "systemctl status puma"
                status_puma_output = await client.send_sudo_command(redisPassword, status_puma_cmd)
                try:
                    if "ERRor:" in status_puma_output:
                        error_output.append(status_puma_output)
                        print_status('error', "Failed to get Puma status")
                    else:
                        print_status('success', "Puma is running")
                except Exception as e:
                    decoded_status_puma_output = status_puma_output.decode("utf-8")
                    output_cache.append(f"Puma Status Output:\n{decoded_status_puma_output}")

                print_action("Closing connection")
                client.close()
                print_status('success', "Connection closed")

                print_stage("DEPLOYMENT COMPLETE")
                
                _data_ = {
                    "output": output_cache,
                    "error_output": error_output,
                    "result": collection
                }

                return _data_
            
            except Exception as e:
                print_status('error', f"Deployment failed: {str(e)}")
                return {"error": str(e)}

    except Exception as e:
        client.close()
        error_msg = f"Failed to initiate update task on {ip_address} with exception: {e}"
        print_status('error', error_msg)
        return "failed_to_update_remote_host"


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