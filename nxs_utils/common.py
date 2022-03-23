from __future__ import division, print_function, absolute_import
import os
import uuid
import shutil
import json
import requests
import time

def generate_uuid() -> str:
    return str(uuid.uuid4()).replace('-','')

def create_dir_if_needed(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def delete_and_create_dir(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path)  

def delete_dir(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

def delete_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        
