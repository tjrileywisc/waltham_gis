
# Half of Waltham's housing would require historical review for demolition

Earlier this year, I saw [an article](https://walthamtimes.org/2026/02/26/zba-delays-main-street-multifamily-parking-case-over-unclear-legal-questions/) in the Waltham Times
regarding the redevelopment of 719 Main St. to support housing. I'm quite happy to see this, though personally I'm wondering why the existing structure is preserved. I noticed
the age of the building (150 years according to the article) and was wondering if that might have been a factor. There's a provision in our code ([Section 23-2](https://ecode360.com/26936024))
that requires a Historical Commission review before demoltion of any structure of a certain age (75 years). Whether that was a factor for the owner, I'd really be curious like to know.

This got me thinking about the age of our housing stock overall in Waltham. It's no secret that housing is expensive here, and it's because we haven't been building enough to meet demand. Since we have
to make do with the housing we have, it continues to age. Using tax assessor data from [MassGIS](https://www.mass.gov/info-details/massgis-data-property-tax-parcels), and assuming any structure without
a known YEAR_BUILT entry in the data is already at least 75 years old (which our code suggests we do), I have been able to determine that this year, **50% of our housing stock is 75 years old or over**.
In terms of homes, this is 7428 historic vs. 7473 that are not.

What does this mean in practice? Older homes are more expensive to maintain, which I'm sure anyone who has been paying heating costs in one of these homes this past winter would tell you (and I expect it
to be much worse next year). Since an older home is decaying if anything, it's a worse product for a buyer at a higher price (i.e. inflation). Unless the age is part of the charm for you personally that you're willing
to pay for I guess.

I'll admit I don't know what the Historical Commission review means in practice for housing development though. Does anyone have experience getting a housing development project involving a demooltion through them? Are the reviews returned without undue delay? Did they make a judgement requiring preservation that didn't seem merited?

## Modeling the future

- No build scenario
Simply assume no new developments after the current year, and let every resdential development age as is.

- Smoothed percentages
In this scenario, I simply look at the rolling average of the last five years' percentage changes and assume this will continue to happen all over the city. This model
is kinda dumb as it means developments could just change every year. Because of the randomness inherent in this model, I run it many times to collect a range of results.

- Regression analysis
In this model, I build a regression on several variables (lot area, structure age, zone, etc.) to determine factors that might signify whether or not a parcel will be redeveloped
in the next year. This doesn't capture data that's outside of the GIS data I have available that could factor in (like labor and material costs).

## Data sources

Data used here can be retrieved from [a large zip](https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles/l3parcels/L3_AGGREGATE_SHP_20260101.zip) with
historical tax assessment data hosted by MassGIS.
