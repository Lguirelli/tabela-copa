from fallback import FallbackEngine
from config import API_SOURCES

engine = FallbackEngine()

def extract_fixtures():
    return engine.fetch(API_SOURCES["fixtures"])