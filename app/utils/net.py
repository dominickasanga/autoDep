import os
import platform
import subprocess
import asyncio
import paramiko
import redis
from redis.asyncio import Redis
from utils import xi
import colorama
from colorama import Fore, Style
import socket
import re
from dotenv import load_dotenv
load_dotenv()

def host_is_reachable(ip_address, port=22):
    sock = None
    try:
        # Create a socket object
        sock = socket.create_connection((ip_address, port), timeout=5)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError):
        return False
    except Exception as e:
        if sock:
            sock.close()
        raise e


class AsyncParamikoSSHClient(paramiko.SSHClient):
    
    def __init__(self, host, username):
        super().__init__()
        self.host = host
        self.username = username

    async def clsConnect(self):
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, self._connect_key_based, self.host, self.username)
        await future

    async def clsConnectWithPass(self, password):
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, self._connect, self.host, self.username, password)
        await future

    def _connect(self, host, username, password):
        # self.connect(host, username, password)
        self.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connect(hostname=host, username=username, password=password, port=22)

    def _connect_key_based(self, host, username):
        try:
            self.load_system_host_keys()
            self.set_missing_host_key_policy(paramiko.WarningPolicy())
            
            # Check common key locations
            key_paths = [
                ("~/.ssh/id_rsa", paramiko.RSAKey),
                # ("~/.ssh/id_ed25519", paramiko.Ed25519Key),
                # ("~/.ssh/id_ecdsa", paramiko.ECDSAKey),
                # ("~/.ssh/id_dsa", paramiko.DSSKey)
            ]
            
            # Override with environment variable if set
            if "SSH_PRIVATE_KEY_PATH" in os.environ:
                custom_path = os.environ["SSH_PRIVATE_KEY_PATH"]
                # Add the custom path to the start of our list
                key_paths.insert(0, (custom_path, None))  # None means we'll detect type
                
            connected = False
            last_exception = None
            
            for key_path, key_type in key_paths:
                try:
                    full_path = os.path.expanduser(key_path)
                    if not os.path.exists(full_path):
                        continue
                        
                    print(f"Attempting connection to {host} with key at {full_path}")
                    
                    # If key_type is None (custom path), try all key types
                    if key_type is None:
                        key_types = [paramiko.Ed25519Key, paramiko.RSAKey, 
                                paramiko.ECDSAKey, paramiko.DSSKey]
                    else:
                        key_types = [key_type]
                    
                    # Try each possible key type for this file
                    for kt in key_types:
                        try:
                            mykey = kt.from_private_key_file(full_path)
                            self.connect(hostname=host, username=username, 
                                    pkey=mykey, port=22)
                            connected = True
                            print(f"Successfully connected using {full_path}")
                            return True
                        except (paramiko.SSHException, Exception) as e:
                            last_exception = e
                            continue
                            
                except Exception as e:
                    last_exception = e
                    continue
                    
            if not connected:
                # If we got here, no connection was successful
                with open("setpolicykey.txt", "a") as file:
                    file.write(f"ssh {username}@{host}\n")
                error_msg = str(last_exception) if last_exception else "No valid keys found"
                print(f"connect key based error: {error_msg} for HOST: {host}")
                return False
                
        except Exception as e:
            with open("setpolicykey.txt", "a") as file:
                file.write(f"ssh {username}@{host}\n")
            print(f"connect key based error: {str(e)} for HOST: {host}")
            return False

    async def send_command(self, command):
        channel = self.exec_command(command)
        stdin, stdout, stderr = channel
        output = stdout.read()
        # self.close()
        return output
    
    async def send_sudo_command(self, password, command):
        sudo_command = f"echo \"{password}\" | sudo -S "+command
        channel = self.exec_command(sudo_command)
        stdin, stdout, stderr = channel
        decoded_stderr = stderr.read().decode("utf-8")  # Decode the stdout bytes into a string
        if decoded_stderr:
            # print(f"ERRor:\n{decoded_stderr}")
            True
        output = stdout.read()
        # self.close()
        return output
    
    async def custom_open_sftp(self):
        channel = self.open_sftp()
        return channel

    async def send_command_for_paths(self, command):
        channel = self.exec_command(command)
        stdin, stdout, stderr = channel
        decoded_stderr = stderr.read().decode("utf-8")  # Decode the stdout bytes into a string
        if decoded_stderr:
            # return f"ERRor:\n{decoded_stderr}"
            True
        output = stdout.read()
        # self.close()
        return output

    async def receive_command(self, command):
        channel = await self.open_channel('session')
        await channel.exec_command(command)
        output = await channel.read_until_eof()
        channel.close()
        return output
    
    def is_connected(self):
        """
        Check if the client is connected to the SSH server.
        """
        transport = self.get_transport()
        if transport and transport.is_active():
            return True
        return False

class RedisCls():
    def __init__(self):
        self.host = 'localhost'
        self.port = 6379
        self.db = 0
        self.redis = None

    async def connect(self):
        # connect to Redis asynchronously
        self.redis = await Redis(host=self.host, port=self.port, db=self.db)

    async def updatePswrdDict(self, key, value):
        # update or insert a key-value pair asynchronously
        await self.redis.set(key, value)

    async def getPswrd(self, ip_address):
        # get the value for the given key asynchronously, or return False if the key is not in Redis
        try:
            value = await self.redis.get(ip_address)

            if value is None:
                return False
            else:
                return value.decode('utf-8')
        except Exception as e:
            return False
        
async def get_host_name__async(ip_address):
    hosts = await xi.get_sites_async()
    for host in hosts:
        if host['fields']['ip_address'] == ip_address:
            return host['fields']['name']

    return None  # Return None if no matching IP address is found
