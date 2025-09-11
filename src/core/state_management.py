"""
Покращений state management з Redux-подібним паттерном
"""

import asyncio
import logging
from typing import Any, Dict, List, Callable, Optional, Union, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json
import copy

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ActionType(Enum):
    """Типи дій"""
    # Profile actions
    SET_PROFILE = "SET_PROFILE"
    CLEAR_PROFILE = "CLEAR_PROFILE"
    UPDATE_PROFILE = "UPDATE_PROFILE"
    
    # Language actions
    SET_LANGUAGE = "SET_LANGUAGE"
    
    # Transaction actions
    ADD_TRANSACTION = "ADD_TRANSACTION"
    UPDATE_TRANSACTION = "UPDATE_TRANSACTION"
    DELETE_TRANSACTION = "DELETE_TRANSACTION"
    SET_TRANSACTIONS = "SET_TRANSACTIONS"
    
    # Property actions
    ADD_PROPERTY = "ADD_PROPERTY"
    UPDATE_PROPERTY = "UPDATE_PROPERTY"
    DELETE_PROPERTY = "DELETE_PROPERTY"
    SELL_PROPERTY = "SELL_PROPERTY"
    SET_PROPERTIES = "SET_PROPERTIES"
    
    # UI actions
    SET_LOADING = "SET_LOADING"
    SET_ERROR = "SET_ERROR"
    CLEAR_ERROR = "CLEAR_ERROR"
    SET_VIEW = "SET_VIEW"

@dataclass
class Action:
    """Дія для state management"""
    type: ActionType
    payload: Any = None
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AppState:
    """Глобальний стан додатку"""
    # Profile state
    current_profile: Optional[Dict[str, Any]] = None
    profiles: List[Dict[str, Any]] = field(default_factory=list)
    
    # Language state
    current_language: str = "uk"
    
    # Transaction state
    transactions: List[Dict[str, Any]] = field(default_factory=list)
    transactions_loading: bool = False
    transactions_error: Optional[str] = None
    
    # Property state
    properties: List[Dict[str, Any]] = field(default_factory=list)
    sold_properties: List[Dict[str, Any]] = field(default_factory=list)
    properties_loading: bool = False
    properties_error: Optional[str] = None
    
    # UI state
    current_view: str = "profiles"
    loading: Dict[str, bool] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    
    # Analytics state
    analytics_data: Dict[str, Any] = field(default_factory=dict)
    analytics_loading: bool = False

class Reducer(ABC):
    """Базовий клас для reducer"""
    
    @abstractmethod
    def reduce(self, state: AppState, action: Action) -> AppState:
        """Обробляє дію та повертає новий стан"""
        pass

class ProfileReducer(Reducer):
    """Reducer для профілів"""
    
    def reduce(self, state: AppState, action: Action) -> AppState:
        new_state = copy.deepcopy(state)
        
        if action.type == ActionType.SET_PROFILE:
            new_state.current_profile = action.payload
        elif action.type == ActionType.CLEAR_PROFILE:
            new_state.current_profile = None
        elif action.type == ActionType.UPDATE_PROFILE:
            if new_state.current_profile and action.payload:
                new_state.current_profile.update(action.payload)
        
        return new_state

class LanguageReducer(Reducer):
    """Reducer для мови"""
    
    def reduce(self, state: AppState, action: Action) -> AppState:
        new_state = copy.deepcopy(state)
        
        if action.type == ActionType.SET_LANGUAGE:
            new_state.current_language = action.payload
        
        return new_state

class TransactionReducer(Reducer):
    """Reducer для транзакцій"""
    
    def reduce(self, state: AppState, action: Action) -> AppState:
        new_state = copy.deepcopy(state)
        
        if action.type == ActionType.ADD_TRANSACTION:
            new_state.transactions.insert(0, action.payload)
        elif action.type == ActionType.UPDATE_TRANSACTION:
            transaction_id = action.payload.get('id')
            for i, transaction in enumerate(new_state.transactions):
                if transaction.get('id') == transaction_id:
                    new_state.transactions[i] = action.payload
                    break
        elif action.type == ActionType.DELETE_TRANSACTION:
            transaction_id = action.payload
            new_state.transactions = [
                t for t in new_state.transactions 
                if t.get('id') != transaction_id
            ]
        elif action.type == ActionType.SET_TRANSACTIONS:
            new_state.transactions = action.payload
        elif action.type == ActionType.SET_LOADING and action.meta.get('key') == 'transactions':
            new_state.transactions_loading = action.payload
        elif action.type == ActionType.SET_ERROR and action.meta.get('key') == 'transactions':
            new_state.transactions_error = action.payload
        elif action.type == ActionType.CLEAR_ERROR and action.meta.get('key') == 'transactions':
            new_state.transactions_error = None
        
        return new_state

