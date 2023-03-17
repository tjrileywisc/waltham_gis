
radius = 35.89088388437564

def calc_local_density(df, indexes):
    
    results = []
    
    for idx in indexes:
    
        # don't calculate neighbors of non-waltham towns
        if df.at[idx, "TOWN_ID"] != 308:
            results.append((idx, 0))
            continue

        neighbors = df[df["centroid"].distance(df.at[idx, "centroid"]) <= radius]

        results.append((idx, neighbors["UNITS"].sum()))
        
    return results