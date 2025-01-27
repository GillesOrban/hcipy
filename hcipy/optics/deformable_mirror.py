import numpy as np
from scipy.sparse import csr_matrix
import numexpr as ne

try:
	from importlib.resources import files
except ImportError:
	from importlib_resources import files

from .optical_element import OpticalElement
from ..field import make_uniform_grid, evaluate_supersampled
from ..mode_basis import ModeBasis, make_gaussian_pokes
from ..interpolation import make_linear_interpolator_separated
from ..util import read_fits

def make_actuator_positions(num_actuators_across_pupil, actuator_spacing, x_tilt=0, y_tilt=0, z_tilt=0):
	'''Make actuator positions using the BMC convention.

	Parameters
	----------
	num_actuators_across_pupil : integer
		The number of actuators across the pupil. The total number of actuators will be this number squared.
	actuator_spacing : scalar
		The spacing between actuators before tilting the deformable mirror.
	x_tilt : scalar
		The tilt of the deformable mirror around the x-axis in radians.
	y_tilt : scalar
		The tilt of the deformable mirror around the y-axis in radians.
	z_tilt : scalar
		The tilt of the deformable mirror around the z-axis in radians.

	Returns
	-------
	Grid
		The actuator positions.
	'''
	extent = actuator_spacing * num_actuators_across_pupil
	grid = make_uniform_grid(num_actuators_across_pupil, [extent, extent]).scaled(np.cos([y_tilt, x_tilt]))

	if z_tilt == 0:
		return grid

	grid = grid.rotated(z_tilt)
	return grid

def make_gaussian_influence_functions(pupil_grid, num_actuators_across_pupil, actuator_spacing, crosstalk=0.15, cutoff=3, x_tilt=0, y_tilt=0, z_tilt=0, oversampling=1):
	'''Create influence functions with a Gaussian profile.

	The default value for the crosstalk is representative for Boston Micromachines DMs.

	Parameters
	----------
	pupil_grid : Grid
		The grid on which to calculate the influence functions.
	num_actuators_across_pupil : integer
		The number of actuators across the pupil. The total number of actuators will be this number squared.
	actuator_spacing : scalar
		The spacing between actuators before tilting the deformable mirror.
	crosstalk : scalar
		The amount of crosstalk between the actuators. This is defined as the value of the influence function
		at a nearest-neighbour actuator.
	cutoff : scalar
		The distance from the center of the actuator, as a fraction of the actuator spacing, where the
		influence function is truncated to zero.
	x_tilt : scalar
		The tilt of the deformable mirror around the x-axis in radians.
	y_tilt : scalar
		The tilt of the deformable mirror around the y-axis in radians.
	z_tilt : scalar
		The tilt of the deformable mirror around the z-axis in radians.
	oversampling : integer
		The oversamping factor when creating the Gaussian. Default: 1.

	Returns
	-------
	ModeBasis
		The influence functions for each of the actuators.
	'''
	actuator_positions = make_actuator_positions(num_actuators_across_pupil, actuator_spacing)

	sigma = actuator_spacing / (np.sqrt((-2 * np.log(crosstalk))))
	cutoff = actuator_spacing / sigma * cutoff

	def transform_poke(poke):
		def new_poke(grid):
			p = poke(grid.scaled(1 / np.cos([y_tilt, x_tilt])).rotated(-z_tilt))
			p /= np.cos(x_tilt) * np.cos(y_tilt)

			return p
		return new_poke

	pokes = make_gaussian_pokes(None, actuator_positions, sigma, cutoff)
	pokes = [transform_poke(p) for p in pokes]
	pokes = evaluate_supersampled(pokes, pupil_grid, oversampling, make_sparse=True)

	return pokes

def make_xinetics_influence_functions(pupil_grid, num_actuators_across_pupil, actuator_spacing, x_tilt=0, y_tilt=0, z_tilt=0):
	'''Create influence functions for a Xinetics deformable mirror.

	This function uses a The rotation of the deformable mirror will be done in the order X-Y-Z.

	Parameters
	----------
	pupil_grid : Grid
		The grid on which to calculate the influence functions.
	num_actuators_across_pupil : integer
		The number of actuators across the pupil. The total number of actuators will be this number squared.
	actuator_spacing : scalar
		The spacing between actuators before tilting the deformable mirror.
	x_tilt : scalar
		The tilt of the deformable mirror around the x-axis in radians.
	y_tilt : scalar
		The tilt of the deformable mirror around the y-axis in radians.
	z_tilt : scalar
		The tilt of the deformable mirror around the z-axis in radians.

	Returns
	-------
	ModeBasis
		The influence functions for each of the actuators.
	'''
	actuator_positions = make_actuator_positions(num_actuators_across_pupil, actuator_spacing)

	# Stretch and rotate pupil_grid to correct for tilted DM
	evaluated_grid = pupil_grid.scaled(1 / np.cos([y_tilt, x_tilt])).rotated(-z_tilt)

	# Read in actuator shape from file.
	f = files('hcipy.optics').joinpath('influence_dm5v2.fits')
	with f.open('rb') as fp:
		actuator = np.squeeze(read_fits(fp)).astype('float')
	actuator /= actuator.max()

	# Convert actuator into linear interpolator.
	actuator_grid = make_uniform_grid(actuator.shape, np.array(actuator.shape) * actuator_spacing / 10.0)
	actuator = make_linear_interpolator_separated(actuator.ravel(), actuator_grid, 0)

	def poke(p):
		res = csr_matrix(actuator(evaluated_grid.shifted(-p))) / np.cos(x_tilt) * np.cos(y_tilt)
		res.eliminate_zeros()

		return res

	return ModeBasis([poke(p) for p in actuator_positions.points], pupil_grid)

