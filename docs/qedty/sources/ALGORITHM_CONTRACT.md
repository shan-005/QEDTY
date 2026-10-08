# Sources contract

Sources are adapters, not authorities. Each fetch is bounded by an explicit host allow-list, timeout, user-agent, response-size limit, and content hash. The normalized record retains source URI/evidence references where applicable.

Primary integration patterns:
- NASA CMR is an authoritative management system for NASA Earth-observation metadata and supports programmatic discovery/search: https://www.earthdata.nasa.gov/about/esdis/eosdis/cmr
- CMR Search exposes JSON, UMM-JSON and STAC-oriented response forms and recommends specifying UMM versions to avoid breaking changes: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
- NOAA NCEI provides REST access and subsetting of environmental datasets: https://www.ncei.noaa.gov/access/search/documentation/data-service/
- OECD ICIO provides internationally consistent inter-country input-output tables; the database was revised in January 2026: https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html
- STAC defines interoperable spatiotemporal asset/catalog/item structures and a REST search API: https://stacspec.org/
- OGC API Features defines standardized feature discovery/query building blocks: https://www.ogc.org/standards/ogcapi-features/
