from __future__ import division

__all__ = ['diff_rot']
import numpy as np
import datetime
from sunpy.time import parse_time, julian_day
from sunpy.wcs import convert_hcc_hg

__author__ = ["Jose Ivan Campos Rozo", "Stuart Mumford", "Jack Ireland"]
__all__ = ['diff_rot', 'sun_pos']


def diff_rot(ddays, latitude, rot_type='howard', frame_time='sidereal'):
    """
    This function computes the change in longitude over days in degrees.

    Parameters
    -----------
    ddays: float or timedelta
        Number of days to rotate over, or timedelta object.

    latitude: float or array-like
        heliographic coordinate latitude in Degrees.

    rot_type: {'howard' | 'snodgrass' | 'allen'}
        howard: Use values for small magnetic features from Howard et al.
        snodgrass: Use Values from Snodgrass et. al
        allen: Use values from Allen, Astrophysical Quantities, and simplier
                equation.

    frame_time: {'sidereal' | 'synodic'}
        Choose 'type of day' time reference frame.

    Returns:
    -------
    longditude_delta: ndarray
        The change in longitude over days (units=degrees)

    See Also
    --------
    IDL code equavalent:
        http://hesperia.gsfc.nasa.gov/ssw/gen/idl/solar/diff_rot.pro

    Howard rotation:
        http://adsabs.harvard.edu/abs/1990SoPh..130..295H

    A review of rotation parameters (including Snodgrass values):
        http://link.springer.com/article/10.1023%2FA%3A1005226402796

    Examples
    --------
    Default rotation calculation over two days at 30 degrees latitude:
        rotation = diff_rot(2, 30)
    Default rotation over two days for a number of latitudes:
        rotation = diff_rot(2, np.linspace(-70, 70, 20))
    With rotation type 'allen':
        rotation = diff_rot(2, np.linspace(-70, 70, 20), 'allen')
    """

    if not isinstance(ddays, datetime.timedelta):
        delta = datetime.timedelta(days=ddays)

    delta_seconds = delta.total_seconds()
    delta_days = delta_seconds / 24 / 3600

    sin2l = (np.sin(np.deg2rad(latitude)))**2
    sin4l = sin2l**2

    rot_params = {'howard': [2.894, -0.428, -0.370],
                  'snodgrass': [2.851, -0.343, -0.474]
                  }

    if rot_type not in ['howard', 'allen', 'snodgrass']:
        raise ValueError("""rot_type must equal one of
                        { 'howard' | 'allen' | 'snodgrass' }""")

    elif rot_type == 'allen':
        rotation_deg = delta_days * (14.44 - (3.0 * sin2l))

    else:
        A, B, C = rot_params[rot_type]

        #This is in micro-radians / sec
        rotation_rate = A + B * sin2l + C * sin4l
        rotation_deg = rotation_rate * 1e-6  * delta_seconds / np.deg2rad(1)

    if frame_time == 'synodic':
        rotation_deg -= 0.9856 * delta_days

    return np.round(rotation_deg, 4)


