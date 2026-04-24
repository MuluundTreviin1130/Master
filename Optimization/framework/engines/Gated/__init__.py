__all__ = ["GatedEngine"]


def __getattr__(name: str):
    if name == "GatedEngine":
        from .gated_engine import GatedEngine
        return GatedEngine
    raise AttributeError(name)
