
class Parcel:
    def __init__(self, loc_id, transit_station, parcel_acres, parcel_sf,
                 excluded_public, excluded_non_public, total_excluded_land,
                 total_sensitive_land, zone=None):
        """
        Initialize a Parcel instance with various properties.

        Args:
            loc_id (int): The unique identifier for the parcel.
            transit_station (bool): Transit access within 0.5 mi?
            parcel_acres (float): The size of the parcel in acres.
            parcel_sf (int): The size of the parcel in square feet.
            excluded_public (bool): Indicates the fraction of the parcel is excluded from public use.
            excluded_non_public (bool): Indicates whether the parcel is excluded from non-public use.
            total_excluded_land (float): The total area of land excluded for various purposes.
            total_sensitive_land (float): The total area of sensitive land on the parcel

        Attributes:
            loc_id (int): The unique identifier for the parcel.
            transit_station (str): The name of the transit station associated with the parcel.
            parcel_acres (float): The size of the parcel in acres.
            parcel_sf (int): The size of the parcel in square feet.
            excluded_public (bool): Indicates whether the parcel is excluded from public use.
            excluded_non_public (bool): Indicates whether the parcel is excluded from non-public use.
            total_excluded_land (float): The total area of land excluded for various purposes.
            total_sensitive_land (float): The total area of sensitive land on the parcel.
            zone (str): The zoning information for the parcel.

        Returns:
            None
        """
        self.loc_id = loc_id
        self.transit_station = transit_station
        self.parcel_acres = parcel_acres
        self.parcel_sf = parcel_sf
        self.excluded_public = excluded_public
        self.excluded_non_public = excluded_non_public
        self.total_excluded_land = total_excluded_land
        self.total_sensitive_land = total_sensitive_land

        if zone:
            self.zoning = zone

    def set_zoning(self, zoning):
        """
        Set the zoning information for the parcel.

        Args:
            zoning (str): The zoning information to be set for the parcel.

        Returns:
            None
        """
        self.zoning = zoning
