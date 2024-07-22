import streamlit as st
import seedoo.streamlit.event_server
from concurrent.futures import ThreadPoolExecutor
from seedoo.streamlit.utils.data_processor import process_dataframe, register_function
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import pandas as pd
from seedoo.streamlit.widgets import websocket_button, modal
from functools import partial
from streamlit_msal import Msal
from tokens_store import OurTokensStore
import uuid
import streamlit.components.v1 as components


with st.sidebar:
    auth_data = Msal.initialize_ui(
        client_id='02dba183-14e1-4c8f-837a-a0a1a75bf811',
        authority='https://login.microsoftonline.com/4cf3d54a-8a8b-4f92-95e6-51043c511c10',
        scopes=[], # Optional
        # Customize (Default values):
        connecting_label="Connecting",
        disconnected_label="Disconnected",
        sign_in_label="Sign in",
        sign_out_label="Sign out"
    )

if auth_data:
    st.session_state['LOGGED_IN'] = True
else:
    st.write("Authenticate to access protected content")
    st.session_state['LOGGED_IN'] = False
    st.stop()

account = auth_data["account"]
accessToken = auth_data['accessToken']

name = account["name"]


st.write(f"Hello {name}!")
st.write("Protected content available")

# Function to fetch the event server and thread pool
@st.cache_resource(show_spinner=False)
def initialize_tokens_store():
    tokens_store = OurTokensStore()
    return tokens_store
@st.cache_resource(show_spinner=False)
def fetch_event_server():
    if 'pool' not in st.session_state:
        st.session_state['pool'] = ThreadPoolExecutor(12)
    return seedoo.streamlit.event_server.WebSocketServer.instance(None), st.session_state['pool']


if __name__ == "__main__":
    import seedoo.streamlit.module.default_module

    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())
        components.html(f"""
                <script>
                    // Save session ID to local storage
                    localStorage.setItem('session_id', '{st.session_state['session_id']}');
                </script>
            """, height=0)
    event_server, asynch_pool = fetch_event_server()
    tokens_store = initialize_tokens_store()
    # Initialize contexts for the event server
    if not event_server.initialized_contexts:
        for t in event_server.thread_pool_executor._threads:
            add_script_run_ctx(t)

        if 'pool' not in st.session_state:
            st.session_state['pool'] = ThreadPoolExecutor(32)
        for t in st.session_state['pool']._threads:
            add_script_run_ctx(t)

        event_server.initialized_contexts = True
    tokens_store.add(accessToken)
    tokens_store.set_session_state(st.session_state['session_id'])
    if not event_server.tokens_store:
        event_server.tokens_store = tokens_store

    seedoo.streamlit.event_server.running_server = event_server
    event_server = seedoo.streamlit.event_server


    # Display a modal component
    modal('modal_id', 'modal_id_test')
    def change_input_session():
        value_one = st.session_state['input_session']
        tokens_store.set_session_data( 'input',value_one)
    st.text_input('text', key='input_session', on_change=change_input_session)
    st.write(tokens_store.get_session_data('input'))
    # Callback function for when the "View Clusters" button is clicked
    def view_clusters_clicked_labeling(msg):
        print(msg)
        event_server.running_server.send_data({
            'id': 'modal_id',
            'showModal': True,
            'event': 'similar',
        })


    # Function to create a WebSocket button that opens a modal
    def open_modal(value: str, row) -> str:
        callback = partial(view_clusters_clicked_labeling)
        return websocket_button('test' + value, 'View', callback)


    # Function to create a text input field with a callback
    def input(value: str, row) -> str:
        def change_input_one():
            value_one = st.session_state['input' + value]
            event_server.running_server.send_data({
                'id': 'modal_id',
                'showModal': True,
                'event': 'similar',
                'value_one': value_one,
            })

        return st.text_input('text', key='input' + value,label_visibility="collapsed", on_change=change_input_one)


    # Register custom functions for 'modal_button' and 'input' columns
    register_function('modal_button', open_modal)
    register_function('input', input)

    # Example data for the DataFrame
    data = {
        'modal_button': ['1aaa', '2sdasd', '3asd', 'asdad', 'bbbb', 'bbbrrrb1123'],
        'input': ['11', '22', '33', 'addddd', 'bsbbb', 'bbbrrrb12'],
        'list_column_2': ['test', 'asd 4', 'asd', 'aaaaa', 'baaabbb', 'bbbrrrb12'],
        'list_column_233': [1, 2, 12313123, 12331, 1233112, 12222],
        'additional_column_1': ['a', 'b', 'c', 'add', 'bbbrrrb', 'bbbrrrb1'],
        'additional_column_3': [3, 123, 3333, 1111, 1233133, 1233111]
    }

    # Create a DataFrame from the data
    df = pd.DataFrame(data)

    # Process the DataFrame to display it in Streamlit with registered functions
    process_dataframe(df, filter=True)
