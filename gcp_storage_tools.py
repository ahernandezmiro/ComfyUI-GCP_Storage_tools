import os
import io
import numpy as np
from PIL import Image, ImageOps
from google.cloud import storage
import torch

class GCPReadImageNode:
    def __init__(self):
       # Build a temp folder 2 levels above this script
       script_dir = os.path.dirname(os.path.abspath(__file__))
       self.output_dir = os.path.normpath(os.path.join(script_dir, "temp"))
       os.makedirs(self.output_dir, exist_ok=True)

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "bucket_name": ("STRING", {"default": "my-bucket"}),
                "bucket_path": ("STRING", {"default": "some/folder"}),
                "file_name": ("STRING", {"default": "my_image.png"}),
                "gcp_service_json": ("STRING", {"default": "/path/to/service_account.json"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "download_from_gcp"
    OUTPUT_NODE = True  # Mark as output node
    CATEGORY = "gcp_storage"
    

    def download_from_gcp(self, bucket_name, bucket_path, file_name, gcp_service_json):
        try:
            
            script_dir = os.path.dirname(os.path.abspath(__file__))  # folder where this script lives
            if not os.path.isabs(gcp_service_json):
                gcp_service_json = os.path.join(script_dir, gcp_service_json)

            # Check if credentials file exists
            if not os.path.exists(gcp_service_json):
                raise FileNotFoundError(f"Credential file not found: {gcp_service_json}")

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_service_json



            if not file_name.lower().endswith(".png"):
                file_name += ".png"

            local_file_path = os.path.join(self.output_dir, os.path.basename(file_name))
            gcp_path = f"{bucket_path}/{os.path.basename(file_name)}".strip("/")

            # Download from GCP to local file
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(gcp_path)
            print(f"[GCP READ] Downloading gs://{bucket_name}/{gcp_path} → {local_file_path}")
            blob.download_to_filename(local_file_path)
            
            # Load and process image
            i = Image.open(local_file_path)
            i = ImageOps.exif_transpose(i)
            image = i.convert("RGB")
            
            # Convert to numpy array and normalize
            image_np = np.array(image).astype(np.float32) / 255.0
            
            # Ensure shape is [batch, height, width, channels]
            if len(image_np.shape) == 3:
                image_np = image_np[None, ...]
            
            image = torch.from_numpy(image_np)
            image = image.contiguous().float()
            
            os.remove(local_file_path)
            
            return (image,)
        except Exception as e:
            print(str(e))
            raise e


class GCPWriteImageNode:
    def __init__(self):
        self.compress_level = 4
        self.type = "output"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.normpath(os.path.join(script_dir, "out"))
        os.makedirs(self.output_dir, exist_ok=True)

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "bucket_name": ("STRING", {"default": "my-bucket"}),
                "bucket_path": ("STRING", {"default": "some/folder"}),
                "file_name": ("STRING", {"default": "my_output.png"}),
                "gcp_service_json": ("STRING", {"default": "/path/to/service_account.json"}),
            }
        }

    # We'll define two outputs:
    #   1) The original image if success
    #   2) A string error message if failure
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "error_message")
    FUNCTION = "store_image_in_gcp"
    OUTPUT_NODE = True  # Mark as output node
    CATEGORY = "gcp_storage"

    def store_image_in_gcp(self, images, bucket_name, bucket_path, file_name, gcp_service_json):
        error_message = ""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))  # folder where this script lives
            if not os.path.isabs(gcp_service_json):
                gcp_service_json = os.path.join(script_dir, gcp_service_json)

            if not os.path.exists(gcp_service_json):
                raise FileNotFoundError(f"Credential file not found: {gcp_service_json}")

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_service_json

            subfolder = os.path.dirname(os.path.normpath(file_name))
            full_output_folder = os.path.join(self.output_dir, subfolder)
            full_file_path = os.path.join(full_output_folder, file_name)

            results = list()
            for (batch_number, image) in enumerate(images):
                i = 255. * image.cpu().numpy()
                img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                metadata = None
                img.save(os.path.join(full_output_folder, file_name), pnginfo=metadata, compress_level=self.compress_level)
                results.append({
                    "filename": file_name,
                    "subfolder": subfolder,
                    "type": self.type
                })
            
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(f"{bucket_path}/{file_name}")
            print(f"Uploading blob to {bucket_name}/{bucket_path}/{file_name}..")
            blob.upload_from_filename(full_file_path)
            
            # Cleanup the temp file if you want
            os.remove(full_file_path)

            return {"ui": {"images": results}}
        except Exception as e:
            error_message = f"Upload failed: {str(e)}"
            print(error_message)
            # Return None for image, and the error message in the second output
            return (None, error_message)



NODE_CLASS_MAPPINGS = {
    "GCPReadImageNode": GCPReadImageNode,
    "GCPWriteImageNode": GCPWriteImageNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GCPReadImageNode": "GCP: Read Image",
    "GCPWriteImageNode": "GCP: Write Images",
}