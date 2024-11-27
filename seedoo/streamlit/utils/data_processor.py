import os
import importlib
import inspect
import traceback

import pandas as pd
from typing import Callable, Dict, Optional, Union
import logging
import numpy as np
import streamlit as st
import pandas
import functools
import math

# Dictionary to store custom functions
custom_functions: Dict[type, Dict[str, Union[Callable, Optional[Callable]]]] = {}


def register_function(column_name: type, func: Callable, component: Optional[Callable] = None) -> None:
    global custom_functions
    """
    Registers a function and an optional component for a specific data type.

    Args:
        name (type): The data type to register the function for.
        func (Callable): The function to handle the data type.
        component (Optional[Callable]): An optional Streamlit component to display the processed data.
    """

    custom_functions[column_name] = {'function': func, 'component': component}


def load_functions_with_decorator(package_root="seedoo.streamlit.module.default_module") -> Dict[
    type, Dict[str, Union[Callable, Optional[Callable]]]]:
    global custom_functions
    """
    Scans all modules in the specified package for functions with the @type_matcher decorator.

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

    if file_path:
        for root, _, files in os.walk(file_path):
            for filename in files:
                if filename.endswith(".py"):
                    module = importlib.import_module(package_root)
                    for name, func in inspect.getmembers(module, inspect.isfunction):
                        if hasattr(func, '_column_type') or hasattr(func, '_column_name'):
                            key = func._column_type if hasattr(func, '_column_type') else func._column_name
                            custom_functions[key] = {'function': func, 'component': func._component}


load_functions_with_decorator()
print('load-----------')


def pick_page(current_page: Optional[int] = None, key: str = '') -> None:
    """
    Sets the current page in Streamlit session state.

    Args:
        current_page (Optional[int]): The current page number.
        key (str): The session state key for the current page.
    """
    st.session_state[key] = current_page


def calculate_total_pages(df: pd.DataFrame, page_size: int) -> int:
    total_rows = len(df)
    if page_size == 0 or 0 == len(df):
        return 10
    total_pages = math.ceil(total_rows / page_size)
    return total_pages


def default_filter_callback(query: str, page_size: int, current_page: int, df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters a DataFrame based on a query and returns a paginated subset.

    Args:
        query (str): The query string to filter the DataFrame.
        page_size (int): The number of rows per page.
        current_page (int): The current page number.
        df (pd.DataFrame): The DataFrame to filter.

    Returns:
        pd.DataFrame: The filtered and paginated DataFrame.
    """
    start_idx = current_page * page_size
    end_idx = start_idx + page_size
    total = calculate_total_pages(df, page_size)
    if query:
        filtered_df = df.query(query)
        return [filtered_df.iloc[start_idx:end_idx], total]
    else:
        return [df.iloc[start_idx:end_idx], total]


def go_to_first_page(key):
    key_current_page = key + 'current_page'
    if key_current_page in st.session_state:
        st.session_state[key_current_page] = 0
