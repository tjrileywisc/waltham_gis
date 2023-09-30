

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink)
from qgis import processing


SQ_FT_IN_ACRE = 43560
# the parking minimum is effectively 2 everywhere for all housing types
PARKING_MINIMUM = 2

class Zone:
    def __init__(self, name, front_setback, side_setback, rear_setback, height, stories, far, max_lot_coverage, min_open_space, lot_area, max_dua, lot_frontage):
        self.name = name
        self.front_setback = front_setback
        self.side_setback = side_setback
        self.rear_setback = rear_setback
        self.height = height
        self.stories = stories
        self.far = far
        self.max_lot_coverage = max_lot_coverage
        self.min_open_space = min_open_space
        self.lot_area = lot_area
        self.max_dua = max_dua
        self.lot_frontage = lot_frontage
        
        self.district_parking_ratio = PARKING_MINIMUM

        

class Parcel:
    def __init__(self, loc_id, transit_station, parcel_acres, parcel_sf, excluded_public, excluded_non_public, total_excluded_land, total_sensitive_land, zone):
       self.loc_id = loc_id
       # ignore irrelevant freetext fields
       self.transit_station = transit_station
       self.parcel_acres = parcel_acres
       self.parcel_sf = parcel_sf
       self.excluded_public = excluded_public
       self.excluded_non_public = excluded_non_public
       self.total_excluded_land = total_excluded_land
       self.total_sensitive_land = total_sensitive_land
       self.zone = zone
       
    def set_zoning(self, zoning):
        self.zoning = zoning
    
    # functions from district tabs
    # col N
    def developable_parcel_sf(self):

        if self.parcel_sf < self.zoning["min_parcel_size"]:
            return 0
        
        return max(self.parcel_sf - self.total_excluded_size, 0)

    # col Q
    # NOTE: we're not applying any overrides
    def developable_sqft_for_unit(self):
        
        return self.developable_parcel_sf()
    
    # col R
    def excluded_land_pct(self):
        if self.parcel_sf == 0:
            return 0
        return self.total_excluded_land / self.parcel_sf

    # col S
    # NOTE: this 0.2 appears to be hardcoded, is it in the law?
    def open_space_required(self):

        return max(0.2, self.zoning["min_open_space"])

    # col T
    # NOTE: we're not applying any overrides
    def open_space_removed(self):

        if self.zoning["allows_restricted_areas"]:
            return max(self.excluded_land_pct(), self.open_space_required()) * self.parcel_sf
        else:
            return (self.excluded_land_pct() + self.open_space_required()) * self.parcel_sf

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
            return (self.parcel_sf - self.open_space_removed()) * self.model_parking_ratio()
        
        return 0

    # col V
    def building_footprint(self):

        if self.developable_sqft_for_unit() == 0:
            return 0
        
        return self.parcel_sf - self.open_space_removed() - self.parking_area_removed()

    # col W
    def building_envelope(self):

        if self.building_footprint() > 0:
            return self.building_footprint() * self.zoning["stories"]
        
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
            return (self.parcel_sf / SQ_FT_IN_ACRE) * self.zoning["max_dua"]
        
        return None

    # col Z
    def max_lot_coverage_limit(self):

        if self.zoning.get("max_lot_coverage_frac"):
            return (self.parcel_sf * self.zoning["max_lot_coverage_frac"]) * self.zoning["stories"] / 1000
        
        return None

    # col AA
    def lot_area_per_dwelling_limit(self):

        if self.zoning.get("lot_area_per_dwelling_unit"):
            return self.parcel_sf / self.zoning["lot_area_per_dwelling_unit"]
        
        return None

    # col AB
    def far_limit(self):

        if self.zoning.get("far"):
            return self.parcel_sf * self.zoning["far"] / 1000
        
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

        if self.parcel_sf < self.zoning["minimum_lot_size"] and self.parcel_sf > 0:
            return True
        
        return False

    # col AE
    def max_units_based_on_addl_lot_size_reqs(self):

        if self.is_non_conforming_lot():
            return 0

        if not self.zoning.get("addl_lot_sq_ft_by_dwelling_unit"):
            return "<no limit>" # TODO: how to render this?

        return int(((self.parcel_sf - self.zoning["base_lot_size"])/self.zoning["addl_lot_sq_ft_by_dwelling_unit"])+1)


    # unit compliance

    # col AF
    def final_lot_mf_unit_capacity(self):

        min_constraints = min(
            self.modeled_unit_capacity(), self.dwelling_units_per_acre_limit(), 
            self.max_lot_coverage_limit(), self.lot_area_per_dwelling_limit(), self.far_limit(), self.max_units_per_lot_limit()) 

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

        return SQ_FT_IN_ACRE * self.final_lot_mf_unit_capacity() / self.parcel_sf


