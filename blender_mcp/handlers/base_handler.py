import uuid
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BaseHandler:
    """
    Base class for all handlers.
    Provides common utility methods, correlation_id tracking, and server context.
    """

    def __init__(self, ctx: Optional[Any] = None) -> None:
        self.ctx = ctx
        self.correlation_id: str = ""

    def process_request(self, **params: Any) -> Dict[str, Any]:
        """
        Intercepts the request to extract and log the correlation_id,
        then calls the execute method.
        """
        # Exclude correlation_id from down-stream execute params if unwanted,
        # or pop it. We'll pop it and inject a UUID if missing.
        self.correlation_id = params.pop("correlation_id", str(uuid.uuid4()))
        logger.info(
            f"[Trace ID: {self.correlation_id}] Executing handler: {self.__class__.__name__}"
        )

        try:
            result = self.execute(**params)
            logger.debug(f"[Trace ID: {self.correlation_id}] Execution successful.")
            return result
        except Exception as e:
            logger.error(
                f"[Trace ID: {self.correlation_id}] Execution failed: {str(e)}", exc_info=True
            )
            raise e

    def execute(self, **params: Any) -> Dict[str, Any]:
        """
        Main execution method for the handler.
        Should be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute() method.")
