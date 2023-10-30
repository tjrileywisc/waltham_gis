

import sys

try:
    from ...waltham.zone import Zone
    from ...waltham.parcel import Parcel
except ImportError:
    # in qgis itself we might need to do this
    sys.path.insert(0, r"C:\workspace\waltham_gis")
    from waltham.zone import Zone
    from waltham.parcel import Parcel

SQ_FT_IN_ACRE = 43560


class MBTACalculator:

    def __init__(self, parcel, zone):
        self.parcel = parcel
        self.zoning = zone

    # functions from district tabs
    # col N
    def developable_parcel_sf(self) -> float:

        if self.parcel.parcel_sf < self.zoning.get("min_parcel_size", 0):
            return 0

        return max(self.parcel.parcel_sf - self.parcel.total_excluded_land, 0)

    # col Q
    # NOTE: we're not applying any overrides
    def developable_sqft_for_unit(self):

        return self.developable_parcel_sf()

    # col R
    def excluded_land_pct(self):
        if self.parcel.parcel_sf == 0:
            return 0
        return self.parcel.total_excluded_land / self.parcel.parcel_sf

    # col S
    # NOTE: this 0.2 appears to be hardcoded, is it in the law?
    def open_space_required(self):

        if self.zoning.get("min_open_space"):
            return max(0.2, self.zoning["min_open_space"])
        return 0.2

    # col T
    # NOTE: we're not applying any overrides
    def open_space_removed(self):

        # TODO: is this buried deeper in the code?
        if self.zoning.get("allows_restricted_areas"):
            # NOTE: same problems with None here as 'min' in another place
            params = [p for p in [self.excluded_land_pct(), self.open_space_required()] if p is not None]
            return max(params) * self.parcel.parcel_sf
        else:
            return (self.excluded_land_pct() + self.open_space_required()) * self.parcel.parcel_sf

    # NOTE: this is from another sheet (Formula Matrix) which seems to have
    # two definitions of how to determine the ratio. I'm basing this formula
    # off of what actually ends up in the sheet, and not the text description
    def model_parking_ratio(self):

        district_parking_ratio = self.zoning.get("district_parking_ratio", 0)

        if district_parking_ratio == 0:
            return 0
        elif district_parking_ratio >= 0.01 and district_parking_ratio <= 0.5:
            return 0.3
        elif district_parking_ratio >= 0.51 and district_parking_ratio <= 1.0:
            return 0.45
        elif district_parking_ratio >= 1.01 and district_parking_ratio <= 1.25:
            return 0.55
        elif district_parking_ratio >= 1.26 and district_parking_ratio <= 1.5:
            return 0.6
        elif district_parking_ratio >= 1.51:
            return 0.65

    # col U
    def parking_area_removed(self):

        if self.developable_sqft_for_unit() > 0:
            return (self.parcel.parcel_sf - self.open_space_removed()) * self.model_parking_ratio()

        return 0

    # col V
    def building_footprint(self):

        if self.developable_sqft_for_unit() == 0:
            return 0

        return self.parcel.parcel_sf - self.open_space_removed() - self.parking_area_removed()

    # col W
    def building_envelope(self):

        if self.building_footprint() > 0:
            return self.building_footprint() * self.zoning.get("stories", 1)

        return 0

    # col X
    def modeled_unit_capacity(self):

        if self.building_envelope() / 1000 > 3:
            return int(self.building_envelope() / 1000)
        else:
            if (self.building_envelope() / 1000 > 2.5) and (self.building_envelope() / 1000 <= 3):
                return 3

        return 0

    # col Y
    def dwelling_units_per_acre_limit(self):

        if self.zoning.get("max_dua"):
            return (self.parcel.parcel_sf / SQ_FT_IN_ACRE) * self.zoning.get("max_dua")
        
        return None

    # col Z
    def max_lot_coverage_limit(self):

        if self.zoning.get("max_lot_coverage_frac"):
            return (self.parcel.parcel_sf * self.zoning["max_lot_coverage_frac"]) * self.zoning["stories"] / 1000
        
        return None

    # col AA
    def lot_area_per_dwelling_limit(self):

        if self.zoning.get("lot_area_per_dwelling_unit"):
            return self.parcel.parcel_sf / self.zoning["lot_area_per_dwelling_unit"]
        
        return None

    # col AB
    def far_limit(self):

        if self.zoning.get("far"):
            return self.parcel.parcel_sf * self.zoning["far"] / 1000
        
        return None

    # col AC
    def max_units_per_lot_limit(self):

        if not self.zoning.get("max_dua"):
            return self.modeled_unit_capacity()
        elif (self.zoning["max_dua"] < self.modeled_unit_capacity()) and (self.zoning["max_dua"] >= 3):
            return self.zoning["max_dua"]
        elif (self.zoning["max_dua"] < self.modeled_unit_capacity()) and (self.zoning["max_dua"] < 3):
            return 0
        
        return self.modeled_unit_capacity()

    # col AD
    def is_non_conforming_lot(self):

        if self.parcel.parcel_sf < self.zoning["minimum_lot_size"] and self.parcel.parcel_sf > 0:
            return True
        
        return False

    # col AE
    def max_units_based_on_addl_lot_size_reqs(self):

        if self.is_non_conforming_lot():
            return 0

        if not self.zoning.get("addl_lot_sq_ft_by_dwelling_unit"):
            return "<no limit>" # TODO: how to render this?

        return int(((self.parcel.parcel_sf - self.zoning["base_lot_size"])/self.zoning["addl_lot_sq_ft_by_dwelling_unit"])+1)


    # unit compliance

    # col AF
    def final_lot_mf_unit_capacity(self):
        
        # NOTE:
        # having trouble here with None values,
        # which I think would have ended up as empty
        # strings in the spreadsheet. does the 'min' function
        # in there just ignore those? the python 'min' doesn't
        # like comparisons with None.
        params = [
            p for p in [
                self.modeled_unit_capacity(),
                self.dwelling_units_per_acre_limit(),
                self.modeled_unit_capacity(),
                self.max_lot_coverage_limit(),
                self.lot_area_per_dwelling_limit(),
                self.far_limit(),
                self.max_units_per_lot_limit()
            ] if p is not None
        ]

        min_constraints = min(
            params
        )

        if min_constraints < 2.5:
            return 0
        elif min_constraints >= 2.5 and min_constraints < 3:
            return 3
        return int(min_constraints)

    # col AG
    def du_per_ac(self):
        """
        The final calculation of dwelling units per acre on the parcel
        """

        return SQ_FT_IN_ACRE * self.final_lot_mf_unit_capacity() / self.parcel.parcel_sf
