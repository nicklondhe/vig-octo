'''Configuration module for the application'''
from pathlib import Path
from typing import Dict, Any
import os


# Define the project root directory
ROOT_DIR = Path(__file__).parent.absolute()

def get_version() -> str:
    '''Get version from pyproject.toml file'''
    '''
    try:
        with open(ROOT_DIR / 'pyproject.toml', 'rb') as f:
            data = tomli.load(f)
            return data['project']['version']
    except (FileNotFoundError, KeyError):
        return '0.1.0'  # Fallback version
    '''
    return '0.1.1'

def get_config() -> Dict[str, Any]:
    '''Get configuration based on environment'''
    env_type = os.environ.get('VIG_ENV_TYPE', 'work')

    # Default configuration
    config = {
        'db_path': os.environ.get(
            'VIG_DB_PATH',
            f'sqlite:///{ROOT_DIR}/instance/tasks.db'
        ),
        'env_type': env_type
    }

    return config
