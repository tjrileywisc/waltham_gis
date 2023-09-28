
from qgis import processing
from qgis.processing import alg
from qgis.core import QgsProject



@alg(name="calc_zoning", label="calculation of units for a parcel", group="examplescripts", group_label="example_scripts")
@alg.input(type=alg.SOURCE, name='INPUT', label='Input vector layer')
@alg.output(type=alg.NUMBER, name="N_UNITS", label="number of units")
def calc_zoning(instance, parameters, context, feedback, inputs):
    """
    Calculate the number of expected units in a parcel, given'
    Waltham's zoning rules for that parcel and the MBTA's provided
    shapefiles for Waltham.
    """
    input_featuresource = instance.parameterAsSource(parameters,
                                                     'INPUT',
                                                     context)
    numfeatures = input_featuresource.featureCount()
    return {'OUTPUT': numfeatures}


# functions from district tabs

# class Parcel:
#     def __init__(self):
#         self.fid
#         self.loc_id
#         # ignore irrelevant freetext fields
#         self.transit_station
#         self.parcel_acres
#         self.parcel_sf
#         self.excluded_public
#         self.excluded_non_public
#         self.total_excluded_land

# # col N
# def developable_parcel_sf(min_parcel_size, parcel_size, excluded_size):
#     """_summary_

#     Args:
#         min_parcel_size (float): minimum parcel size set in district
#         parcel_size (float)    : actual parcel lot size
#         excluded_size(float) : excluded buildable area of the parcel
        
#     """

#     if parcel_size < min_parcel_size:
#         return 0
    
#     return min(parcel_size - excluded_size, 0)

# # col Q
# def developable_sqft_for_unit():
    
#     return developable_parcel_sf

# def open_space_required(required_open_space_frac):
#     """_summary_

#     Args:
#         required_open_space_frac (float):
#             district required open space fraction
#     """
#     return max(0.2, required_open_space_frac)


# def open_space_removed():
#     """_summary_
#     """

#     if override_dev_sqft == 0:
#         if allows_restricted_areas:
#             return max(excluded_land_frac, open_space_required) * parcel_size
#         else:
#             return (excluded_land_frac + open_space_required) * parcel_size
    
#     return developable_sqft_for_unit * open_space_required


# def model_parking_ratio(district_parking_ratio):
#     """_summary_

#     Args:
#         district_parking_ratio (_type_): _description_
#     """
#     if district_parking_ratio == 0:
#         return 0
#     elif district_parking_ratio >= 0.01 and district_parking_ratio <= 0.5:
#         return 0.3
#     elif district_parking_ratio >= 0.51 and district_parking_ratio <= 1.0:
#         return 0.45
#     elif district_parking_ratio >= 1.01 and district_parking_ratio <= 1.25:
#         return 0.55
#     elif district_parking_ratio >= 1.26 and district_parking_ratio <= 1.5:
#         return 0.6
#     elif district_parking_ratio >= 1.51:
#         return 0.65


# def parking_area_removed(parcel_size):
#     """_summary_
#     """

#     if developable_sqft_for_unit > 0:
#         return (parcel_size - open_space_removed) * model_parking_ratio
    
#     return 0

# def building_footprint(parcel_size):

#     if developable_sqft_for_unit == 0:
#         return 0
    
#     return parcel_size - open_space_removed - parking_area_removed

# def building_envelope():

#     if building_footprint > 0:
#         return building_footprint * max_building_stories
    
#     return 0

# # unit capacity tests (i.e. NIMBY's playground)

# def modeled_unit_capacity():

#     if building_envelope / 1000 > 3:
#         return int(building_envelope / 1000)
#     else:
#         if building_envelope / 1000 > 2.5 and building_envelope / 1000 <= 3:
#             return 3
    
#     return 0

# def dwelling_units_per_acre_limit():

#     if max_units_per_acre:
#         return (parcel_size / SQ_FT_IN_ACRE) * max_units_per_acre
    
#     return None

# def max_lot_coverage_limit():

#     if max_lot_coverage_frac:
#         return (parcel_size * max_lot_coverage_frac) * max_building_stories / 1000
    
#     return None

# def lot_area_per_dwelling_limit():

#     if lot_area_per_dwelling_unit:
#         return parcel_size / lot_area_per_dwelling_unit
    
#     return None

# def far_limit():

#     if far:
#         return parcel_size * far / 1000
    
#     return None

# def max_units_per_lot_limit():

#     if not max_units_per_lot:
#         return modeled_unit_capacity
#     elif max_units_per_lot < modeled_unit_capacity and max_units_per_lot >= 3:
#         return max_units_per_lot
#     elif max_units_per_lot < modeled_unit_capacity and max_units_per_lot < 3:
#         return 0
    
#     return modeled_unit_capacity

# def is_non_conforming_lot():

#     if parcel_size < minimum_lot_size and parcel_size > 0:
#         return True
    
#     return False

# def max_units_based_on_addl_lot_size_reqs():

#     if is_non_conforming_lot:
#         return 0

#     if not addl_lot_sq_ft_by_dwelling_unit:
#         return "<no limit>" # TODO: how to render this?

#     return int(((parcel_size-base_lot_size)/addl_lot_sq_ft_by_dwelling_unit)+1)


# # unit compliance

# def final_lot_mf_unit_capacity():

#     min_constraints = min(modeled_unit_capacity, dwelling_units_per_acre_limit, max_lot_coverage_limit, lot_area_per_dwelling_limit, far_limit, max_units_per_lot_limit) 

#     if min_constraints < 2.5:
#         return 0
#     elif min_constraints >= 2.5 and min_constraints < 3:
#         return 3
#     return int(min_constraints)

# def du_per_ac():

#     return SQ_FT_IN_ACRE * final_lot_mf_unit_capacity / parcel_size
