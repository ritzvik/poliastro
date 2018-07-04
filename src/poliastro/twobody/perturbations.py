from astropy.time import Time
import numpy as np
from poliastro.util import norm
from poliastro.twobody import Orbit
import astropy.units as u
from poliastro.jit import jit


def J2_perturbation(t0, state, k, J2, R):
    """Calculates J2_perturbation acceleration (km/s2)

    .. versionadded:: 0.9.0

    Parameters
    ----------
    t0 : float
        Current time (s)
    state : numpy.ndarray
        Six component state vector [x, y, z, vx, vy, vz] (km, km/s).
    k : float
        gravitational constant, (km^3/s^2)
    J2: float
        obliteness factor
    R: float
        attractor radius

    Notes
    -----
    The J2 accounts for the obliteness of the attractor. The formula is given in
    Howard Curtis, (12.30)

    """
    r_vec = state[:3]
    r = norm(r_vec)

    factor = (3.0 / 2.0) * k * J2 * (R ** 2) / (r ** 5)

    a_x = 5.0 * r_vec[2] ** 2 / r ** 2 - 1
    a_y = 5.0 * r_vec[2] ** 2 / r ** 2 - 1
    a_z = 5.0 * r_vec[2] ** 2 / r ** 2 - 3
    return np.array([a_x, a_y, a_z]) * r_vec * factor


def J3_perturbation(t0, state, k, J3, R):
    """Calculates J3_perturbation acceleration (km/s2)

    Parameters
    ----------
    t0 : float
        Current time (s)
    state : numpy.ndarray
        Six component state vector [x, y, z, vx, vy, vz] (km, km/s).
    k : float
        gravitational constant, (km^3/s^2)
    J3: float
        obliteness factor
    R: float
        attractor radius

    Notes
    -----
    The J3 accounts for the obliteness of the attractor. The formula is given in
    Howard Curtis, problem 12.8

    """
    r_vec = state[:3]
    r = norm(r_vec)

    factor = (1.0 / 2.0) * k * J3 * (R ** 3) / (r ** 5)
    cos_phi = r_vec[2] / r

    a_x = 5.0 * r_vec[0] / r * (7.0 * cos_phi ** 3 - 3.0 * cos_phi)
    a_y = 5.0 * r_vec[1] / r * (7.0 * cos_phi ** 3 - 3.0 * cos_phi)
    a_z = 3.0 * (35.0 / 3.0 * cos_phi ** 4 - 10.0 * cos_phi ** 2 + 1)
    return np.array([a_x, a_y, a_z]) * factor


def atmospheric_drag(t0, state, k, R, C_D, A, m, H0, rho0):
    """Calculates atmospheric drag acceleration (km/s2)

    .. versionadded:: 0.9.0

    Parameters
    ----------
    t0 : float
        Current time (s)
    state : numpy.ndarray
        Six component state vector [x, y, z, vx, vy, vz] (km, km/s).
    k : float
        gravitational constant, (km^3/s^2)
    C_D: float
        dimensionless drag coefficient ()
    A: float
        frontal area of the spacecraft (km^2)
    m: float
        mass of the spacecraft (kg)
    H0 : float
        atmospheric scale height, (km)
    rho0: float
        the exponent density pre-factor, (kg / m^3)

    Notes
    -----
    This function provides the acceleration due to atmospheric drag. We follow
    Howard Curtis, section 12.4
    the atmospheric density model is rho(H) = rho0 x exp(-H / H0)

    """
    H = norm(state[:3])

    v_vec = state[3:]
    v = norm(v_vec)
    B = C_D * A / m
    rho = rho0 * np.exp(-(H - R) / H0)

    return -(1.0 / 2.0) * rho * B * v * v_vec


def third_body(t0, state, k, k_third, third_body):
    """Calculates 3rd body acceleration (km/s2)

    Parameters
    ----------
    t0 : float
        Current time (s)
    state : numpy.ndarray
        Six component state vector [x, y, z, vx, vy, vz] (km, km/s).
    k : float
        gravitational constant, (km^3/s^2)
    third_body: a callable object returning the position of 3rd body
        third body that causes the perturbation
    """

    body_r = third_body(t0)
    delta_r = body_r - state[:3]
    return k_third * delta_r / norm(delta_r) ** 3 - k_third * body_r / norm(body_r) ** 3


@jit
def shadow_function(r_sat, r_sun, R):
    """Determines whether the satellite is in attractor's shadow,
       uses algorithm 12.3 from Howard Curtis

    Parameters
    ----------
    r_sat : numpy.ndarray
        position of the satellite in the frame of attractor (km)
    r_sun : numpy.ndarray
        position of star in the frame of attractor (km)
    R : float
        radius of body (attractor) that creates shadow (km)
    """

    r_sat_norm = np.sqrt(np.sum(r_sat ** 2))
    r_sun_norm = np.sqrt(np.sum(r_sun ** 2))

    theta = np.arccos(np.dot(r_sat, r_sun) / r_sat_norm / r_sun_norm)
    theta_1 = np.arccos(R / r_sat_norm)
    theta_2 = np.arccos(R / r_sun_norm)

    return theta < theta_1 + theta_2


def radiation_pressure(t0, state, k, R, C_R, A, m, Wdivc_s, star):
    """Calculates radiation pressure acceleration (km/s2)

    Parameters
    ----------
    t0 : float
        Current time (s)
    state : numpy.ndarray
        Six component state vector [x, y, z, vx, vy, vz] (km, km/s).
    k : float
        gravitational constant, (km^3/s^2)
    R : float
        radius of the attractor
    C_R: float
        dimensionless radiation pressure coefficient, 1 < C_R < 2 ()
    A: float
        effective spacecraft area (km^2)
    m: float
        mass of the spacecraft (kg)
    Wdivc_s : float
        total star emitted power divided by the speed of light (W * s / km)
    star: a callable object returning the position of star in attractor frame
        star position
    Notes
    -----
    This function provides the acceleration due to star light pressure. We follow
    Howard Curtis, section 12.9

    """

    r_star = star(t0)
    r_sat = state[:3]
    P_s = Wdivc_s / (norm(r_star) ** 2)

    nu = float(shadow_function(r_sat, r_star, R))
    return -nu * P_s * (C_R * A / m) * r_star / norm(r_star)
