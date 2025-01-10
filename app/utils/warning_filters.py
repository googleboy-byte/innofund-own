import warnings
import logging
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ignore_web3_warnings(func):
    """Decorator to suppress Web3 related warnings"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            # Ignore all eth_utils network warnings
            warnings.filterwarnings("ignore", category=UserWarning, module="eth_utils.network")
            # Ignore rusty-rlp performance warning
            warnings.filterwarnings("ignore", message=".*rusty-rlp.*")
            return func(*args, **kwargs)
    return wrapper

def setup_warning_filters():
    """Set up global warning filters"""
    # Suppress eth_utils network warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="eth_utils.network")
    # Suppress rusty-rlp performance warning
    warnings.filterwarnings("ignore", message=".*rusty-rlp.*")
    logger.info("Web3 warning filters configured")
