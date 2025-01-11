import os
from dotenv import load_dotenv
load_dotenv()
from utils import imp_exp_func
import logging

async def get_sites_async():
    """
    Asynchronously retrieves site information from the configured API endpoint.
    
    Returns:
        Optional[list]: List of sites if successful, None if failed
    """
    endpoint = os.getenv('IMPORTER_ENDPOINT')
    if not endpoint:
        logging.error("IMPORTER_ENDPOINT environment variable is not set")
        return None
        
    print("Getting sites: ", endpoint)
    response = await imp_exp_func.get_data_from_api_async(endpoint)
    return response

async def get_cluster_async():
    """
    Asynchronously retrieve cluster data from the API
    """
    cluster = await imp_exp_func.get_data_from_api_async(os.getenv('CLUSTER_ID'))
    return cluster

async def get_cluster_id_async():
    """
    Asynchronously get cluster IDs from the cluster data
    """
    data = await get_cluster_async()
    pks = []
    for item in data:
        pk = item.get("pk")
        if pk is not None:
            pks.append(pk)
    return pks

async def get_cluster_name_async():
    """
    Asynchronously get cluster name from the cluster data
    """
    data = await get_cluster_async()
    cluster_name = data[0]['fields']['name']
    return cluster_name
