Cleanup
- Remove test area code from pipeline
- Data directories and paths
- ss unused data; run pipeline; if all works delete ss
- Check for any optimisations

AddressBase
- Investigate is_residential criteria ('class' logic): class rule may count both an HMO parent record and the units within it.
- Investigate state criteria (2, 3, NA): check what happens to dwelling totals if NA and 3 included/excluded
- Use Census LSOA vacancy estimates in allocating private rentals + set Census PRS household counts as ceiling
- Include additional information in allocating which properties are private rentals (corporate land ownership, property characteristics, tenancy deposit scheme records)

HASP
- Make probabilistic match safe (for now excluded)
- See if/how to include zoopla property matches that point to the same UPRN (for now excluded as suspicious)

Rent estimation
- Estimate rents with a geographically weighted hedonic regression model (EPC property characteristics)
- Scale rent estimates down to match local authority achieved rent averages.