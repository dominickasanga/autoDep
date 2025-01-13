from multiprocessing import Process
import asyncio
import os
import time
from time import sleep
from dotenv import load_dotenv
from utils import imp_exp_func, file_operations, xi
from transpoter import update_host
from concurrent.futures import ProcessPoolExecutor
import asyncio
from functools import partial

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

def process_site(ip_address: str, user_name: str, headers: dict, cluster_id: int, 
                cluster_name: str, host_name: str) -> bool:
    """
    Wrapper function to run update_host in a separate process.
    """
    return asyncio.run(update_host(
        ip_address, user_name, headers, cluster_id, cluster_name, host_name
    ))

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
            
        # Get cluster details asynchronously
        try:
            cluster_details = await asyncio.gather(
                xi.get_cluster_id_async(),
                xi.get_cluster_name_async()
            )
            cluster_id = cluster_details[0][0]  # Assuming it returns a list
            cluster_name = cluster_details[1]
        except Exception as e:
            print(f"Error getting cluster details: {str(e)}")
            cluster_id = 1
            cluster_name = "default"

        # Prepare site processing arguments
        site_args = [
            (
                site["fields"]["ip_address"],
                site["fields"]["username"],
                headers,
                cluster_id,
                cluster_name,
                site["fields"]["name"]
            )
            for site in filtered_sites
        ]

        # Create a ProcessPoolExecutor with a maximum number of workers
        max_workers = min(len(site_args), os.cpu_count() or 4)
        
        # Process sites in parallel using ProcessPoolExecutor
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Create tasks for each site
            futures = [
                loop.run_in_executor(
                    executor,
                    partial(process_site, *args)
                )
                for args in site_args
            ]
            
            # Wait for all tasks to complete and gather results
            results = await asyncio.gather(*futures, return_exceptions=True)
            
            # Process results
            for host_name, result in zip([site["fields"]["name"] for site in filtered_sites], results):
                if isinstance(result, Exception):
                    print(f"Error processing {host_name}: {str(result)}")
                elif not result:
                    print(f"Failed to update {host_name}")
                else:
                    print(f"Successfully updated {host_name}")
                    
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