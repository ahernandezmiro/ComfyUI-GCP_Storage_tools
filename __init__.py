import importlib
import pip

def install_gcp_storage():
    print("Checking for google-cloud-storage installation..")
    try:
        importlib.import_module("google.cloud.storage")
    except ImportError:
        print("google-cloud-storage not found. Installing...")
        pip.main(["install", "google-cloud-storage"])


install_gcp_storage()

from .gcp_storage_tools import NODE_CLASS_MAPPINGS
from .gcp_storage_tools import NODE_DISPLAY_NAME_MAPPINGS

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
