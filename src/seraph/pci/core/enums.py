from __future__ import annotations

from enum import StrEnum


class EpistemicStatus(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    MODELED = "modeled"
    COUNTERFACTUAL = "counterfactual"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    SATELLITE = "satellite"
    GROUND_STATION = "ground_station"
    GNSS_SERVICE = "gnss_service"
    TELECOM_NETWORK = "telecom_network"
    DATA_CENTER = "data_center"
    POWER_PLANT = "power_plant"
    POWER_GRID = "power_grid"
    PORT = "port"
    RAILWAY = "railway"
    AIRPORT = "airport"
    ROAD = "road"
    PIPELINE = "pipeline"
    BANK = "bank"
    PAYMENT_SYSTEM = "payment_system"
    MARKET = "market"
    COMPANY = "company"
    GOVERNMENT = "government"
    REGION = "region"
    COUNTRY = "country"
    ECONOMIC_FUNCTION = "economic_function"
    SERVICE = "service"
    ASSET = "asset"
    OTHER = "other"


class RelationshipType(StrEnum):
    SUPPORTS = "supports"
    DEPENDS_ON = "depends_on"
    PROVIDES = "provides"
    CONNECTS_TO = "connects_to"
    LOCATED_IN = "located_in"
    OWNED_BY = "owned_by"
    OPERATED_BY = "operated_by"
    CONTROLLED_BY = "controlled_by"
    SUPPLIED_BY = "supplied_by"
    USES = "uses"
    TRANSPORTS = "transports"
    POWERS = "powers"
    TIMES = "times"
    ENABLES = "enables"
    BACKS_UP = "backs_up"
    ALTERNATIVE_TO = "alternative_to"
    MEMBER_OF = "member_of"
    AFFECTS = "affects"
    CUSTOM = "custom"


class ShockType(StrEnum):
    OUTAGE = "outage"
    DEGRADATION = "degradation"
    CAPACITY_LOSS = "capacity_loss"
    PHYSICAL_DAMAGE = "physical_damage"
    SUPPLY_DISRUPTION = "supply_disruption"
    CYBER_EVENT = "cyber_event"
    GEOPOLITICAL = "geopolitical"
    NATURAL_HAZARD = "natural_hazard"
    SPACE_WEATHER = "space_weather"
    GNSS_INTERFERENCE = "gnss_interference"
    OTHER = "other"


class InterventionType(StrEnum):
    REDUNDANCY = "redundancy"
    HARDENING = "hardening"
    DIVERSIFICATION = "diversification"
    STOCKPILE = "stockpile"
    BACKUP_SERVICE = "backup_service"
    ROUTING_CHANGE = "routing_change"
    DEMAND_RESPONSE = "demand_response"
    CAPACITY_EXPANSION = "capacity_expansion"
    OTHER = "other"
