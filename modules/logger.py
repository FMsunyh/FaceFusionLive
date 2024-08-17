import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime

# Ensure logs directory exists
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

# Generate a filename based on the current date and time
log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '.log'
log_filepath = os.path.join(log_dir, log_filename)

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
    handlers=[
        TimedRotatingFileHandler(log_filepath, when="midnight", interval=1, backupCount=30),
        logging.StreamHandler()
    ]
)

# Example usage
logger = logging.getLogger('Face_Live')
logger.info("This is a log message.")
