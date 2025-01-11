from typing import Any
from typing import Any, Optional
import requests
import json
import os
import aiohttp
import asyncio
import logging
from typing import Optional, Any

async def get_data_from_api_async(endpoint: str, timeout: int = 30) -> Optional[Any]:
    """
    Asynchronously fetches data from an API endpoint.
    
    Args:
        endpoint (str): The API endpoint URL
        timeout (int): Request timeout in seconds
        
    Returns:
        Optional[Any]: JSON response if successful, None if failed
    """
    timeout = aiohttp.ClientTimeout(total=timeout)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint) as response:
                if response.status == 200:
                    return await response.json()
                logging.error(f"API request failed with status {response.status}")
                return None
                
    except aiohttp.ClientError as e:
        logging.error(f"Request failed: {str(e)}")
        return None
    except asyncio.TimeoutError:
        logging.error(f"Request timed out after {timeout} seconds")
        return None


def send_data(endpoint: str, payload: dict, headers: dict) -> bool:
    """sends data to central repo

    Args:
        endpoint (str): central repo endpoint
        payload (dict): remote data
        headers (str): required headers

    Returns:
        bool: True if data is sent to central repo successfully, False otherwise
    """
    try:
        r = requests.post(endpoint, json=payload, headers=headers)

    except Exception as e:
        print("Failed to send data to a central point. The exception details is: ", e)
        return False

    else:

        r.raise_for_status()
        print('Data sent successfully', r.json())
        return True
