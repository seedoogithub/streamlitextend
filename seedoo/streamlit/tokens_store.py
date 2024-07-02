import streamlit as st
from datetime import datetime, timedelta
# from seedoo.collections.capped_caches import LRUCache


class OurTokensStore:
    def __init__(self):
        # self.data = LRUCache(capacity = 1000, max_age = 600) # max age is in seconds
        self.data = {} # max age is in seconds

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
