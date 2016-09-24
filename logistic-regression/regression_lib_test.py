# Unit testing for regression_lib.
#
# Eli Bendersky (http://eli.thegreenplace.net)
# This code is in the public domain
from __future__ import print_function
import numpy as np
import unittest

from regression_lib import *
from timer import Timer


def hinge_loss_simple(X, y, theta, reg_beta=0.0):
    """Unvectorized version of hinge loss.

    Closely follows the formulae without vectorizing optimizations, so it's
    easier to understand and correlate to the math.
    """
    k, n = X.shape
    loss = 0
    dtheta = np.zeros_like(theta)
    for i in range(k):
        # The contribution of each data item.
        x_i = X[i, :]
        y_i = y[i, 0]
        m_i = x_i.dot(theta).flat[0] * y_i  # margin for i
        loss += np.maximum(0, 1 - m_i) / k
        for j in range(n):
            # This data item contributes gradients to each of the theta
            # components.
            dtheta[j, 0] += -y_i * x_i[j] / k if m_i < 1 else 0

    # Add regularization.
    loss += np.dot(theta.T, theta) * reg_beta / 2
    for j in range(n):
        dtheta[j, 0] += reg_beta * theta[j, 0]

    return loss, dtheta


def cross_entropy_loss_binary_simple(X, y, theta, reg_beta=0.0):
    """Unvectorized cross-entropy loss for binary classification."""
    k, n = X.shape
    yhat_prob = predict_logistic_probability(X, theta)
    loss = np.mean(np.where(y == 1,
                            -np.log(yhat_prob),
                            -np.log(1 - yhat_prob)))
    loss += np.dot(theta.T, theta) * reg_beta / 2

    dtheta = np.zeros_like(theta)
    for i in range(k):
        for j in range(n):
            if y[i] == 1:
                dtheta[j, 0] += (yhat_prob[i, 0] - 1 ) * X[i, j]
            else:
                dtheta[j, 0] += yhat_prob[i, 0] * X[i, j]
    dtheta = dtheta / k + reg_beta * theta
    return loss, dtheta


def softmax_gradient_simple(z):
    """Unvectorized computation of the gradient of softmax.

    z: (N, 1) column array of input values.

    Returns dz (N, N) the Jacobian matrix of softmax(z) at the given z. dz[i, j]
    is DjSi - the partial derivative of Si w.r.t. input j.
    """
    Sz = softmax(z)
    N = z.shape[0]
    dz = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            dz[i, j] = Sz[i, 0] * (np.float32(i == j) - Sz[j, 0])
    return dz


def eval_numerical_gradient(f, x, verbose=False, h=1e-5):
    """A naive implementation of numerical gradient of f at x.

    f: function taking a single array argument and returning a scalar.
    x: array starting point for evaluation.

    Based on http://cs231n.github.io/assignments2016/assignment1/, with a
    bit of cleanup.

    Returns a numerical gradient
    """
    grad = np.zeros_like(x)
    # iterate over all indexes in x
    it = np.nditer(x, flags=['multi_index'], op_flags=['readwrite'])
    while not it.finished:
        ix = it.multi_index
        oldval = x[ix]
        x[ix] = oldval + h
        fxph = f(x) # evalute f(x + h)
        x[ix] = oldval - h
        fxmh = f(x) # evaluate f(x - h)
        x[ix] = oldval # restore

        # compute the partial derivative with centered formula
        grad[ix] = (fxph - fxmh) / (2 * h)
        if verbose:
            print(ix, grad[ix])
        it.iternext()
    return grad