def rot_xy(x, y, date=datetime.datetime.utcnow(), **kwargs):
    """ Get a solar rotated position for a given time interval.

    Parameters
    -----------
    x: float or numpy ndarray
        x-locations.

    y: float or numpy ndarray
        y-locations.

    interval: Time interval in seconds; positive (negative) values leads to '
              forward (backward) rotation.

    date: date/time at which the sun position is calculated; can be in any
          format accepted by parse_time. If missing, current date/time is
          assumed.
;
; OUTPUTS:
;       RESULT - A (Mx2) array representing rotated positions in arcsecs,
;                RESULT(*,0) being X position and RESULT(*,1) Y position;
;                where M is number of elements in XX (and in YY).
;                If an error occurs, [-9999,-9999] will be returned.
;
;                If OFFLIMB = 1 after the call, there must be some
;                points rotated to the back of the sun. The points remain
;                visible can be determined by RESULT(INDEX,*), and
;                off-limb points will have the value of (-9999, -9999).
;
; OPTIONAL OUTPUTS:
;       None.
;
; KEYWORDS:
;       DATE    - Date/time at which the sun position is calculated; can
;                 be in any UTC format. If missing, current date/time is
;                 assumed.
;       TSTART  - Date/time to which XX and YY are referred; can be in
;                 any acceptable time format. Must be supplied if
;                 INTERVAL is not passed
;       TEND    - Date/time at which XX and YY will be rotated to; can be
;                 in any acceptable time format. If needed but missing,
;                 current time is assumed

;       OFFLIMB - A named variable indicating whether any rotated
;                 point is off the limb (1) or not (0). When OFFLIMB
;                 is 1, the points still remaining visible (inside the limb)
;                 will be those whose indices are INDEX (below)
;       INDEX   - Indices of XX/YY which remain inside the limb after
;                 rotation. When OFFLIMB becomes 1, the number of
;                 INDEX will be smaller than that of XX or YY. If no
;                 point remains inside the limb, INDEX is set to -1
;       BACK_INDEX  - Indices of XX/YY which were on the disk at TSTART, 
;                 but are no longer visible (i.e. are behind the visible 
;                 solar disk) after rotation. 
;       KEEP    - keep same epoch DATE when rotating; use same P,B0,R values 
;                 both for DATE and DATE+INTERVAL
;       VSTART, VEND = {b0,l0,rsun} = input structure with b0,l0,rsun
;                at start/end of rotation


    Returns:
    -------
    longditude_delta: ndarray
        The change in longitude over days (units=degrees)

    See Also
    --------
    IDL code equavalent:
        http://hesperia.gsfc.nasa.gov/ssw/gen/idl/solar/rot_xy.pro

"""
    # must have pairs of co-ordinates
    if np.array(x).shape != np.array(y).shape:
        raise ValueError('Input co-ordinates must have the same shape.')

    # Make sure we have enough time information to perform a solar differential
    # rotation
    if kwargs.get("tend") is not None:
        tend = parse_time(kwargs.get("tend"))
    else:
        tend = datetime.datetime.utcnow()
    if (kwargs.get("tstart") is not None):
        delta = tend - parse_time(kwargs.get("tstart"))

    if kwargs.get("interval") is not None:
        if isinstance(kwargs.get("interval"), datetime.timedelta):
            delta = kwargs.get("interval")
        else:
            delta = datetime.timedelta(seconds=kwargs.get("interval"))
    if ((kwargs.get("tstart") is None) and (kwargs.get("tend") is None)) or \
    ((kwargs.get("tstart") is None) and kwargs.get("interval") is None):
        raise ValueError("You need to specify 'tstart' & 'tend', or " + \
                          "'tstart' and 'interval'")

    # differentially rotate if interval is non-zero
    if delta.total_seconds() > 0.0:
        hgln, hglt = convert_hcc_hg(rsun, b0, l0, x, y)

    return None


def pb0r(date, stereo=False):
    """To calculate the solar P, B0 angles and the semi-diameter.  Based on
    http://hesperia.gsfc.nasa.gov/ssw/gen/idl/solar/pb0r.pro
    """
    # place holder for STEREO calculation
    if stereo:
        raise ValueError("STEREO solar P, B0 and semi-diameter calcution" + \
                         " is not supported.")
    # number of Julian days since 2415020.0
    de = julian_day(date) - 2415020.0

    # get the longitude of the sun etc.
    sun_position = sun_pos(date)
    longmed = sun_position["longitude"]
    ra = sun_position["ra"]
    dec = sun_position["dec"]
    appl = sun_position["app_long"]
    oblt = sun_position["obliq"]

    # form the aberrated longitude
    Lambda = longmed - (20.50 / 3600.0)

    # form longitude of ascending node of sun's equator on ecliptic
    node = 73.6666660 + (50.250 / 3600.0) * ((de / 365.250) + 50.0)
    arg = Lambda - node

    # calculate P, the position angle of the pole
    p = np.rad2deg(\
        np.arctan(-np.tan(np.deg2rad(oblt) * np.cos(np.deg2rad(appl)))) + \
        np.arctan(-0.127220 * np.cos(np.deg2rad(arg))))

    # B0 the tilt of the axis


    return {"b0":b0, "rsun":rsun, "l0":l0}


