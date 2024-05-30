import streamlit as st
import streamlit.components.v1 as components
import os
import seedoo.streamlit.event_server

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
build_dir = os.path.join(parent_dir, "frontend/build/WebsocketButton")

_component_func_websocket_button = components.declare_component(name="WebsocketButton", path=build_dir)

def websocket_button(id, label, callback):
    port = int(os.environ.get('SEEDOO_WEBSOCKET_EVENT_PORT', '9898'))
    component_value = _component_func_websocket_button(id=id, label=label, port=port)
    seedoo.streamlit.event_server.running_server.register_callback(id, callback)