from qedty.core.version import PRODUCT_VERSION

__version__ = PRODUCT_VERSION
__all__ = ["__version__"]
# QEDTY: Pydantic forward-reference bootstrap
from qedty._pydantic_bootstrap import rebuild_all_models as _rebuild_all_models

_rebuild_all_models()
del _rebuild_all_models
