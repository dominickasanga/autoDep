from utils import imp_exp_func, host, decorators, net
from utils.app_version import apps, check_versions
from utils.file_operations import insert_data_to_csv
import os
from dotenv import load_dotenv
import asyncio
load_dotenv()
import colorama
from colorama import Fore, Style

@decorators.check_if_host_is_reachable
async def update_host(ip_address: str, user_name: str, headers: dict, cluster_id: int, cluster_name: str, host_name: str) -> bool:
    try:
        # Get update details
        details = await host.update_remote_host(user_name, ip_address)
        
        # Validate details
        if not details or not isinstance(details, dict):
            raise ValueError(f"Invalid response from update_remote_host: {details}")
            
        # Safely access dictionary values with error handling
        error_output = details.get("error_output")
        output = details.get("output")
        result = details.get("result")
        
        if error_output is None or output is None or result is None:
            raise KeyError(f"Missing required keys in response: {details}")
            
        # Print logs
        decorators.print_tap_window_box(error_output, f"{host_name} ERROR LOG")
        decorators.print_tap_window_box(output, f"{host_name} GENERAL LOG")
        
        # Check versions and handle results
        if check_versions(result):
            await insert_data_to_csv(ip_address, host_name, cluster_id, cluster_name, "updated")
            
            notification_data = {
                "ip_address": ip_address,
                "apps": apps  # Make sure 'apps' is defined in scope
            }
            
            try:
                await imp_exp_func.send_data(
                    os.getenv('NOTIFICATION_ENDPOINT'), 
                    notification_data, 
                    headers
                )
            except Exception as e:
                print(f"Notification error: {str(e)}")
                # Continue execution even if notification fails
                
            return True
            
        else:
            await insert_data_to_csv(ip_address, host_name, cluster_id, cluster_name, "failed")
            
            failure_payload = {
                "ip_address": ip_address,
                "message": "failed to auto deploy"
            }
            
            try:
                await imp_exp_func.send_data(
                    os.getenv('GENERAL_NOTIFICATION_ENDPOINT'), 
                    failure_payload, 
                    headers
                )
            except Exception as e:
                print(f"Failure notification error: {str(e)}")
                
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to update host {host_name} ({ip_address})")
        print(f"Exception details: {str(e)}")
        
        # Log the failure
        await insert_data_to_csv(ip_address, host_name, cluster_id, cluster_name, "failed")
        
        return False
