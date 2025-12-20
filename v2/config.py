'''Configuration module for v2 task management system'''
from pathlib import Path
from typing import Any, Dict
import os


# Define the project root directory (parent of v2 directory)
ROOT_DIR = Path(__file__).parent.parent.absolute()


def get_version() -> str:
    '''Get version for v2 system'''
    return '2.0.0'


def get_config() -> Dict[str, Any]:
    '''Get v2 configuration based on environment'''
    env_type = os.environ.get('VIG_ENV_TYPE', 'work')

    # V2-specific configuration
    config = {
        'db_path': os.environ.get(
            'VIG_V2_DB_PATH',
            f'sqlite:///{ROOT_DIR}/instance/tasks_v2.db'
        ),
        'env_type': env_type,
        'version': get_version()
    }

    return config
