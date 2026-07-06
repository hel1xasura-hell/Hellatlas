"""
Loads countries.json and cities.json and builds fast lookup structures:
  - a set of valid lowercase names per mode (for validity checking)
  - a mapping of lowercase name -> original display spelling
  - a mapping of first-letter -> list of names (handy for hints, not required)

If you want to expand the word lists, just add more entries to
data/countries.json / data/cities.json (plain JSON arrays of strings).
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clean(name):
    """Normalize a place name for comparison: lowercase, strip spaces/punctuation."""
    return "".join(ch for ch in name.lower() if ch.isalpha())


class GeoData:
    def __init__(self):
        countries = _load("countries.json")
        cities = _load("cities.json")

        # display maps: cleaned-key -> nice original string
        self.country_display = {_clean(c): c for c in countries}
        self.city_display = {_clean(c): c for c in cities}

        self.country_set = set(self.country_display.keys())
        self.city_set = set(self.city_display.keys())
        self.all_set = self.country_set | self.city_set
        self.all_display = {**self.country_display, **self.city_display}

    def valid_for_mode(self, mode, cleaned_name):
        from config import MODE_ALL, MODE_COUNTRY, MODE_CITY, MODE_WORD
        if mode == MODE_COUNTRY:
            return cleaned_name in self.country_set
        if mode == MODE_CITY:
            return cleaned_name in self.city_set
        if mode == MODE_ALL:
            return cleaned_name in self.all_set
        if mode == MODE_WORD:
            # Any alphabetic word is accepted; no geography dictionary check.
            return cleaned_name.isalpha() and len(cleaned_name) > 0
        return False

    def display_name(self, mode, cleaned_name, raw_fallback):
        if cleaned_name in self.all_display:
            return self.all_display[cleaned_name]
        return raw_fallback.strip().title()


geo = GeoData()
clean_name = _clean