class TestSquareLoss(unittest.TestCase):
    def test_simple_vs_numerical_noreg(self):
        X = np.array([
            [0.1, 0.2, -0.3],
            [0.6, -0.5, 0.1],
            [0.6, -0.4, 0.3],
            [-0.2, 0.4, 2.2]])
        theta = np.array([
            [0.2],
            [-1.5],
            [2.35]])
        y = np.array([
            [1],
            [-1],
            [1],
            [1]])

        loss, grad = square_loss(X, y, theta)
        gradnum = eval_numerical_gradient(
            lambda theta: square_loss(X, y, theta)[0], theta, h=1e-8)
        np.testing.assert_allclose(grad, gradnum, rtol=1e-4)

    def test_simple_vs_numerical_withreg(self):
        # Same test with a regularization factor.
        X = np.array([
                [0.1, 0.2, -0.3],
                [0.6, -0.5, 0.1],
                [0.6, -0.4, 0.3],
                [-0.2, 0.4, 2.2]])
        theta = np.array([
            [0.2],
            [-1.5],
            [2.35]])
        y = np.array([
            [1],
            [-1],
            [1],
            [1]])

        beta = 0.1
        loss, grad = square_loss(X, y, theta, reg_beta=beta)
        gradnum = eval_numerical_gradient(
            lambda theta: square_loss(X, y, theta, reg_beta=beta)[0],
            theta, h=1e-8)
        np.testing.assert_allclose(grad, gradnum, rtol=1e-4)


class TestHingeLoss(unittest.TestCase):
    def checkHingeLossSimpleVsVec(self, X, y, theta, reg_beta=0.0):
        loss_vec, dtheta_vec = hinge_loss(X, y, theta, reg_beta)
        loss_simple, dtheta_simple = hinge_loss_simple(X, y, theta, reg_beta)
        self.assertAlmostEqual(loss_vec, loss_simple)
        np.testing.assert_allclose(dtheta_vec, dtheta_simple)

    def test_hinge_loss_small(self):
        X = np.array([
                [0.1, 0.2, -0.3],
                [0.6, -0.5, 0.1],
                [0.6, -0.4, 0.3],
                [-0.2, 0.4, 2.2]])
        theta = np.array([
            [0.2],
            [-1.5],
            [2.35]])
        y = np.array([
            [1],
            [-1],
            [1],
            [1]])
        # Without regularization.
        self.checkHingeLossSimpleVsVec(X, y, theta, reg_beta=0.0)

        # With regularization.
        beta = 0.05
        self.checkHingeLossSimpleVsVec(X, y, theta, reg_beta=beta)

        # With regularization, compare to numerical gradient.
        loss, grad = hinge_loss(X, y, theta, reg_beta=beta)
        gradnum = eval_numerical_gradient(
            lambda theta: hinge_loss(X, y, theta, reg_beta=beta)[0],
            theta, h=1e-8)
        np.testing.assert_allclose(grad, gradnum, rtol=1e-4)

    def test_hinge_loss_larger_random(self):
         np.random.seed(1)
         k, n = 20, 5
         X = np.random.uniform(low=0, high=1, size=(k,n))
         theta = np.random.randn(n, 1)
         y = np.random.choice([-1, 1], size=(k,1))
         self.checkHingeLossSimpleVsVec(X, y, theta)

    def test_hinge_loss_even_larger_random(self):
         np.random.seed(1)
         k, n = 350, 15
         X = np.random.uniform(low=0, high=1, size=(k,n))
         theta = np.random.randn(n, 1) * 2
         y = np.random.choice([-1, 1], size=(k,1))
         self.checkHingeLossSimpleVsVec(X, y, theta)


