from typing import Callable, Dict, Optional, Union
import logging

def type_matcher(column_type: type, component: Optional[Callable] = None) -> Callable:
    """
    Decorator for marking a function with a column type and a corresponding Streamlit component.

    Args:
        column_type (type): The data type of the column that the function should process.
        component (Optional[Callable]): The Streamlit component for displaying the function's output.

    Returns:
        Callable: The decorated function with added attributes _column_type and _component.
    """

    def decorator(func: Callable) -> Callable:


        def wrapper(*args, **kwargs):
            logger = logging.getLogger(__name__)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error processing function '{func.__name__}' for type '{column_type.__name__}': {e}")
                raise

        wrapper._column_type = column_type
        wrapper._component = component
        return wrapper

    return decorator


def column_name_matcher(column_name: str, component: Optional[Callable] = None) -> Callable:
    """
    Decorator for marking a function with a column name and a corresponding Streamlit component.

    Args:
        column_name (str): The name of the column that the function should process.
        component (Optional[Callable]): The Streamlit component for displaying the function's output.

    Returns:
        Callable: The decorated function with added attributes _column_name and _component.
    """

    def decorator(func: Callable) -> Callable:


        def wrapper(*args, **kwargs):
            logger = logging.getLogger(__name__)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error processing function '{func.__name__}' for column '{column_name}': {e}")
                raise

        wrapper._column_name = column_name
        wrapper._component = component
        return wrapper


    return decorator