
import pytest
from waltham.zone import Zone
from waltham.parcel import Parcel

from investigations.mbta_zoning_changes.MBTACalculator import MBTACalculator


def test_developable_parcel_sf_no_excluded_land():
    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(1617.262852) == calc.developable_parcel_sf()


def test_open_space_removed():
    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(323, 1) == calc.open_space_removed()


def test_parking_area_removed():

    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100,
        0
    )

    calc = MBTACalculator(parcel, zone)

    assert 0 == calc.parking_area_removed()

    # uses default parking ratio of 2.0
    # for waltham
    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(841, 1) == calc.parking_area_removed()


def test_building_footprint():

    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(1294, 1) == calc.building_footprint()


def test_building_envelope():

    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(3235, 1) == calc.building_envelope()


def test_modeled_unit_capacity():

    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "B",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(0.0) == calc.modeled_unit_capacity()

def test_final_lot_mf_unit_capacity():

    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "C",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(0.0) == calc.final_lot_mf_unit_capacity()
    
    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.08880941894,
        3868.538289,
        0,
        0,
        0,
        0
    )
    
    zone = Zone(
        "C",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(3, 1) == calc.final_lot_mf_unit_capacity()

def test_du_per_ac():

    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.03712724637,
        1617.262852,
        0,
        0,
        0,
        0
    )

    zone = Zone(
        "C",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(0.0) == calc.du_per_ac()
    
    parcel = Parcel(
        "LOC_ID",
        "Y",
        0.08880941894,
        3868.538289,
        0,
        0,
        0,
        0
    )
    
    zone = Zone(
        "C",
        40,
        20,
        40,
        35,
        2.5,
        None,
        0.2,
        None,
        20_000,
        None,
        100
    )

    calc = MBTACalculator(parcel, zone)

    assert pytest.approx(33, 1) == calc.du_per_ac()


