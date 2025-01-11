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
def update_host(ip_address: str, user_name: str, headers: dict, cluster_id: int, cluster_name: str, host_name: str) -> bool:

    
    details = asyncio.run(host.update_remote_host(user_name, ip_address))

    decorators.print_tap_window_box(details["error_output"], host_name +" ERROR LOG")

    decorators.print_tap_window_box(details["output"], host_name +" GENERAL LOG")

    if check_versions(details["result"]):

        asyncio.run(insert_data_to_csv(ip_address, host_name, cluster_id, cluster_name, "updated"))

        data = {
            "ip_address": ip_address,
            "apps": apps
            }

        try:
            imp_exp_func.send_data(
                os.getenv('NOTIFICATION_ENDPOINT'), data, headers)
        except Exception as e:
            print("eeror: ", e)
    else:
        asyncio.run(insert_data_to_csv(ip_address, host_name, cluster_id, cluster_name, "failed"))

        payload = {
                "ip_address": ip_address,
                "message": "failed to auto deploy"
        }
        
        try:
            imp_exp_func.send_data(
                os.getenv('GENERAL_NOTIFICATION_ENDPOINT'), payload, headers)
        except Exception as e:
            print("eeror: ", e)
