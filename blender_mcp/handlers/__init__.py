# Expose the registration decorator so handlers can import it as:
# from ..dispatcher import register_handler
# OR
# We might need to handle circular imports carefully.
# Typically, handlers import the registry to register themselves.

# Ideally, handlers should do: `from ..dispatcher import register_handler`
# So this file can be empty, forcing them to look up to the parent.
pass
