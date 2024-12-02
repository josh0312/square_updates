import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning

def get_with_ssl_ignore(url, headers=None, timeout=30):
    """
    Make a GET request ignoring SSL verification warnings
    """
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=InsecureRequestWarning)
        return requests.get(url, headers=headers, verify=False, timeout=timeout) 