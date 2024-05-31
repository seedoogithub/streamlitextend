import os
import importlib
import inspect
import pandas as pd
from typing import Callable, Dict, Optional, Union
import logging
import numpy as np
import streamlit as st
import pandas
import functools

custom_functions = {}


def register_function(name: type, func: Callable, component: Optional[Callable] = None) -> None:
    custom_functions[name] = {'function': func, 'component': component}


def load_functions_with_decorator() -> Dict[type, Dict[str, Union[Callable, Optional[Callable]]]]:
    package_root = "seedoo.streamlit.module.default_module"
    """
    Scans all modules in the specified package for functions with the @type_matcher decorator.

    Args:
        package_root (str): The root package to scan for modules and functions.

    Returns:
        Dict[type, Dict[str, Union[Callable, Optional[Callable]]]]: A dictionary mapping column data types to corresponding functions and Streamlit components.

    Raises:
        ValueError: If the specified root package is invalid.
    """
    file_path = None
    try:
        file_path = os.path.dirname(importlib.import_module(package_root).__file__)
    except ModuleNotFoundError:
        raise ValueError(f"The package '{package_root}' is invalid.")
    functions = {}

    if file_path:
        for root, _, files in os.walk(file_path):
            for filename in files:
                if filename.endswith(".py"):
                    module = importlib.import_module(package_root)
                    for name, func in inspect.getmembers(module, inspect.isfunction):
                        if hasattr(func, '_column_type') or hasattr(func, '_column_name'):
                            key = func._column_type if hasattr(func, '_column_type') else func._column_name
                            functions[key] = {'function': func, 'component': func._component}
        return functions


def pick_page(current_page=None, key=''):
    st.session_state[key] = current_page


def default_filter_callback(query: str, page_size: int, current_page: int, df: pd.DataFrame) -> pd.DataFrame:
    start_idx = current_page * page_size
    end_idx = start_idx + page_size
    if query:
        filtered_df = df.query(query)
        return filtered_df.iloc[start_idx:end_idx]
    else:
        return df.iloc[start_idx:end_idx]


def default_filter_callback(query: str, page_size: int, current_page: int, df) -> pd.DataFrame:
    start_idx = current_page * page_size
    end_idx = start_idx + page_size
    if query:
        filtered_df = df.query(query)
        return filtered_df.iloc[start_idx:end_idx]
    else:
        return df.iloc[start_idx:end_idx]


def process_dataframe(df: pd.DataFrame, columns_length: Optional[list] = None,
                      filter: bool = None,
                      filter_callback: Optional[Callable[[str, int, int], pd.DataFrame]] = default_filter_callback,
                      key: str = "process_dataframe_key", page_size_num: int = 5) -> None:
    """
    Processes each value in the DataFrame, passing it to a function based on the column's data type.

    Args:
        df (pd.DataFrame): The DataFrame to process.
        package_root (str): The root package to scan for functions with the @type_matcher decorator.
        strict (bool): If True, raises an exception if there is no corresponding function for a column's data type.

    Returns:
        None
    """

    logger = logging.getLogger(__name__)
    key_page_size = key + 'PAGE_SIZE'
    key_current_page = key + 'current_page'
    if key_page_size not in st.session_state:
        st.session_state[key_page_size] = page_size_num
        PAGE_SIZE = page_size_num
    else:
        PAGE_SIZE = st.session_state[key_page_size]
    current_page = st.session_state.get(key_current_page, 0)

    if filter:
        query = st.text_input("Enter your query (e.g., id == 54):", key=key + 'query')
        try:
            df = filter_callback(query, PAGE_SIZE, current_page, df)
        except Exception as e:
            st.error(f"Query failed: {e}")
            return

    functions = load_functions_with_decorator()
    functions.update(custom_functions)
    col_names = [c for c in df.columns.values if '_widget' not in c]
    handled_rows = 0

    def decide_length(c):
        if isinstance(c, (pandas.core.frame.DataFrame,)):
            return 2
        elif isinstance(c, (str,)):
            return 0.1
        elif isinstance(c, (float, int, np.int64, np.float32)):
            return 0.1
        else:
            return 1

    lengths = []
    for col in col_names:
        lengths.append(np.rint(np.mean([decide_length(c) for c in df[col].values])))
    lengths = np.array(lengths)
    lengths = np.maximum(lengths, 1)
    lengths[np.isnan(lengths)] = 1
    lengths = lengths.astype('int').tolist()
    col_names = [c for c in df.columns.values if '_widget' not in c]
    if columns_length:
        lengths = columns_length

    columns = st.columns(lengths, gap='small')
    with st.container():
        for i, column_name in enumerate(col_names):
            column = columns[i]
            with column:
                if isinstance(column_name, (int, float)) or len(column_name) == 1:
                    st.text('')
                else:
                    st.text(column_name)
        with st.container():
            for _, row in df.iterrows():
                with st.container():
                    columns = st.columns(lengths, gap='small')
                    for i, column in enumerate(col_names):
                        value = row[column]
                        column_type = type(value)
                        with columns[i]:
                            if column in functions:
                                func = functions[column]['function']
                                component = functions[column]['component']
                                output = func(value, row)
                                if component:
                                    component(output)
                                else:
                                    print(f"Output for {value} in column {column}: {output}")
                            elif column_type in functions:
                                func = functions[column_type]['function']
                                component = functions[column_type]['component']
                                output = func(value, row)
                                if component:
                                    component(output)
                                else:
                                    print(f"Output for {value} in column {column}: {output}")
                            else:

                                message = f"No registered function for processing type '{column_type.__name__}' in column '{column}'."
                                st.write(message)
                                logger.warning(message)
        columns = st.columns(10)

        current_selected_page = st.session_state.get(key_current_page, 0)
        for page_number, c in enumerate(columns):
            button_key = f'page_{page_number}_clicked'
            with c:
                if page_number == current_selected_page:
                    st.markdown(
                        """
                        <style>
                        .element-container:has(style){
                            display: none;
                        }
                        #button-after {
                            display: none;
                        }
                        .element-container:has(#button-after) {
                            display: none;
                        }
                        .element-container:has(#button-after) + div button {
                            background-color: orange;
                            }
                        </style>
                        """,
                        unsafe_allow_html=True,
                    )

                    st.button(f'** {page_number + 1}', key=button_key,
                              on_click=functools.partial(pick_page, page_number, key_current_page))
                    st.markdown('<span id="button-after"></span>', unsafe_allow_html=True)
                else:
                    st.button(f'{page_number + 1}', key=button_key,
                              on_click=functools.partial(pick_page, page_number, key_current_page))