class WalthamUnitCalc(QgsProcessingAlgorithm):
    """
    Calculates the number of units expected on a parcel
    given the current zoning
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = 'INPUT'
    ZONING_TABLE = 'ZONING_TABLE'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return WalthamUnitCalc()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'myscript'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('My Script')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Example scripts')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'examplescripts'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("Example algorithm short description")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # the shapefile with geometry and parcel attributes
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        
        # a csv file that has the lookup for zoning params
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.ZONING_TABLE,
                "Zoning table",
                [QgsProcessing.TypeFile]
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Run the calculation of units
        """

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        source = self.parameterAsVectorLayer(
            parameters,
            self.INPUT,
            context
        )
        
        zoning_table = self.parameterAsSource(
            parameters,
            self.ZONING_TABLE,
            context
        )

        # If source was not found, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSourceError method to return a standard
        # helper text for when a source cannot be evaluated
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )

        # Send some information to the user
        feedback.pushInfo('CRS is {}'.format(source.sourceCrs().authid()))

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / source.featureCount() if source.featureCount() else 0
        
        zone_features = zoning_table.getFeatures()
        zoning = dict()
        for index, zone_rules in enumerate(zone_features):
            z = Zone(
                zone_rules["District"],
                zone_rules["front setback"],
                zone_rules["side setback"],
                zone_rules["rear setback"],
                zone_rules["height"],
                zone_rules["stories"],
                zone_rules["FAR by right"],
                zone_rules["max lot coverage"],
                zone_rules["min open space"],
                zone_rules["lot area"],
                zone_rules["max DUA"],
                zone_rules["lot frontage"]
            )
            zoning[zone_rules["District"]] = z
        
        parcels = source.getFeatures()
        for index, parcel in enumerate(parcels):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break
            
            p = Parcel(
                parcel["LOC_ID"],
                parcel["TRANSIT"],
                parcel["ACRES"],
                parcel["SQFT"],
                parcel["PublicInst"],
                parcel["NonPubExc"],
                parcel["Tot_Exclud"],
                parcel["Tot_Sensit"],
                parcel["NAME"]
            )
            
            # TODO: get zone of parcel
            p.set_zoning(zoning[parcel["NAME"]])
            
            #feedback.pushInfo('zone is {}'.format(zoning))
            
            # run the calculation
            du_per_ac = p.du_per_ac()

            # Add a feature in the sink
            #sink.addFeature(parcel, QgsFeatureSink.FastInsert)

            # Update the progress bar
            feedback.setProgress(int(index * total))

        # To run another Processing algorithm as part of this algorithm, you can use
        # processing.run(...). Make sure you pass the current context and feedback
        # to processing.run to ensure that all temporary layer outputs are available
        # to the executed algorithm, and that the executed algorithm can send feedback
        # reports to the user (and correctly handle cancellation and progress reports!)
        if False:
            buffered_layer = processing.run("native:buffer", {
                'INPUT': dest_id,
                'DISTANCE': 1.5,
                'SEGMENTS': 5,
                'END_CAP_STYLE': 0,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'DISSOLVE': False,
                'OUTPUT': 'memory:'
            }, context=context, feedback=feedback)['OUTPUT']

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}