class PropertyReducer(Reducer):
    """Reducer для майна"""
    
    def reduce(self, state: AppState, action: Action) -> AppState:
        new_state = copy.deepcopy(state)
        
        if action.type == ActionType.ADD_PROPERTY:
            new_state.properties.append(action.payload)
        elif action.type == ActionType.UPDATE_PROPERTY:
            property_id = action.payload.get('id')
            for i, prop in enumerate(new_state.properties):
                if prop.get('id') == property_id:
                    new_state.properties[i] = action.payload
                    break
        elif action.type == ActionType.DELETE_PROPERTY:
            property_id = action.payload
            new_state.properties = [
                p for p in new_state.properties 
                if p.get('id') != property_id
            ]
        elif action.type == ActionType.SELL_PROPERTY:
            property_id = action.payload.get('id')
            for i, prop in enumerate(new_state.properties):
                if prop.get('id') == property_id:
                    sold_property = new_state.properties.pop(i)
                    sold_property.update(action.payload)
                    new_state.sold_properties.append(sold_property)
                    break
        elif action.type == ActionType.SET_PROPERTIES:
            new_state.properties = action.payload
        elif action.type == ActionType.SET_LOADING and action.meta.get('key') == 'properties':
            new_state.properties_loading = action.payload
        elif action.type == ActionType.SET_ERROR and action.meta.get('key') == 'properties':
            new_state.properties_error = action.payload
        elif action.type == ActionType.CLEAR_ERROR and action.meta.get('key') == 'properties':
            new_state.properties_error = None
        
        return new_state

class UIReducer(Reducer):
    """Reducer для UI стану"""
    
    def reduce(self, state: AppState, action: Action) -> AppState:
        new_state = copy.deepcopy(state)
        
        if action.type == ActionType.SET_VIEW:
            new_state.current_view = action.payload
        elif action.type == ActionType.SET_LOADING:
            key = action.meta.get('key', 'default')
            new_state.loading[key] = action.payload
        elif action.type == ActionType.SET_ERROR:
            key = action.meta.get('key', 'default')
            new_state.errors[key] = action.payload
        elif action.type == ActionType.CLEAR_ERROR:
            key = action.meta.get('key', 'default')
            if key in new_state.errors:
                del new_state.errors[key]
        
        return new_state

