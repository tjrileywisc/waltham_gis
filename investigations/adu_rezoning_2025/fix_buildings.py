
def fix_buildings(parcels_df, buildings_df):
    """
    The buildings shapefile has a 'TYPE' field that
    labels several buildings in the same plot as 'BLDG',
    which doesn't make it clear which is the main building and
    which are 'OUT_BLDG'. This function corrects that, given
    the parent parcels dataframe and the buildings dataframe.
    """
    
    return
