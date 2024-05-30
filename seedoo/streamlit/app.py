import streamlit as st
import seedoo.streamlit.event_server
from concurrent.futures import ThreadPoolExecutor
from seedoo.streamlit.utils.data_processor import process_dataframe , register_function
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import pandas as pd
from seedoo.streamlit.widgets import websocket_button ,modal
from functools import partial
@st.cache_resource(show_spinner=False)
def fetch_event_server():
    if 'pool' not in st.session_state:
        st.session_state['pool'] = ThreadPoolExecutor(12)

    return seedoo.streamlit.event_server.WebSocketServer.instance(), st.session_state['pool']





if __name__ == "__main__":
    import seedoo.streamlit.module.default_module

    package_root = "seedoo.streamlit.module"
    event_server,asynch_pool = fetch_event_server()
    if not event_server.initialized_contexts:
        for t in event_server.thread_pool_executor._threads:
            add_script_run_ctx(t)

        if 'pool' not in st.session_state:
            st.session_state['pool'] = ThreadPoolExecutor(32)
        for t in st.session_state['pool']._threads:
            add_script_run_ctx(t)

        event_server.initialized_contexts = True
    seedoo.streamlit.event_server.running_server = event_server
    event_server = seedoo.streamlit.event_server
    modal('modal_id','modal_id_test')
    def view_clusters_clicked_labeling(msg):
        event_server.running_server.send_data({'id': 'modal_id',
                                               'showModal': True,
                                               'event': 'similar'
                                               })


    def open_modal(value: str,row) -> str:
        callback = partial(view_clusters_clicked_labeling)
        # event_server.running_server.register_callback('test' + value, callback)
        return websocket_button('test' + value, 'View', callback)

    def input(value: str,row) -> str:
        def change_input_one():
            value_one = st.session_state['input' + value]
            event_server.running_server.send_data({'id': 'modal_id',
                                                   'showModal': True,
                                                   'event': 'similar',
                                                   'value_one':value_one
                                                   })

        return st.text_input('text',key='input'+value,on_change=change_input_one)
    register_function('modal_button', open_modal)
    register_function('input', input)
    data = {
        'modal_button': ['1', '2', '3'],
        'input': ['11', '22', '33'],
        'list_column_2': ['test', 'asd 4', 'asd'],
        'list_column_233': [1, 2, 12313123],

    }
    df = pd.DataFrame(data)

    process_dataframe(df)