def sun_pos(date, is_julian=False, since_2415020=False):
    """ Calculate solar ephemeris parameters.  Allows for planetary and lunar
    perturbations in the calculation of solar longitude at date and various
    other solar positional parameters. This routine is a truncated version of
    Newcomb's Sun and is designed to give apparent angular coordinates (T.E.D)
    to a precision of one second of time.

    Parameters
    -----------
    date: a date/time object or a fractional number of days since JD 2415020.0

    is_julian: { False | True }
        notify this routine that the variable "date" is a Julian date
        (a floating point number)

    since_2415020: { False | True }
        notify this routine that the variable "date" has been corrected for
        the required time offset

    Returns:
    -------
    A dictionary with the following keys with the following meanings:

    longitude  -  Longitude of sun for mean equinox of date (degs)
    ra         -  Apparent RA for true equinox of date (degs)
    dec        -  Apparent declination for true equinox of date (degs)
    app_long   -  Apparent longitude (degs)
    obliq      -  True obliquity (degs)longditude_delta:

    See Also
    --------
    IDL code equavalent:
        http://hesperia.gsfc.nasa.gov/ssw/gen/idl/solar/sun_pos.pro

    Examples
    --------
    >>> sp = sun_pos('2013-03-27')
    >>> sp['longitude'], sp['ra'], sp['dec'], sp['app_long'], sp['obliq']

    (6.4854963639582923,
     5.9525787873210403,
     2.5739661719621627,
     6.4834125906094799,
     23.435885888864924)

    >>> jd = sunpy.time.julian_day('2013-03-27')
    >>> jd
    2456378.5
    >>> sp = sun_pos(2456378.5, is_julian=True)
    >>> sp['longitude'], sp['ra'], sp['dec'], sp['app_long'], sp['obliq']

    (6.4854963639582923,
     5.9525787873210403,
     2.5739661719621627,
     6.4834125906094799,
     23.435885888864924)
    """
    # check the time input
    if is_julian:
        # if a Julian date is being passed in
        if since_2415020:
            dd = date
        else:
            dd = date - 2415020.0
    else:
        # parse the input time as a julian day
        if since_2415020:
            dd = julian_day(date)
        else:
            dd = julian_day(date) - 2415020.0

    # form time in Julian centuries from 1900.0
    t = dd / 36525.0

    # form sun's mean longitude
    l = (279.6966780 + np.mod(36000.7689250 * t, 360.00)) * 3600.0

    # allow for ellipticity of the orbit (equation of centre) using the Earth's
    # mean anomaly ME
    me = 358.4758440 + np.mod(35999.049750 * t, 360.0)
    ellcor = (6910.10 - 17.20 * t) * np.sin(np.deg2rad(me)) + \
    72.30 * np.sin(np.deg2rad(2.0 * me))
    l = l + ellcor

    # allow for the Venus perturbations using the mean anomaly of Venus MV
    mv = 212.603219 + np.mod(58517.8038750 * t, 360.0)
    vencorr = 4.80 * np.cos(np.deg2rad(299.10170 + mv - me)) + \
          5.50 * np.cos(np.deg2rad(148.31330 + 2.0 * mv - 2.0 * me)) + \
          2.50 * np.cos(np.deg2rad(315.94330 + 2.0 * mv - 3.0 * me)) + \
          1.60 * np.cos(np.deg2rad(345.25330 + 3.0 * mv - 4.0 * me)) + \
          1.00 * np.cos(np.deg2rad(318.150 + 3.0 * mv - 5.0 * me))
    l = l + vencorr

    # Allow for the Jupiter perturbations using the mean anomaly of Jupiter MJ
    mj = 225.3283280 + np.mod(3034.69202390 * t, 360.00)
    jupcorr = 7.20 * np.cos(np.deg2rad(179.53170 - mj + me)) + \
          2.60 * np.cos(np.deg2rad(263.21670 - mj)) + \
          2.70 * np.cos(np.deg2rad(87.14500 - 2.0 * mj + 2.0 * me)) + \
          1.60 * np.cos(np.deg2rad(109.49330 - 2.0 * mj + me))
    l = l + jupcorr

    # Allow for the Moons perturbations using the mean elongation of the Moon
    # from the Sun D
    d = 350.73768140 + np.mod(445267.114220 * t, 360.0)
    mooncorr = 6.50 * np.sin(np.deg2rad(d))
    l = l + mooncorr

    # Note the original code is
    # longterm  = + 6.4d0 * sin(( 231.19d0  +  20.20d0 * t )*!dtor)
    longterm = 6.40 * np.sin(np.deg2rad(231.190 + 20.20 * t))
    l = l + longterm
    l = np.mod(l + 2592000.0, 1296000.0)
    longmed = l / 3600.0

    # Allow for Aberration
    l = l - 20.5

    # Allow for Nutation using the longitude of the Moons mean node OMEGA
    omega = 259.1832750 - np.mod(1934.1420080 * t, 360.0)
    l = l - 17.20 * np.sin(np.deg2rad(omega))

    # Form the True Obliquity
    oblt = 23.4522940 - 0.01301250 * t + \
    (9.20 * np.cos(np.deg2rad(omega))) / 3600.0

    # Form Right Ascension and Declination
    l = l / 3600.0
    ra = np.rad2deg(np.arctan2(np.sin(np.deg2rad(l)) * \
                        np.cos(np.deg2rad(oblt)), np.cos(np.deg2rad(l))))

    if isinstance(ra, np.ndarray):
        ra[ra < 0.0] += 360.0
    elif ra < 0.0:
        ra = ra + 360.0

    dec = np.rad2deg(np.arcsin(np.sin(np.deg2rad(l)) * \
                                np.sin(np.deg2rad(oblt))))

    # convert the internal variables to those listed in the top of the
    # comment section in this code and in the original IDL code.
    return {"longitude": longmed, "ra": ra, "dec": dec, "app_long": l,
            "obliq": oblt}
