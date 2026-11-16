"""Plotting helpers and example functions for the gradient descent notebooks.

Every plot is static: run the cell again with other parameters (learning rate,
number of iterations, starting point) to see how gradient descent behaves.
"""
import numpy as np
import matplotlib.pyplot as plt

BLUE, CORAL, GREEN, MUTED = "#3B47C4", "#E4572E", "#2E7D4F", "#666666"


# ------------------------------------------------------------ example functions

def f_example_2(x):
    """One variable, several minima."""
    return (np.exp(x) - np.log(x)) * np.sin(2 * np.pi * x)


def dfdx_example_2(x):
    return ((np.exp(x) - 1 / x) * np.sin(2 * np.pi * x)
            + (np.exp(x) - np.log(x)) * np.cos(2 * np.pi * x) * 2 * np.pi)


def f_example_3(x, y):
    """Two variables, one global minimum."""
    return 85 + 0.1 * (-(x - 6) * x**2 * y**3 / 9 + 2 * (x - 6) * x**2 * y**2 / 3)


def dfdx_example_3(x, y):
    return 0.1 / 3 * x * y**2 * (2 - y / 3) * (3 * x - 12)


def dfdy_example_3(x, y):
    return 0.1 / 3 * (x - 6) * x**2 * y * (4 - y)


def _bumps(x, y):
    return (10 / (3 + 3 * (x - 0.5)**2 + 3 * (y - 0.5)**2),
            2 / (1 + 2 * (x - 3)**2 + 2 * (y - 1.5)**2),
            3 / (1 + 0.5 * (x - 3.5)**2 + 0.5 * (y - 4)**2))


def f_example_4(x, y):
    """Two variables, one global minimum and two local minima."""
    a, b, c = _bumps(x, y)
    return 10 - (a + b + c)


def dfdx_example_4(x, y):
    return (6 * (x - 0.5) * 10 / (3 + 3 * (x - 0.5)**2 + 3 * (y - 0.5)**2)**2
            + 4 * (x - 3) * 2 / (1 + 2 * (x - 3)**2 + 2 * (y - 1.5)**2)**2
            + 1 * (x - 3.5) * 3 / (1 + 0.5 * (x - 3.5)**2 + 0.5 * (y - 4)**2)**2)


def dfdy_example_4(x, y):
    return (6 * (y - 0.5) * 10 / (3 + 3 * (x - 0.5)**2 + 3 * (y - 0.5)**2)**2
            + 4 * (y - 1.5) * 2 / (1 + 2 * (x - 3)**2 + 2 * (y - 1.5)**2)**2
            + 1 * (y - 4) * 3 / (1 + 0.5 * (x - 3.5)**2 + 0.5 * (y - 4)**2)**2)


# ------------------------------------------------------------ one variable

def plot_f(x_range, y_range, f, ox_position=0.0):
    """Plot f on x_range, with the horizontal axis drawn at height ox_position."""
    x = np.linspace(*x_range, 500)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, f(x), color=BLUE, lw=2.5)
    ax.axhline(ox_position, color=MUTED, lw=1)
    ax.set(xlim=x_range, ylim=y_range, xlabel="x", ylabel="f(x)")
    ax.grid(alpha=0.3)
    plt.show()


def _path_1d(dfdx, x_0, learning_rate, num_iterations, tol=1e-6):
    path = [x_0]
    for _ in range(num_iterations):
        x_new = path[-1] - learning_rate * dfdx(path[-1])
        if not np.isfinite(x_new):
            break
        path.append(x_new)
        if abs(path[-1] - path[-2]) < tol:
            break
    return np.array(path)


def gradient_descent_one_variable(x_range, y_range, f, dfdx, gd, num_iterations, learning_rate,
                                  x_0, ox_position=0.0, t_position=None):
    """Run gradient descent from x_0 and draw every step on the curve of f.

    `gd` is your own gradient_descent(dfdx, x, learning_rate, num_iterations) function:
    its result is printed and marked on the plot.
    """
    path = _path_1d(dfdx, x_0, learning_rate, num_iterations)
    x_min = gd(dfdx, x_0, learning_rate, num_iterations)
    x = np.linspace(*x_range, 500)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, f(x), color=BLUE, lw=2.5, label="f(x)")
    ax.axhline(ox_position, color=MUTED, lw=1)
    inside = (path >= x_range[0]) & (path <= x_range[1])
    p = path[inside]
    ax.plot(p, f(p), "-o", color=CORAL, ms=5, lw=1.2, alpha=0.9, label="gradient descent steps")
    ax.plot(path[0], f(path[0]), "o", color=GREEN, ms=11, label=f"start x₀ = {x_0}")
    if x_range[0] <= x_min <= x_range[1]:
        ax.plot(x_min, f(x_min), "*", color=CORAL, ms=18, label=f"result x = {x_min:.4f}")
    else:
        ax.text(0.5, 0.92, "The steps left the plotted range: the method diverged.", transform=ax.transAxes,
                ha="center", color=CORAL, fontweight="bold")
    ax.set(xlim=x_range, ylim=y_range, xlabel="x", ylabel="f(x)",
           title=f"learning rate = {learning_rate}, iterations = {num_iterations}")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.3)
    plt.show()
    print(f"Gradient descent result: x_min = {x_min}")


