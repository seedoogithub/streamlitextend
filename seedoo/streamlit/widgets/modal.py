import streamlit as st
import streamlit.components.v1 as components
import os

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
build_dir = os.path.join(parent_dir, "frontend/build/ModalComponent")

_component_func = components.declare_component(name="modal", path=build_dir)




def modal(id_unic, id_event_add ):
    # [Define] the custom component
    port = int(os.environ.get('SEEDOO_WEBSOCKET_EVENT_PORT', '9898'))
    config = {
        'filter': 0.01,
        'repulsion': 200000,
        'attraction': 10000,
        'layout': 'main'  # similarity main
    }
    string_id = id_unic
    component_value = _component_func(filter=config['filter'], layout=config['layout'], attraction=config['attraction'],
                                      repulsion=config['repulsion'], port=port,id=string_id , id_event_add=id_event_add)





