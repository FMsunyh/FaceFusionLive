#!/usr/bin/env python3

from modules import core
import multiprocessing
import platform

if __name__ == '__main__':
    if platform.system().lower() == 'Linux':
        multiprocessing.set_start_method('spawn')
    core.run()