class TestCrossEntropyBinaryLoss(unittest.TestCase):
    def checkXentLossSimpleVsVec(self, X, y, theta, reg_beta=0.0):
        loss_vec, dtheta_vec = cross_entropy_loss_binary(X, y, theta, reg_beta)
        loss_simple, dtheta_simple = cross_entropy_loss_binary_simple(
            X, y, theta, reg_beta)
        self.assertAlmostEqual(loss_vec, loss_simple)
        np.testing.assert_allclose(dtheta_vec, dtheta_simple)

    def test_xent_no_overflow_from_0(self):
        X = np.array([[100, 200, 300]])
        theta = np.array([
            [-1.0],
            [-1.1],
            [-1.2]])
        y = np.array([[1]])
        loss, grad = cross_entropy_loss_binary(X, y, theta)
        self.assertTrue(np.isfinite(loss))

    def test_xent_loss_oneitem(self):
        X = np.array([[0.1, 0.2, -0.3]])
        theta = np.array([
            [0.2],
            [-1.5],
            [2.35]])
        y = np.array([[1]])

        self.checkXentLossSimpleVsVec(X, y, theta, reg_beta=0.0)
        self.checkXentLossSimpleVsVec(X, y, theta, reg_beta=0.1)

        loss, grad = cross_entropy_loss_binary_simple(X, y, theta, reg_beta=0.1)
        gradnum = eval_numerical_gradient(
            lambda theta: cross_entropy_loss_binary_simple(X, y, theta,
                                                           reg_beta=0.1)[0],
            theta, h=1e-8)
        np.testing.assert_allclose(grad, gradnum, rtol=1e-4)

    def test_xent_loss_small(self):
        X = np.array([
                [0.1, 0.2, -0.3],
                [0.6, -0.5, 0.1],
                [0.6, -0.4, 0.3],
                [-0.2, 0.4, 2.2]])
        theta = np.array([
            [0.2],
            [-1.5],
            [2.35]])
        y = np.array([
            [1],
            [-1],
            [1],
            [1]])

        self.checkXentLossSimpleVsVec(X, y, theta, reg_beta=0.0)
        self.checkXentLossSimpleVsVec(X, y, theta, reg_beta=0.1)

        loss, grad = cross_entropy_loss_binary_simple(X, y, theta, reg_beta=0.1)
        gradnum = eval_numerical_gradient(
            lambda theta: cross_entropy_loss_binary_simple(X, y,
                                                           theta,
                                                           reg_beta=0.1)[0],
            theta, h=1e-8)
        np.testing.assert_allclose(grad, gradnum, rtol=1e-4)

    def test_xent_loss_larger(self):
        X = np.array([
                [0.1, 0.2, -0.3, 1.2],
                [0.6, -0.5, 0.1, -0.1],
                [0.6, -0.4, 0.3, 0.0],
                [0.4, -0.3, 0.3, 0.0],
                [-0.2, 0.4, 2.2, 0.7]])
        theta = np.array([
            [0.2],
            [0.3],
            [-1.5],
            [2.35]])
        y = np.array([
            [1],
            [-1],
            [-1],
            [1],
            [1]])

        self.checkXentLossSimpleVsVec(X, y, theta, reg_beta=0.0)
        self.checkXentLossSimpleVsVec(X, y, theta, reg_beta=0.1)

        loss, grad = cross_entropy_loss_binary_simple(X, y, theta, reg_beta=0.1)
        gradnum = eval_numerical_gradient(
            lambda theta: cross_entropy_loss_binary_simple(X, y,
                                                           theta,
                                                           reg_beta=0.1)[0],
            theta, h=1e-8)
        np.testing.assert_allclose(grad, gradnum, rtol=1e-4)


class TestSoftmaxGradient(unittest.TestCase):
    def checkSoftmaxGradientSimpleVsVec(self, z):
        dz_vec = softmax_gradient(z)
        dz_simple = softmax_gradient_simple(z)
        np.testing.assert_allclose(dz_vec, dz_simple)

    def test_simple_vs_numerical(self):
        z = np.array([
            [0.2],
            [0.9],
            [-0.3],
            [-0.5]])
        grad = softmax_gradient_simple(z)

        for i in range(z.shape[0]):
            # Compute numerical gradient for output Si w.r.t. all inputs
            # j=0...N-1; this computes one row of the jacobian.
            gradnum = eval_numerical_gradient(lambda z: softmax(z)[i, 0], z)
            np.testing.assert_allclose(grad[i, :].flatten(),
                                       gradnum.flatten(),
                                       rtol=1e-4)

    def test_simple_vs_vectorized_small(self):
        z = np.array([
            [0.2],
            [0.9]])
        self.checkSoftmaxGradientSimpleVsVec(z)

    def test_simple_vs_vectorized_larger(self):
        z = np.array([
            [1.2],
            [0],
            [-0.01],
            [2.12],
            [-0.9]])
        self.checkSoftmaxGradientSimpleVsVec(z)

    def test_simple_vs_vectorized_random(self):
        z = np.random.uniform(low=-2.0, high=2.0, size=(100,1))
        self.checkSoftmaxGradientSimpleVsVec(z)


class TestPredictBinary(unittest.TestCase):
    def test_simple(self):
        # Make sure positive gets +1, negative -1 and zero also gets +1.
        theta = np.array([[2], [-1]])
        X = np.array([
            [7, 3],
            [2, 4],
            [-1, 1]])
        yhat = predict_binary(X, theta)
        np.testing.assert_equal(yhat, np.array([[1], [1], [-1]]))