class Store:
    """Головний store для state management"""
    
    def __init__(self, initial_state: Optional[AppState] = None):
        self._state = initial_state or AppState()
        self._reducers: List[Reducer] = []
        self._subscribers: List[Callable[[AppState, Action], None]] = []
        self._middleware: List[Callable[[Action], Action]] = []
        self._lock = asyncio.Lock()
        
        # Додаємо стандартні reducers
        self.add_reducer(ProfileReducer())
        self.add_reducer(LanguageReducer())
        self.add_reducer(TransactionReducer())
        self.add_reducer(PropertyReducer())
        self.add_reducer(UIReducer())
    
    def add_reducer(self, reducer: Reducer):
        """Додає reducer"""
        self._reducers.append(reducer)
    
    def add_middleware(self, middleware: Callable[[Action], Action]):
        """Додає middleware"""
        self._middleware.append(middleware)
    
    def subscribe(self, callback: Callable[[AppState, Action], None]):
        """Підписується на зміни стану"""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[AppState, Action], None]):
        """Відписується від змін стану"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def dispatch(self, action: Action):
        """Відправляє дію"""
        async with self._lock:
            # Застосовуємо middleware
            for middleware in self._middleware:
                action = middleware(action)
            
            # Зберігаємо попередній стан
            previous_state = copy.deepcopy(self._state)
            
            # Застосовуємо reducers
            for reducer in self._reducers:
                self._state = reducer.reduce(self._state, action)
            
            # Сповіщаємо підписників
            for callback in self._subscribers:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self._state, action)
                    else:
                        callback(self._state, action)
                except Exception as e:
                    logger.error(f"Error in state subscriber: {e}")
    
    def get_state(self) -> AppState:
        """Отримує поточний стан"""
        return copy.deepcopy(self._state)
    
    def get_state_slice(self, selector: Callable[[AppState], T]) -> T:
        """Отримує частину стану"""
        return selector(self._state)

# Action creators
class ActionCreators:
    """Створювачі дій"""
    
    @staticmethod
    def set_profile(profile: Dict[str, Any]) -> Action:
        return Action(ActionType.SET_PROFILE, profile)
    
    @staticmethod
    def clear_profile() -> Action:
        return Action(ActionType.CLEAR_PROFILE)
    
    @staticmethod
    def update_profile(updates: Dict[str, Any]) -> Action:
        return Action(ActionType.UPDATE_PROFILE, updates)
    
    @staticmethod
    def set_language(language: str) -> Action:
        return Action(ActionType.SET_LANGUAGE, language)
    
    @staticmethod
    def add_transaction(transaction: Dict[str, Any]) -> Action:
        return Action(ActionType.ADD_TRANSACTION, transaction)
    
    @staticmethod
    def update_transaction(transaction: Dict[str, Any]) -> Action:
        return Action(ActionType.UPDATE_TRANSACTION, transaction)
    
    @staticmethod
    def delete_transaction(transaction_id: int) -> Action:
        return Action(ActionType.DELETE_TRANSACTION, transaction_id)
    
    @staticmethod
    def set_transactions(transactions: List[Dict[str, Any]]) -> Action:
        return Action(ActionType.SET_TRANSACTIONS, transactions)
    
    @staticmethod
    def add_property(property_data: Dict[str, Any]) -> Action:
        return Action(ActionType.ADD_PROPERTY, property_data)
    
    @staticmethod
    def update_property(property_data: Dict[str, Any]) -> Action:
        return Action(ActionType.UPDATE_PROPERTY, property_data)
    
    @staticmethod
    def delete_property(property_id: int) -> Action:
        return Action(ActionType.DELETE_PROPERTY, property_id)
    
    @staticmethod
    def sell_property(property_data: Dict[str, Any]) -> Action:
        return Action(ActionType.SELL_PROPERTY, property_data)
    
    @staticmethod
    def set_properties(properties: List[Dict[str, Any]]) -> Action:
        return Action(ActionType.SET_PROPERTIES, properties)
    
    @staticmethod
    def set_loading(key: str, loading: bool) -> Action:
        return Action(ActionType.SET_LOADING, loading, {'key': key})
    
    @staticmethod
    def set_error(key: str, error: str) -> Action:
        return Action(ActionType.SET_ERROR, error, {'key': key})
    
    @staticmethod
    def clear_error(key: str) -> Action:
        return Action(ActionType.CLEAR_ERROR, None, {'key': key})
    
    @staticmethod
    def set_view(view: str) -> Action:
        return Action(ActionType.SET_VIEW, view)

# Middleware
class LoggingMiddleware:
    """Middleware для логування дій"""
    
    def __call__(self, action: Action) -> Action:
        logger.debug(f"Action dispatched: {action.type.value} with payload: {action.payload}")
        return action

class PersistenceMiddleware:
    """Middleware для збереження стану"""
    
    def __init__(self, storage_key: str = "app_state"):
        self.storage_key = storage_key
    
    def __call__(self, action: Action) -> Action:
        # Тут можна додати логіку збереження стану
        return action

# Глобальний store
_store: Optional[Store] = None

def get_store() -> Store:
    """Отримує глобальний store"""
    global _store
    if _store is None:
        _store = Store()
        # Додаємо middleware
        _store.add_middleware(LoggingMiddleware())
        _store.add_middleware(PersistenceMiddleware())
    return _store

def dispatch(action: Action):
    """Відправляє дію в глобальний store"""
    store = get_store()
    asyncio.create_task(store.dispatch(action))

def get_state() -> AppState:
    """Отримує поточний стан"""
    return get_store().get_state()

def subscribe(callback: Callable[[AppState, Action], None]):
    """Підписується на зміни стану"""
    get_store().subscribe(callback)

def unsubscribe(callback: Callable[[AppState, Action], None]):
    """Відписується від змін стану"""
    get_store().unsubscribe(callback)
