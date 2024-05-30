from typing import Any
from PIL import Image
import streamlit as st
from seedoo.streamlit.utils.decorators import type_matcher, column_name_matcher

@type_matcher(dict, st.json)
def process_dict(value: dict, row: Any = None) -> dict:
    value['processed'] = True
    return value

@type_matcher(list, st.write)
def process_list(value: list, row: Any = None) -> list:
    value.append('processed')
    return value
@type_matcher(str, st.write)
def process_str(value: list, row: Any = None) -> list:

    return value
@type_matcher(int, st.write)
def process_int(value: list, row: Any = None) -> list:

    return value

@column_name_matcher('list_column', st.write)
def create_image(value: Any, row: Any = None) -> Image.Image:

    return st.button(value)

