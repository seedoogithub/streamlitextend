# Streamlit Table with WebSocket and React Components

A project that showcases a table for working with Streamlit, featuring WebSocket integration and the ability to add functions to columns or data types. This project includes examples of custom React components that communicate via WebSocket, avoiding page reloads typically triggered by Streamlit's actions.

## Contents

- [About the Project](#about-the-project)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Contribution](#contribution)
- [License](#license)

## About the Project

This project provides a robust example of integrating WebSocket and React components with Streamlit. It demonstrates how to avoid page reloads by using WebSocket events and React, which allows for a smoother user experience.

Features:
- Table with the ability to add functions to columns or data types.
- Custom React components that communicate via WebSocket.
- Avoids page reloads by leveraging WebSocket and React integration.

## Installation

To run this project, ensure you have the following installed:
- Python
- npm

Follow these steps to set up the project:

1. Clone the repository:
    ```sh
    git clone https://github.com/seedoogithub/streamlitextend.git
    ```

2. Navigate to the project directory:
    ```sh
    cd streamlitextend
    ```

3. Install the Python package:
    ```sh
    pip install -e ./
    ```

4. Navigate to the frontend directory:
    ```sh
    cd seedoo/streamlit/frontend
    ```

5. Install npm dependencies:
    ```sh
    npm install
    ```

6. Build the npm project:
    ```sh
    npm run build
    ```

7. Navigate back to the Streamlit directory:
    ```sh
    cd ../../
    ```

8. Run the Streamlit application:
    ```sh
    streamlit run app.py
    ```
### Changing the WebSocket Port

To change the WebSocket port, use the environment variable:

```bash
SEEDOO_WEBSOCKET_EVENT_PORT=9897
```
If this environment variable is not set, the default port is 9897.
### Setting Up HTTPS with Nginx

This project includes a script to set up HTTPS with Nginx. The script is located at:
'streamlitextend\seedoo\streamlit\nginx_https.sh'
To start the project with Nginx using HTTPS, run this script.
## Usage

The project includes examples demonstrating how to work with the table and custom components.

### Example Code (app.py)

Below is a simple example of using a table and a modal that can be opened via WebSocket events.

```python
import streamlit as st
import seedoo.streamlit.event_server
from concurrent.futures import ThreadPoolExecutor
from seedoo.streamlit.utils.data_processor import process_dataframe, register_function
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
import pandas as pd
from seedoo.streamlit.widgets import websocket_button, modal
from functools import partial

# Function to fetch the event server and thread pool
@st.cache_resource(show_spinner=False)
def fetch_event_server():
    if 'pool' not in st.session_state:
        st.session_state['pool'] = ThreadPoolExecutor(12)
    return seedoo.streamlit.event_server.WebSocketServer.instance(), st.session_state['pool']

if __name__ == "__main__":
    import seedoo.streamlit.module.default_module

    event_server, asynch_pool = fetch_event_server()

    # Initialize contexts for the event server
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

    # Display a modal component
    modal('modal_id', 'modal_id_test')

    # Callback function for when the "View Clusters" button is clicked
    def view_clusters_clicked_labeling(msg):
        event_server.running_server.send_data({
            'id': 'modal_id',
            'showModal': True,
            'event': 'similar'
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
                'value_one': value_one
            })

        return st.text_input('text', key='input' + value, on_change=change_input_one)

    # Register custom functions for 'modal_button' and 'input' columns
    register_function('modal_button', open_modal)
    register_function('input', input)

    # Example data for the DataFrame
    data = {
        'modal_button': ['1aaa', '2sdasd', '3asd'],
        'input': ['11', '22', '33'],
        'list_column_2': ['test', 'asd 4', 'asd'],
        'list_column_233': [1, 2, 12313123],
        'additional_column_1': ['a', 'b', 'c'],
        'additional_column_3': [3, 123, 3333]
    }

    # Create a DataFrame from the data
    df = pd.DataFrame(data)

    # Process the DataFrame to display it in Streamlit with registered functions
    process_dataframe(df)
```
Also the possibility of using the load_functions_with_decorator function to scan a module in your project for functions for the table. There are two types of decorators: one for data types and one for column names.
Example module:
```paython
from typing import Any
from PIL import Image
import streamlit as st
from seedoo.streamlit.utils.decorators import type_matcher, column_name_matcher

@type_matcher(dict, st.json)
def process_dict(value: dict, row: Any = None) -> dict:
    value['processed'] = True
    return value
```
Before displaying the table, call the function:
```paython
from seedoo.streamlit.utils.data_processor import load_functions_with_decorator

load_functions_with_decorator('path.to.module.example_module')
```


## License

This project is licensed under the terms [Apache License 2.0](LICENSE).
