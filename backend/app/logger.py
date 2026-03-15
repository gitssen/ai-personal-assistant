import logging
import sys

def setup_logger():
    logger = logging.getLogger("ai_assistant")
    logger.setLevel(logging.DEBUG)
    
    # Just log to console (which run.py will capture)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

logger = setup_logger()
