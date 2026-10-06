from seraph.sources.space.rinex import parse_header
def test_rinex_header():
 text="     4.02           OBSERVATION DATA    G                   RINEX VERSION / TYPE"; assert parse_header(text).version=="4.02"
