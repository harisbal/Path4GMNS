import logging

from .accessibility import *
from .colgen import *
from .dtaapi import *
from .io import *
from .odme import *
from .simulation import *
from .utils import *
from .zonesyn import *

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

__version__ = "0.10.0"

# print out the current version
logging.info(f"path4gmns, version {__version__}\n")
