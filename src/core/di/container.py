"""
Lightweight Dependency Injection Container.

Supports:
- Singleton, scoped, and transient lifetimes
- Interface-to-implementation mapping
- Factory functions
- Constructor injection
"""

from __future__ import annotations
from typing import TypeVar, Type, Dict, Callable, Optional, Any
from enum import Enum
import threading
import inspect
import logging

log = logging.getLogger("CellarLogger")

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime options."""

    SINGLETON = "singleton"  # One instance for entire app
    SCOPED = "scoped"  # One instance per scope
    TRANSIENT = "transient"  # New instance each time


class ServiceDescriptor:
    """Describes how to create a service."""

    def __init__(
        self,
        service_type: Type,
        implementation_type: Optional[Type] = None,
        factory: Optional[Callable[[DIContainer], Any]] = None,
        instance: Optional[Any] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ):
        self.service_type = service_type
        self.implementation_type = implementation_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime


class DIContainer:
    """
    Lightweight dependency injection container.

    Supports:
    - Interface-to-implementation mapping
    - Factory functions
    - Singleton, scoped, and transient lifetimes
    - Constructor injection (resolves parameters by type annotation)

    Example:
        container = DIContainer()
        container.register_singleton(IAssetRepository, JsonAssetRepository)
        container.register_transient(IAssetService, AssetService)

        service = container.resolve(IAssetService)
    """

    def __init__(self, parent: Optional[DIContainer] = None):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[Type, Any] = {}
        self._parent = parent
        self._lock = threading.RLock()  # RLock allows recursive acquisition

    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[DIContainer], T]] = None,
        instance: Optional[T] = None,
    ) -> DIContainer:
        """
        Register a singleton service.

        Args:
            service_type: The interface/base type
            implementation_type: The concrete type (optional if factory/instance provided)
            factory: Factory function that creates the instance
            instance: Pre-created instance

        Returns:
            Self for method chaining
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )
        return self

    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[DIContainer], T]] = None,
    ) -> DIContainer:
        """
        Register a transient service (new instance each time).

        Args:
            service_type: The interface/base type
            implementation_type: The concrete type (optional if factory provided)
            factory: Factory function that creates the instance

        Returns:
            Self for method chaining
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT,
        )
        return self

    def register_scoped(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[DIContainer], T]] = None,
    ) -> DIContainer:
        """
        Register a scoped service (one instance per scope/child container).

        Args:
            service_type: The interface/base type
            implementation_type: The concrete type (optional if factory provided)
            factory: Factory function that creates the instance

        Returns:
            Self for method chaining
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=ServiceLifetime.SCOPED,
        )
        return self

    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service by its type.

        Args:
            service_type: The type to resolve

        Returns:
            Instance of the service

        Raises:
            ValueError: If service is not registered
        """
        with self._lock:
            return self._resolve_internal(service_type)

    def _resolve_internal(self, service_type: Type[T]) -> T:
        """Internal resolve without lock (for recursive resolution)."""
        descriptor = self._services.get(service_type)

        if descriptor is None:
            if self._parent:
                return self._parent.resolve(service_type)
            type_name = getattr(service_type, '__name__', str(service_type))
            raise ValueError(f"Service {type_name} is not registered")

        # Return pre-created instance
        if descriptor.instance is not None:
            return descriptor.instance

        # Return existing singleton
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

        # Return existing scoped instance
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]

        # Create new instance
        instance = self._create_instance(descriptor)

        # Store based on lifetime
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            self._singletons[service_type] = instance
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            self._scoped_instances[service_type] = instance

        return instance

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new instance of a service."""
        # Use factory if provided
        if descriptor.factory:
            return descriptor.factory(self)

        # Get implementation type
        impl_type = descriptor.implementation_type or descriptor.service_type

        # Get constructor parameters and resolve dependencies
        try:
            sig = inspect.signature(impl_type.__init__)
        except (ValueError, TypeError):
            # No signature available, try creating without args
            return impl_type()

        kwargs: Dict[str, Any] = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Skip *args and **kwargs
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            # Try to resolve by type annotation
            if param.annotation != inspect.Parameter.empty:
                # Skip string annotations (from __future__ import annotations)
                # and non-class types
                if isinstance(param.annotation, str):
                    if param.default != inspect.Parameter.empty:
                        continue
                    # Can't resolve string annotations, skip if has default
                    continue

                try:
                    kwargs[param_name] = self._resolve_internal(param.annotation)
                except ValueError:
                    # If can't resolve and has default, skip
                    if param.default != inspect.Parameter.empty:
                        continue
                    raise

        log.debug(f"Creating instance of {impl_type.__name__}")
        return impl_type(**kwargs)

    def create_scope(self) -> DIContainer:
        """
        Create a child container for scoped services.

        Returns:
            New container with this container as parent
        """
        return DIContainer(parent=self)

    def dispose(self) -> None:
        """Clean up scoped instances and call dispose on disposable services."""
        for instance in self._scoped_instances.values():
            if hasattr(instance, "dispose"):
                instance.dispose()
            elif hasattr(instance, "close"):
                instance.close()

        self._scoped_instances.clear()

    def dispose_all(self) -> None:
        """Clean up all instances including singletons."""
        self.dispose()

        for instance in self._singletons.values():
            if hasattr(instance, "dispose"):
                instance.dispose()
            elif hasattr(instance, "close"):
                instance.close()

        self._singletons.clear()

    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered."""
        if service_type in self._services:
            return True
        if self._parent:
            return self._parent.is_registered(service_type)
        return False
