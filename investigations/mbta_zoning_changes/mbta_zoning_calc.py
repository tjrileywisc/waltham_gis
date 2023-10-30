

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsField,
                       QgsFields,
                       QgsFeature,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink)
from qgis import processing

import sys
# in qgis itself we might need to do this
sys.path.insert(0, r"C:\workspace\waltham_gis")
from waltham.zone import Zone
from waltham.parcel import Parcel
from investigations.mbta_zoning_changes.MBTACalculator import MBTACalculator

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

        # Send some information to the user
        #feedback.pushInfo('CRS is {}'.format(source.sourceCrs().authid()))

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        
        out_fields = QgsFields()
        out_fields.extend(source.fields())
        out_fields.append(QgsField('NEW_CAPACITY', QVariant.Double))
        out_fields.append(QgsField('DU_PER_AC', QVariant.Double))
            
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            out_fields,
            source.wkbType(),
            source.sourceCrs()
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / source.featureCount() if source.featureCount() else 0

        zone_features = zoning_table.getFeatures()
        zoning = dict()
        for index, zone_rules in enumerate(zone_features):

            far = zone_rules["FAR by right"]
            if far != "":
                far = float(far)
            else:
                far = None

            max_lot_coverage = zone_rules["max lot coverage"]
            if max_lot_coverage != "":
                max_lot_coverage = float(max_lot_coverage)
            else:
                max_lot_coverage = None
            
            min_open_space = zone_rules["min open space"]
            if min_open_space != "":
                min_open_space = float(min_open_space)
            else:
                min_open_space = None
                
            lot_area = zone_rules["lot area"]
            if lot_area != "":
                lot_area = int(lot_area)
            else:
                lot_area = None
            
            max_dua = zone_rules["max DUA"]
            if max_dua != "":
                max_dua = int(max_dua)
            else:
                max_dua = None
            
            z = Zone(
                zone_rules["District"],
                int(zone_rules["front setback"]),
                int(zone_rules["side setback"]),
                int(zone_rules["rear setback"]),
                int(zone_rules["height"]),
                float(zone_rules["stories"]),
                far,
                max_lot_coverage,
                min_open_space,
                lot_area,
                max_dua,
                int(zone_rules["lot frontage"])
            )
            zoning[zone_rules["District"]] = z
            


        parcels = source.getFeatures()
        for index, parcel in enumerate(parcels):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break

            attributes = parcel.attributes()
            
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

            p.set_zoning(vars(zoning[parcel["NAME"]]))
            
            calc = MBTACalculator(p, vars(zoning[parcel["NAME"]]))

            # run the calculation
            new_capacity = calc.final_lot_mf_unit_capacity()
            du_per_ac = calc.du_per_ac()

            # add new data (need to keep the order the same!)
            attributes.append(new_capacity)
            attributes.append(du_per_ac)

            updated_parcel = QgsFeature()
            updated_parcel.setFields(out_fields)
            updated_parcel.setGeometry(parcel.geometry())
            updated_parcel.setAttributes(attributes)

            # Add a feature in the sink
            sink.addFeature(updated_parcel, QgsFeatureSink.FastInsert)

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
