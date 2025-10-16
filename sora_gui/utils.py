"""Utility functions"""
import json

def aspect_of(size_str):
    w, h = size_str.split("x")
    return int(w), int(h)

def safe_json(resp):
    try:
        return resp.json()
    except:
        try:
            return {"text": resp.text}
        except:
            return {"error": "unreadable response"}

def pretty(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)
