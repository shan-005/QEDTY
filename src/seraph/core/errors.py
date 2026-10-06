class SeraphError(Exception):
    pass


class ContractError(SeraphError):
    pass


class IdentityError(ContractError):
    pass


class ProvenanceError(ContractError):
    pass


class SourceError(SeraphError):
    pass


class ModelError(SeraphError):
    pass
