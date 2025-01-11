from multiprocessing import Process
import asyncio
import os
import time
from time import sleep
from dotenv import load_dotenv
from utils import imp_exp_func, file_operations, xi
from transpoter import update_host

load_dotenv()

def filter_sites(sites_list, cluster_data):
    """
    Filter sites based on site IDs from cluster data.
    Returns all sites if no cluster data is available.
    """
    if not cluster_data:
        print("Warning: No cluster data available, returning all sites")
        return sites_list
        
    try:
        site_ids = cluster_data[0]['fields']['site']
        filtered_sites = [site for site in sites_list if site['pk'] in site_ids]
        print(f"Filtered {len(filtered_sites)} sites from {len(sites_list)} total sites")
        return filtered_sites
    except (IndexError, KeyError) as e:
        print(f"Error filtering sites: {str(e)}")
        print("Returning all sites as fallback")
        return sites_list

async def init():
    """
    Initialize the deployment process with async site and cluster retrieval.
    """
    try:
        # Get sites and cluster data asynchronously
        sites = await xi.get_sites_async()
        if not sites:
            print("Error: No sites retrieved")
            return False
            
        cluster_hosts = await xi.get_cluster_async()
        if not cluster_hosts:
            print("Warning: No cluster hosts retrieved")
            
        headers = {
            'Content-type': 'application/json',
            'Accept': 'text/plain',
            'Authorization': os.getenv('EXPORTER_KEY')
        }
        
        filtered_sites = filter_sites(sites, cluster_hosts)
        if not filtered_sites:
            print("No sites to process after filtering")
            return False
            
        processes = []
        
        # Get cluster details asynchronously
        try:
            cluster_id = await xi.get_cluster_id_async()
            cluster_name = await xi.get_cluster_name_async()
        except Exception as e:
            print(f"Error getting cluster details: {str(e)}")
            # You might want to set default values here
            cluster_id = [1]  # or whatever default makes sense
            cluster_name = "default"
        
        # Start processes for each site
        for site in filtered_sites:
            ip_address = site["fields"]["ip_address"]
            user_name = site["fields"]["username"]
            host_name = site["fields"]["name"]
            
            print(f"Processing site: {host_name} ({ip_address})")
            
            p_process = Process(
                target=update_host,
                args=(ip_address, user_name, headers, cluster_id[0], cluster_name, host_name)
            )
            p_process.start()
            processes.append(p_process)
        
        # Wait for all processes to finish
        for process in processes:
            process.join()
            
        return True
        
    except Exception as e:
        print(f"Error in init: {str(e)}")
        return False

def call_process():
    """
    Main process handler with output redirection and timing.
    """
    file_operations.redirect_output_to_file('app/output.txt')
    start_time = time.time()
    
    # Run the async init function using asyncio
    asyncio.run(init())
    
    end_time = time.time()
    runtime = end_time - start_time
    print("Runtime:", runtime, "seconds")
    file_operations.restore_output()

if __name__ == '__main__':
    start_time = time.time()
    
    # Run the async init function using asyncio
    if asyncio.run(init()):
        end_time = time.time()
        runtime = end_time - start_time
        print("########################################################################################################")
        print("Runtime: ", runtime, " seconds")
        print()
        print()
        file_operations.read_csv_contents()