def render_pagination(total_pages=None, has_more_data=True,
                              key_current_page: str = "current_page"):
            """
            Render a dynamic pagination component in Streamlit.

            Args:
                current_page (int): Currently active page.
                total_pages (int, optional): Total number of pages. Defaults to None for dynamic pagination.
                has_more_data (bool): Indicator if there's more data to paginate through. Defaults to True.
                key_current_page (str): Session state key to track the current page. Defaults to "current_page".
            """

            # Check if total_pages is provided or not (dynamic mode)
            dynamic_mode = total_pages is None

            # Initialize current page if not present in session state
            if key_current_page not in st.session_state:
                st.session_state[key_current_page] = 0

            # Get the current page from session state
            current_page = st.session_state[key_current_page]

            # Render dynamic pagination when total_pages is None
            if dynamic_mode:
                # Center the buttons and page info
                col_space1, col_prev, col_info, col_next, col_space2 = st.columns([1, 2, 2, 2, 1])

                with col_info:
                    first, second, third = st.columns([2,2,2])
                    with first:
                        if current_page > 0:
                            st.button("Previous",use_container_width=True,
                                      on_click=functools.partial(pick_page, current_page - 1, key_current_page))
                        else:
                            st.button("Previous", disabled=True , use_container_width=True)
                    with second:
                        st.write(
                            f"<div style='text-align: center;font-size: 17px;border: 1px solid rgb(237, 111, 19);border-color: rgb(255, 75, 75);color: rgb(255, 75, 75);padding: 0.25rem 0.75rem;border-radius: 0.5rem;min-height: 38.4px;'>{current_page + 1}</div>",
                            use_container_width=True, unsafe_allow_html=True)
                    with third:
                        st.button("Next",use_container_width=True, on_click=functools.partial(pick_page, current_page + 1, key_current_page),
                                  disabled=not has_more_data)
            else:
                # Static mode: use page range logic
                if total_pages <= 1:
                    return  # No need for pagination if there's only one page

                # Calculate page range based on the current page position
                page_range = [0]

                if current_page <= 3:
                    page_range.extend(range(1, min(total_pages - 1, 6)))
                elif current_page >= total_pages - 4:
                    page_range.extend(range(max(1, total_pages - 6), total_pages - 1))
                else:
                    page_range.extend(range(current_page - 2, current_page + 3))

                # Ensure first and last pages are included in the range
                if total_pages > 1:
                    page_range.append(total_pages - 1)

                # Remove duplicates and sort the range
                page_range = sorted(set(page_range))

                # Add "..." where needed
                if len(page_range) > 2 and page_range[1] != 1:
                    page_range.insert(1, "...")  # Add "..." after the first page
                if len(page_range) > 2 and page_range[-2] != page_range[-1] - 1:
                    page_range.insert(-1, "...")  # Add "..." before the last page

                # Center the buttons and page info
                alignment_cols = len(page_range)

                # Create columns for centering the pagination buttons
                if alignment_cols < 7:
                    cols = st.columns(7)
                    start_index = (7 - alignment_cols) // 2  # Calculate the start index for centering the buttons
                else:
                    cols = st.columns(alignment_cols)
                    start_index = 0  # No offset needed if we have enough columns

                # Render pagination buttons with adjusted centering
                for index, page_num in enumerate(page_range):
                    with cols[start_index + index]:  # Adjust index for centering
                        if page_num == "...":
                            st.write("<div style='text-align: center; font-size: 24px;'>...</div>",use_container_width=True,unsafe_allow_html=True)  # Static placeholder for "..."
                        elif page_num == current_page:
                            st.write(f"<div style='text-align: center;font-size: 17px;border: 1px solid rgb(237, 111, 19);border-color: rgb(255, 75, 75);color: rgb(255, 75, 75);padding: 0.25rem 0.75rem;border-radius: 0.5rem;min-height: 38.4px;'>{page_num + 1}</div>",
                                     use_container_width=True, unsafe_allow_html=True)
                        else:
                            st.button(f"{page_num + 1}",use_container_width=True, key=f"page_{page_num}_clicked",
                                      on_click=functools.partial(pick_page, page_num, key_current_page))

def process_dataframe(
        df: pd.DataFrame,
        columns_length: Optional[list] = None,
        filter: bool = None,
        filter_callback: Optional[Callable[[str, int, int, pd.DataFrame], pd.DataFrame]] = default_filter_callback,
        key: str = "process_dataframe_key",
        page_size_num: int = 5, strict=False, disabled: bool = False) -> None:
    global custom_functions
    """
    Processes each value in the DataFrame, passing it to a function based on the column's data type.

    Args:
        df (pd.DataFrame): The DataFrame to process.
        columns_length (Optional[list]): List of column lengths.
        filter (bool): Whether to apply filtering.
        filter_callback (Optional[Callable[[str, int, int, pd.DataFrame], pd.DataFrame]]): Callback for filtering the DataFrame.
        key (str): Session state key for the DataFrame.
        page_size_num (int): Number of rows per page.

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

        def change_input_one():
            go_to_first_page(key)

        query = st.text_input("Enter your query (e.g., id == 54):", key=key + 'query', on_change=change_input_one)
        try:
            result = filter_callback(query, PAGE_SIZE, current_page, df)
            if len(result) == 3:
                df, total_pages, stop_page = result
            else:
                df, total_pages = result
                stop_page = True
        except Exception as e:
            st.error(f"Query failed: {traceback.format_exc()}")
            raise

    col_names = [c for c in df.columns.values if '_widget' not in c]
    handled_rows = 0

    def decide_length(c: Union[pandas.core.frame.DataFrame, str, float, int, np.int64, np.float32]) -> float:
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
                            if column in custom_functions:
                                func = custom_functions[column]['function']
                                component = custom_functions[column]['component']
                                output = func(value, row, disabled)
                                if component:
                                    component(output)
                                elif strict:
                                    raise RuntimeError(f"Output for {value} in column {column}: {output}")

                            elif column_type in custom_functions:
                                func = custom_functions[column_type]['function']
                                component = custom_functions[column_type]['component']
                                output = func(value, row, disabled)
                                if component:
                                    component(output)
                                elif strict:
                                    raise RuntimeError(f"Output for {value} in column {column}: {output}")
                            else:
                                message = f"No registered function for processing type '{column_type.__name__}' in column '{column}'."
                                st.write(message)
                                logger.warning(message)

        columns = st.columns(10)
        if filter:
            print(len(df))
            render_pagination(total_pages,stop_page, key_current_page)
