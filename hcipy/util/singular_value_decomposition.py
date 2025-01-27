import numpy as np
import scipy.sparse
import scipy.sparse.linalg

from ..mode_basis import ModeBasis

class SVD(object):
	'''The Singular Value Decomposition for the provided matrix.

	This class wraps two versions of the SVD in numpy and scipy, and provides
	easy access to singular modes (as mode bases) and allows for calculation
	of the SVD for a limited number of modes.

	When a sparse matrix is passed, and no number of modes is given, all but one
	mode will be calculated. The reason is that the sparse SVD implementation in Scipy
	doesn't allow calculation of all modes. If all modes are required, the user
	must pass a densified version of the matrix (ie. `matrix.toarray()`).

	Parameters
	----------
	matrix : ndarray or any sparse matrix
		The matrix on which to perform the SVD.
	num_modes : int or None
		The number of singular values and modes to calculate. If this is None,
		and `matrix` is not sparse, all modes will be computed. If this is None and
		`matrix` is sparse, all but one mode will be computed.
	'''
	def __init__(self, matrix=None, num_modes=None, M=None):
		if matrix is None:
			import warnings
			warnings.warn('Deprecated: use "matrix" instead of "M".', DeprecationWarning, stacklevel=2)
			matrix = M

		if matrix is None:
			raise ValueError('You need to supply a matrix.')

		self._matrix = matrix
		self._num_modes = num_modes

		is_sparse = scipy.sparse.issparse(matrix)

		if is_sparse and self.num_modes is None:
			self._num_modes = min(matrix.shape) - 1

		if self.num_modes is None:
			self._svd = np.linalg.svd(matrix, full_matrices=False)
		else:
			self._svd = scipy.sparse.linalg.svds(matrix, int(self.num_modes))

	@property
	def left_singular_modes(self):
		'''The left singular modes of the matrix, as a ModeBasis.
		'''

		return ModeBasis([m for m in self.U.conj().T])

	@property
	def right_singular_modes(self):
		'''The right singular modes of the matrix, as a ModeBasis.
		'''
		from ..mode_basis import ModeBasis

		return ModeBasis([m for m in self.Vt.conj()])

	@property
	def singular_values(self):
		'''The singular values of the matrix.
		'''
		return self.S

	@property
	def U(self):  # noqa: N802
		'''The U matrix of the SVD.
		'''
		return self.svd[0]

	@property
	def S(self):  # noqa: N802
		'''The singular values of the matrix.
		'''
		return self.svd[1]

	@property
	def Vt(self):  # noqa: N802
		'''The V^T matrix of the SVD.
		'''
		return self.svd[2]

	def __getitem__(self, i):
		'''The raw U, S, and V^T matrices of the SVD by index.
		'''
		return self.svd[i]

	@property
	def svd(self):
		'''The raw U, S, and V^T matrices of the SVD as a tuple.
		'''
		return self._svd

	@property
	def num_modes(self):
		'''The number of singular modes that were calculated in this SVD.
		'''
		return self._num_modes

	@property
	def matrix(self):
		'''The matrix for which the SVD was calculated.
		'''
		return self._matrix

	@property
	def M(self):  # noqa: N802
		import warnings
		warnings.warn('Deprecated: use "matrix" instead of "M".', DeprecationWarning, stacklevel=2)
		return self.matrix
