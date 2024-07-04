import streamlit as st
test = st.session_state.get('LOGGED_IN',False)

st.write('test page')
if not test:
    st.switch_page("app.py")