class TestPredictLogisticProbability(unittest.TestCase):
    def test_close_to_zero(self):
        # For very large negative z, predicted probability is close to zero.
        X = np.array([
            [10.0, 20.0],
            [20.0, 30.0],
            [30.0, 40.0]])
        theta = np.array([[-5], [-6]])
        p = predict_logistic_probability(X, theta)
        np.testing.assert_allclose(p, np.zeros_like(p), atol=1e-8)

    def test_close_to_one(self):
        # For very large positive z, predicted probability is close to one.
        X = np.array([
            [10.0, 20.0],
            [20.0, 30.0],
            [30.0, 40.0]])
        theta = np.array([[3], [4]])
        p = predict_logistic_probability(X, theta)
        np.testing.assert_allclose(p, np.ones_like(p), atol=1e-8)

    def test_half(self):
        # For z=0 we get probability 0.5
        X = np.array([
            [10.0, 20.0],
            [20.0, 40.0],
            [40.0, 80.0]])
        theta = np.array([[-2], [1]])
        p = predict_logistic_probability(X, theta)
        np.testing.assert_allclose(p, np.full(p.shape, 0.5))


def tuplize_2d_array(arr):
    """Returns a list of tuples, each tuple being one row of arr."""
    return [tuple(row) for row in arr]


class TestGenerateBatch(unittest.TestCase):
    def test_simple(self):
        X = np.array([
            [10.0, 20.0],
            [12.0, 22.0],
            [13.0, 24.0],
            [20.0, 40.0],
            [40.0, 80.0]])
        y = np.array([[3], [4], [5], [9], [10]])

        Xt = tuplize_2d_array(X)
        yt = tuplize_2d_array(y)

        for _ in range(10):
            X_batch, y_batch = generate_batch(X, y, batch_size=3)
            Xbt = tuplize_2d_array(X_batch)
            ybt = tuplize_2d_array(yt)

            # Make sure the items in Xbt are unique and each comes from Xt.
            self.assertEqual(len(set(Xbt)), len(Xbt))
            for row in Xbt:
                self.assertIn(row, Xt)

            # ... same for yt.
            self.assertEqual(len(set(ybt)), len(ybt))
            for row in ybt:
                self.assertIn(row, yt)


class TestGradientDescent(unittest.TestCase):
    def test_applies_dtheta(self):
        # Tests that gradient_descent applies dtheta to an internal theta as
        # expected
        k, n = 40, 3
        dtheta = np.arange(1, n + 1).reshape(-1, 1)
        learning_rate = 0.1
        def lossfunc(X, y, theta):
            return 0, dtheta

        gi = gradient_descent(
                X=np.ones((k, n)),
                y=np.ones((k, 1)),
                lossfunc=lossfunc,
                nsteps=10,
                learning_rate=learning_rate)

        # Take note of initial theta: copy it since it's modified inside
        # gradient_descent.
        init_theta, _ = gi.next()
        init_theta = init_theta.copy()

        for i, (theta, _) in enumerate(gi, 1):
            expected = init_theta - i * learning_rate * dtheta
            np.testing.assert_allclose(expected, theta)


class TestFeatureNormalize(unittest.TestCase):
    def test_simple(self):
        X = np.array([
            [3, 6],
            [5, 14]])

        X_norm, mu, sigma = feature_normalize(X)
        np.testing.assert_equal(mu, np.array([4, 10]))
        np.testing.assert_equal(sigma, np.array([1, 4]))
        np.testing.assert_equal(X_norm, np.array([[-1, -1], [1, 1]]))

    def test_with_nans(self):
        # stddev of second feature is 0, so we'd get nan's if feature_normalize
        # wasn't fixing them.
        X = np.array([
            [3, 6],
            [5, 6]])
        X_norm, mu, sigma = feature_normalize(X)
        #print(feature_normalize(X))
        np.testing.assert_equal(mu, np.array([4, 6]))
        np.testing.assert_equal(sigma, np.array([1, 1]))
        np.testing.assert_equal(X_norm, np.array([[-1, 0], [1, 0]]))


if __name__ == '__main__':
    unittest.main()