def find_illuminated_actuators(basis, aperture, power_cutoff=0.1):
	'''Find the illuminated modes.

	A subset of the modes is selected based on the aperture function and a power cutoff.

	Parameters
	----------
	basis : ModeBasis
		The mode basis for which we want to find the illuminated modes.
	aperture : Field or array_like
		The aperture
	power_cutoff : scalar
		The minimal required power over the aperture.

	Returns
	-------
	ModeBasis
		The illuminated influence functions.
	'''
	total_power = np.sum(abs(basis._transformation_matrix)**2, axis=0)
	masked_power = np.sum(abs(basis._transformation_matrix[aperture > 0])**2, axis=0)
	illuminated_actuator_mask = masked_power >= (power_cutoff * total_power)

	return ModeBasis(basis._transformation_matrix[:, illuminated_actuator_mask], basis.grid)

class DeformableMirror(OpticalElement):
	'''A deformable mirror using influence functions.

	This class does not contain any temporal simulation (ie. settling time),
	and assumes that there is no crosstalk between actuators.

	Parameters
	----------
	influence_functions : ModeBasis
		The influence function for each of the actuators.
	'''
	def __init__(self, influence_functions):
		self.influence_functions = influence_functions

		self.actuators = np.zeros(len(influence_functions))
		self._actuators_for_cached_surface = None

		self.input_grid = influence_functions.grid
		self._surface = self.input_grid.zeros()

	@property
	def num_actuators(self):
		return self._actuators.size

	@property
	def actuators(self):
		return self._actuators

	@actuators.setter
	def actuators(self, actuators):
		self._actuators = actuators

	def forward(self, wavefront):
		'''Propagate a wavefront through the deformable mirror.

		Parameters
		----------
		wavefront : Wavefront
			The incoming wavefront.

		Returns
		-------
		Wavefront
			The reflected wavefront.
		'''
		wf = wavefront.copy()

		variables = {'alpha': 2j * wavefront.wavenumber, 'surf': self.surface}
		wf.electric_field *= ne.evaluate('exp(alpha * surf)', local_dict=variables)

		return wf

	def backward(self, wavefront):
		'''Propagate a wavefront backwards through the deformable mirror.

		Parameters
		----------
		wavefront : Wavefront
			The incoming wavefront.

		Returns
		-------
		Wavefront
			The reflected wavefront.
		'''
		wf = wavefront.copy()

		variables = {'alpha': -2j * wavefront.wavenumber, 'surf': self.surface}
		wf.electric_field *= ne.evaluate('exp(alpha * surf)', local_dict=variables)

		return wf

	@property
	def influence_functions(self):
		'''The influence function for each of the actuators of this deformable mirror.
		'''
		return self._influence_functions

	@influence_functions.setter
	def influence_functions(self, influence_functions):
		self._influence_functions = influence_functions
		self._actuators_for_cached_surface = None

	@property
	def surface(self):
		'''The surface of the deformable mirror in meters.
		'''
		if self._actuators_for_cached_surface is not None:
			if np.all(self.actuators == self._actuators_for_cached_surface):
				return self._surface

		self._surface = self.influence_functions.linear_combination(self.actuators)
		self._actuators_for_cached_surface = self.actuators.copy()

		return self._surface

	@property
	def opd(self):
		'''The optical path difference in meters that this deformable
		mirror induces.
		'''
		return 2 * self.surface

	def random(self, rms):
		'''Set the dm actuators with random white noise of a certain rms.

		Parameters
		----------
		rms : scalar
			The dm surface rms.
		'''
		self._actuators = np.random.randn(self._actuators.size) * rms

	def phase_for(self, wavelength):
		'''Get the phase in radians that is added to a wavefront with a specified wavelength.

		Parameters
		----------
		wavelength : scalar
			The wavelength at which to calculate the phase deformation.

		Returns
		-------
		Field
			The calculated phase deformation.
		'''
		return 2 * self.surface * 2 * np.pi / wavelength

	def flatten(self):
		'''Flatten the DM by setting all actuators to zero.
		'''
		self._actuators = np.zeros(len(self.influence_functions))

def label_actuator_centroid_positions(influence_functions, label_format='{:d}', **text_kwargs):
	'''Display centroid positions for a set of influence functions.

	The location of each of the actuators is calculated using a weighted centroid, and
	at that location a label is written to the open Matplotlib Figure. The text can be
	modified with `label_format`, which is formatted with new-style Python formatting:
	`label_format.format(i)` where `i` is the actuator index.

	Parameters
	----------
	influence_functions : ModeBasis
		The influence function for each actuator.
	label_format : string
		The text that will be displayed at the actuator centroid. This must be a new-style
		formattable string.

	Raises
	------
	ValueError
		If the influence functions mode basis does not contain a grid.
	'''
	import matplotlib.pyplot as plt

	if influence_functions.grid is None:
		raise ValueError('The influence functions mode basis must contain a grid to calcuate centroids.')

	grid = influence_functions.grid.as_('cartesian')
	x, y = grid.coords

	# Center the labels unless overridden by the user.
	kwargs = {'verticalalignment': 'center', 'horizontalalignment': 'center'}
	kwargs.update(text_kwargs)

	for i, act in enumerate(influence_functions):
		x_pos = (act * x).sum() / act.sum()
		y_pos = (act * y).sum() / act.sum()
		pos = (x_pos, y_pos)

		plt.annotate(label_format.format(i), xy=pos, **kwargs)
