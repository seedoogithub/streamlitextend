import streamlit as st
from datetime import datetime, timedelta
from seedoo.collections.capped_cahes import LRUCache


class OurTokensStore:
    def __init__(self):
        self.data = LRUCache(capacity = 5000, max_age = 86400) # max age is in seconds

    def add(self, token):
        if token not in self.data:
            self.data[token] = datetime.now()

    def expire(self, token):
        if token in self.data:
            del self.data[token]

    def check_valid(self, token):
        if token in self.data:
            return True
        return False

