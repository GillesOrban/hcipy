# Import all submodules.
from . import aperture
from . import atmosphere
from . import coronagraphy
from . import field
from . import fourier
from . import interpolation
from . import mode_basis
from . import optics
from . import plotting
from . import propagation
from . import tests
from . import util
from . import wavefront_control
from . import wavefront_sensing

# Import all core submodules in default namespace.
from .aperture import *
from .atmosphere import *
from .config import *
from .coronagraphy import *
from .field import *
from .fourier import *
from .interpolation import *
from .metrics import *
from .mode_basis import *
from .optics import *
from .plotting import *
from .propagation import *
from .tests import *
from .util import *
from .wavefront_control import *
from .wavefront_sensing import *

# Export default namespaces.
__all__ = []
__all__.extend(aperture.__all__)
__all__.extend(atmosphere.__all__)
__all__.extend(config.__all__)
__all__.extend(coronagraphy.__all__)
__all__.extend(field.__all__)
__all__.extend(fourier.__all__)
__all__.extend(interpolation.__all__)
__all__.extend(metrics.__all__)
__all__.extend(mode_basis.__all__)
__all__.extend(optics.__all__)
__all__.extend(plotting.__all__)
__all__.extend(propagation.__all__)
__all__.extend(tests.__all__)
__all__.extend(util.__all__)
__all__.extend(wavefront_control.__all__)
__all__.extend(wavefront_sensing.__all__)

from .version import get_version
__version__ = get_version()
