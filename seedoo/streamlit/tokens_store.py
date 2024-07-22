import streamlit as st
from datetime import datetime, timedelta
from seedoo.collections.capped_cahes import LRUCache


class OurTokensStore:
    def __init__(self):
        self.data = LRUCache(capacity=5000, max_age=86400)  # max age is in seconds
        self.session_state = LRUCache(capacity=5000, max_age=86400)  # max age is in seconds

    def add(self, token):
        if token not in self.data:
            self.data[token] = datetime.now()

    def get_session_state(self, session_id):
        if session_id and session_id in self.session_state:
            return self.session_state[session_id]
        else:
            return None

    def set_session_state(self, session_id):
        if session_id not in self.session_state:
            self.session_state[session_id] = {}

    def set_session_data(self, key, value):
        session_id = st.session_state['session_id']
        session_state = self.get_session_state(session_id)
        if session_state is None:
            session_state = {}
            self.session_state[session_id] = session_state
        session_state[key] = value
        self.session_state[session_id] = session_state

    def get_session_data(self, key):
        session_id = st.session_state['session_id']
        session_state = self.get_session_state(session_id)
        if session_state is not None:
            return session_state.get(key)
        return None

    def expire(self, token):
        if token in self.data:
            del self.data[token]

    def check_valid(self, token):
        if token in self.data:
            return True
        return False
