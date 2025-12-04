"""Label-to-action routing for the ALM Orchestrator."""

from typing import Dict, List
from alm_orchestrator.actions.base import BaseAction


class UnknownLabelError(Exception):
    """Raised when no action is registered for a label."""
    pass


class LabelRouter:
    """Routes AI labels to their corresponding action handlers."""

    def __init__(self):
        """Initialize an empty router."""
        self._actions: Dict[str, BaseAction] = {}

    def register(self, label: str, action: BaseAction) -> None:
        """Register an action handler for a label.

        Args:
            label: The AI label (e.g., "ai-investigate").
            action: The action handler instance.
        """
        self._actions[label] = action

    def get_action(self, label: str) -> BaseAction:
        """Get the action handler for a label.

        Args:
            label: The AI label.

        Returns:
            The registered action handler.

        Raises:
            UnknownLabelError: If no action is registered for the label.
        """
        if label not in self._actions:
            raise UnknownLabelError(f"No action registered for label: {label}")
        return self._actions[label]

    def has_action(self, label: str) -> bool:
        """Check if an action is registered for a label.

        Args:
            label: The AI label.

        Returns:
            True if an action is registered, False otherwise.
        """
        return label in self._actions

    @property
    def action_count(self) -> int:
        """Get the number of registered actions.

        Returns:
            The count of actions loaded from the actions directory.
        """
        return len(self._actions)

    @property
    def action_names(self) -> List[str]:
        """Get the class names of all registered actions.

        Returns:
            A list of action class names as strings.
        """
        return [type(action).__name__ for action in self._actions.values()]


def discover_actions(prompts_dir: str) -> LabelRouter:
    """Auto-discover and register all action handlers.

    Scans the actions package for BaseAction subclasses,
    instantiates each with prompts_dir, and registers them.

    Args:
        prompts_dir: Path to prompt templates directory.

    Returns:
        LabelRouter with all discovered actions registered.
    """
    import importlib
    import pkgutil
    from alm_orchestrator import actions

    router = LabelRouter()

    # Iterate through all modules in the actions package
    for importer, modname, ispkg in pkgutil.iter_modules(actions.__path__):
        if modname == "base":
            continue  # Skip the base module

        module = importlib.import_module(f"alm_orchestrator.actions.{modname}")

        # Find all BaseAction subclasses in this module
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and
                issubclass(obj, BaseAction) and
                obj is not BaseAction):
                action = obj(prompts_dir)
                router.register(action.label, action)

    return router
