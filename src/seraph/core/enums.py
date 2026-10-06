from enum import StrEnum

class EpistemicStatus(StrEnum):
    OBSERVED="observed"; DERIVED="derived"; INFERRED="inferred"; MODELED="modeled"; COUNTERFACTUAL="counterfactual"; UNKNOWN="unknown"
class EntityType(StrEnum):
    SATELLITE="satellite"; GROUND_STATION="ground_station"; GNSS_SERVICE="gnss_service"; FACILITY="facility"; PORT="port"; AIRPORT="airport"; ROAD="road"; RAIL="rail"; POWER_PLANT="power_plant"; POWER_GRID="power_grid"; TELECOM_NETWORK="telecom_network"; DATA_CENTER="data_center"; BANK="bank"; PAYMENT_SYSTEM="payment_system"; MARKET="market"; COMPANY="company"; GOVERNMENT="government"; REGION="region"; COUNTRY="country"; SECTOR="sector"; SERVICE="service"; CAPABILITY="capability"; FLOW="flow"; OTHER="other"
class RelationshipType(StrEnum):
    PROVIDES="provides"; DEPENDS_ON="depends_on"; SUPPORTS="supports"; CONNECTS_TO="connects_to"; LOCATED_IN="located_in"; OWNED_BY="owned_by"; OPERATED_BY="operated_by"; CONTROLLED_BY="controlled_by"; SUPPLIES="supplies"; USES="uses"; TRANSPORTS="transports"; POWERS="powers"; TIMES="times"; ENABLES="enables"; BACKS_UP="backs_up"; SUBSTITUTES="substitutes"; MEMBER_OF="member_of"; AFFECTS="affects"; SERVES="serves"; EXPOSES="exposes"; DERIVED_FROM="derived_from"; OTHER="other"
class EventType(StrEnum):
    OUTAGE="outage"; DEGRADATION="degradation"; CAPACITY_LOSS="capacity_loss"; PHYSICAL_DAMAGE="physical_damage"; SUPPLY_DISRUPTION="supply_disruption"; CYBER="cyber"; GEOPOLITICAL="geopolitical"; NATURAL_HAZARD="natural_hazard"; SPACE_WEATHER="space_weather"; GNSS_INTERFERENCE="gnss_interference"; MARKET_SHOCK="market_shock"; POLICY_CHANGE="policy_change"; OTHER="other"
class InterventionType(StrEnum):
    REDUNDANCY="redundancy"; HARDENING="hardening"; DIVERSIFICATION="diversification"; STOCKPILE="stockpile"; BACKUP_SERVICE="backup_service"; ROUTING_CHANGE="routing_change"; DEMAND_RESPONSE="demand_response"; CAPACITY_EXPANSION="capacity_expansion"; SUBSTITUTION="substitution"; OTHER="other"
