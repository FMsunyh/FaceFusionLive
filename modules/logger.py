import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime

class LoggerWrapper:
    _instance = None
    _log_filename = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = cls.setup_logger()
        return cls._instance

    @classmethod
    def setup_logger(cls):
        # Ensure logs directory exists
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)

        # Generate a filename based on the current date and time (when the program starts)
        if cls._log_filename is None:
            # cls._log_filename = 'server.log'
            cls._log_filename = 'server_' + datetime.now().strftime('%Y-%m-%d') + '.log'
        
        log_filepath = os.path.join(log_dir, cls._log_filename)

        # Set up logging configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(threadName)s: %(message)s',
            handlers=[
                TimedRotatingFileHandler(log_filepath, when="midnight", interval=1, backupCount=30),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('my_logger')

    @property
    def logger(self):
        return self._logger


logger = LoggerWrapper().logger
