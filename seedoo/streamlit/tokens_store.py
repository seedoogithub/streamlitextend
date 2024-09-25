import streamlit as st
from datetime import datetime, timedelta
from seedoo.collections.capped_cahes import LRUCache


class OurTokensStore:
    """
       A class to manage tokens and session states with expiration support using LRU cache.

       This class provides methods to add, retrieve, and manage tokens and session states
       with a Least Recently Used (LRU) cache that has a specified maximum age for entries.

       Attributes:
           data (LRUCache): An LRU cache to store tokens with a capacity of 5000 entries and a max age of 86400 seconds (1 day).
           session_state (LRUCache): An LRU cache to store session states with a capacity of 5000 entries and a max age of 86400 seconds (1 day).

       Methods:
           add(token):
               Adds a token to the data cache if it is not already present.

           get_session_state(session_id):
               Retrieves the session state for a given session ID if it exists in the session_state cache.

           set_session_state(session_id):
               Initializes a session state for a given session ID if it does not already exist.

           set_session_data(session_id, key, value):
               Sets a key-value pair in the session state for a given session ID.

           get_session_data(session_id, key):
               Retrieves the value for a given key in the session state for a given session ID.

           expire(token):
               Removes a token from the data cache.

           check_valid(token):
               Checks if a token is present in the data cache.
       """
    def __init__(self):
        self.data = LRUCache(capacity=5000, max_age=86400)  # max age is in seconds
        self.session_state = LRUCache(capacity=5000, max_age=86400)  # max age is in seconds
        self.user_stor = LRUCache(capacity=5000, max_age=86400)  # max age is in seconds

    def add(self, token):
        if token not in self.data:
            self.data[token] = datetime.now()

    def get_user_state(self, user_id):
        if user_id and user_id in self.user_stor:
            return self.user_stor[user_id]
        else:
            return None

    def set_user_state(self, user_id):
        if user_id not in self.user_stor:
            self.user_stor[user_id] = {}

    def set_user_data(self, user_id, key, value):
        local_state = self.get_user_state(user_id)
        if local_state is None:
            local_state = {}
            self.user_stor[user_id] = local_state
        local_state[key] = value
        self.user_stor[user_id] = local_state

    def get_user_data(self, user_id, key):
        user_state = self.get_user_state(user_id)
        if user_state is not None:
            return user_state.get(key)
        return None

    def get_session_state(self, session_id):
        if session_id and session_id in self.session_state:
            return self.session_state[session_id]
        else:
            return None

    def set_session_state(self, session_id):
        if session_id not in self.session_state:
            self.session_state[session_id] = {}

    def set_session_data(self, session_id, key, value):
        session_state = self.get_session_state(session_id)
        if session_state is None:
            session_state = {}
            self.session_state[session_id] = session_state
        session_state[key] = value
        self.session_state[session_id] = session_state

    def get_session_data(self, session_id, key):
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