# ------------------------------------------------------------ two variables

def _grid(x_range, y_range, f, n=120):
    X, Y = np.meshgrid(np.linspace(*x_range, n), np.linspace(*y_range, n))
    return X, Y, f(X, Y)


def plot_f_cont_and_surf(x_range, y_range, z_range, f, cmap="coolwarm", view=None):
    """Contour plot (left) and 3D surface (right) of f(x, y)."""
    view = view or {"azim": -60, "elev": 28}
    X, Y, Z = _grid(x_range, y_range, f)
    fig = plt.figure(figsize=(12, 5))
    ax1 = fig.add_subplot(1, 2, 1)
    cs = ax1.contourf(X, Y, Z, levels=30, cmap=cmap)
    ax1.contour(X, Y, Z, levels=30, colors="white", linewidths=0.4, alpha=0.6)
    fig.colorbar(cs, ax=ax1, shrink=0.85)
    ax1.set(xlabel="x", ylabel="y", title="contour plot", aspect="equal")
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    ax2.plot_surface(X, Y, Z, cmap=cmap, linewidth=0, alpha=0.9)
    ax2.view_init(**view)
    ax2.set(xlabel="x", ylabel="y", zlabel="f(x, y)", zlim=z_range, title="surface")
    plt.tight_layout()
    plt.show()


def _path_2d(dfdx, dfdy, x_0, y_0, learning_rate, num_iterations, tol=1e-6):
    path = [(x_0, y_0)]
    for _ in range(num_iterations):
        x, y = path[-1]
        nxt = (x - learning_rate * dfdx(x, y), y - learning_rate * dfdy(x, y))
        if not np.all(np.isfinite(nxt)):
            break
        path.append(nxt)
        if np.hypot(nxt[0] - x, nxt[1] - y) < tol:
            break
    return np.array(path)


def gradient_descent_two_variables(x_range, y_range, z_range, f, dfdx, dfdy, gd, num_iterations,
                                   learning_rate, x_0, y_0, *_layout, cmap="coolwarm", view=None):
    """Run gradient descent from (x_0, y_0) and draw every step on the contour and surface plots.

    `gd` is your own gradient_descent(dfdx, dfdy, x, y, learning_rate, num_iterations) function.
    Extra positional arguments (text positions of the interactive version) are accepted and ignored.
    """
    view = view or {"azim": -60, "elev": 28}
    path = _path_2d(dfdx, dfdy, x_0, y_0, learning_rate, num_iterations)
    x_min, y_min = gd(dfdx, dfdy, x_0, y_0, learning_rate, num_iterations)
    X, Y, Z = _grid(x_range, y_range, f)
    fig = plt.figure(figsize=(12, 5))
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.contourf(X, Y, Z, levels=30, cmap=cmap)
    ax1.contour(X, Y, Z, levels=30, colors="white", linewidths=0.4, alpha=0.6)
    ax1.plot(path[:, 0], path[:, 1], "-o", color="black", ms=4, lw=1.2)
    ax1.plot(x_0, y_0, "o", color=GREEN, ms=11, label=f"start ({x_0}, {y_0})")
    ax1.plot(x_min, y_min, "*", color=CORAL, ms=18, label=f"result ({x_min:.3f}, {y_min:.3f})")
    ax1.set(xlim=x_range, ylim=y_range, xlabel="x", ylabel="y", aspect="equal",
            title=f"learning rate = {learning_rate}, iterations = {num_iterations}")
    ax1.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    ax2.plot_surface(X, Y, Z, cmap=cmap, linewidth=0, alpha=0.75)
    ax2.plot(path[:, 0], path[:, 1], f(path[:, 0], path[:, 1]), "-o", color="black", ms=3, lw=1.2, zorder=10)
    ax2.view_init(**view)
    ax2.set(xlabel="x", ylabel="y", zlabel="f(x, y)", zlim=z_range, title="surface")
    plt.tight_layout()
    plt.show()
    print(f"Gradient descent result: x_min, y_min = {x_min}, {y_min}")
