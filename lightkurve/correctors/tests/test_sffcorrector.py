"""Tests the `lightkurve.correctors.SFFCorrector` class."""
import pytest
import numpy as np
from astropy.utils.data import get_pkg_data_filename

from ... import LightCurve, KeplerLightCurveFile, KeplerLightCurve
from .. import SFFCorrector


K2_C08 = ("https://archive.stsci.edu/missions/k2/lightcurves/c8/"
          "220100000/39000/ktwo220139473-c08_llc.fits")


@pytest.mark.remote_data
@pytest.mark.parametrize("path", [K2_C08])
def test_remote_data(path):
    """Can we correct a simple K2 light curve?"""
    lcf = KeplerLightCurveFile(path, quality_bitmask=None)
    sff = SFFCorrector(lcf.PDCSAP_FLUX.remove_nans())
    sff.correct(windows=10, bins=5, timescale=0.5)


def test_sff_knots():
    """Is SFF robust against gaps in time and irregular time sampling?
    This test creates a light curve with gaps in time between
    days 20-30 and days 78-80.  In addition, the time sampling rate changes
    in the interval between day 30 and 78.  SFF should fail without error.
    """
    n_points = 300
    fn = get_pkg_data_filename('../../tests/data/ep60021426alldiagnostics.csv')
    data = np.genfromtxt(fn, delimiter=',', skip_header=1)
    raw_flux = data[:, 1][:n_points]
    centroid_col = data[:, 3][:n_points]
    centroid_row = data[:, 4][:n_points]

    time = np.concatenate((np.linspace(0, 20, int(n_points/3)),
                           np.linspace(30, 78, int(n_points/3)),
                           np.linspace(80, 100, int(n_points/3))
                           ))
    lc = KeplerLightCurve(time=time,
                          flux=raw_flux,
                          flux_err=np.ones(n_points) * 0.0001,
                          centroid_col=centroid_col,
                          centroid_row=centroid_row)

    # These calls should not raise an exception:
    SFFCorrector(lc).correct()
    lc.to_corrector(method="sff").correct()


def test_sff_corrector():
    """Does our code agree with the example presented in Vanderburg
    and Johnson (2014)?"""
    # The following csv file, provided by Vanderburg and Johnson
    # at https://www.cfa.harvard.edu/~avanderb/k2/ep60021426.html,
    # contains the results of applying SFF to EPIC 60021426.
    fn = get_pkg_data_filename('../../tests/data/ep60021426alldiagnostics.csv')
    data = np.genfromtxt(fn, delimiter=',', skip_header=1)
    mask = data[:, -2] == 0  # indicates whether the thrusters were on or off
    time = data[:, 0]
    raw_flux = data[:, 1]
    corrected_flux = data[:, 2]
    centroid_col = data[:, 3]
    centroid_row = data[:, 4]

    # NOTE: we need a small number of windows below because this test data set
    # is unusually short, i.e. has an unusually small number of cadences.
    lc = LightCurve(time=time, flux=raw_flux, flux_err=np.ones(len(raw_flux)) * 0.0001)
    sff = SFFCorrector(lc)
    corrected_lc = sff.correct(centroid_col=centroid_col,
                               centroid_row=centroid_row,
                               restore_trend=True,
                               windows=1)
    assert (np.isclose(corrected_flux, corrected_lc.flux, atol=0.001).all())

    # masking
    corrected_lc = sff.correct(centroid_col=centroid_col,
                               centroid_row=centroid_row,
                               windows=3,
                               restore_trend=True,
                               cadence_mask=mask)
    assert (np.isclose(corrected_flux, corrected_lc.flux, atol=0.001).all())

    # masking and breakindex
    corrected_lc = sff.correct(centroid_col=centroid_col,
                               centroid_row=centroid_row,
                               windows=3,
                               restore_trend=True,
                               cadence_mask=mask,
                               breakindex=150)
    assert (np.isclose(corrected_flux, corrected_lc.flux, atol=0.001).all())

    # masking and breakindex and iters
    corrected_lc = sff.correct(centroid_col=centroid_col,
                               centroid_row=centroid_row, windows=3, restore_trend=True,
                               cadence_mask=mask, breakindex=150, niters=3)
    assert (np.isclose(corrected_flux, corrected_lc.flux, atol=0.001).all())

    # masking and breakindex and bins
    corrected_lc = sff.correct(centroid_col=centroid_col,
                               centroid_row=centroid_row, windows=3, restore_trend=True,
                               cadence_mask=mask, breakindex=150, bins=5)
    assert (np.isclose(corrected_flux, corrected_lc.flux, atol=0.001).all())
    assert np.all((sff.lc.flux_err/sff.corrected_lc.flux_err) == 1)


    # masking and breakindex and bins and propagate_errors
    corrected_lc = sff.correct(centroid_col=centroid_col,
                               centroid_row=centroid_row, windows=3, restore_trend=True,
                               cadence_mask=mask, breakindex=150, bins=5, propagate_errors=True)
    assert (np.isclose(corrected_flux, corrected_lc.flux, atol=0.001).all())
    assert np.all((sff.lc.flux_err/sff.corrected_lc.flux_err) < 1)

    # test using KeplerLightCurve interface
    klc = KeplerLightCurve(time=time,
                           flux=raw_flux,
                           flux_err=np.ones(len(raw_flux)) * 0.0001,
                           centroid_col=centroid_col,
                           centroid_row=centroid_row)
    sff = klc.to_corrector("sff")
    klc = sff.correct(windows=3, restore_trend=True)
    assert (np.isclose(corrected_flux, klc.flux, atol=0.001).all())

    # Can plot
    sff.diagnose()


def test_sff_priors():
    """SFF Spline flux mean should == lc.flux.mean()
    SFF arclength component should have mean 0
    """
    n_points = 300
    fn = get_pkg_data_filename('../../tests/data/ep60021426alldiagnostics.csv')
    data = np.genfromtxt(fn, delimiter=',', skip_header=1)
    raw_flux = data[:, 1][:n_points]
    centroid_col = data[:, 3][:n_points]
    centroid_row = data[:, 4][:n_points]

    time = np.concatenate((np.linspace(0, 20, int(n_points/3)),
                           np.linspace(30, 78, int(n_points/3)),
                           np.linspace(80, 100, int(n_points/3))
                           ))
    lc = KeplerLightCurve(time=time,
                          flux=raw_flux,
                          flux_err=np.ones(n_points) * 0.0001,
                          centroid_col=centroid_col,
                          centroid_row=centroid_row)

    sff = SFFCorrector(lc)
    sff.correct()  # should not raise an exception
    assert np.isclose(sff.diagnostic_lightcurves['spline'].flux.mean(), 1, atol=1e-3)
    assert np.isclose(sff.diagnostic_lightcurves['sff'].flux.mean(), 0, atol=1e-3)
