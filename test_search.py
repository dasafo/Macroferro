#!/usr/bin/env python3
import requests
import json

def test_search():
    url = "http://localhost:8000/api/v1/products/search"
    payload = {"query_text": "amoladora", "top_k": 3}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search() 