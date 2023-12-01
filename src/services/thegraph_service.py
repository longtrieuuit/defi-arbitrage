from requests import request, Response

from typing import Optional

class TheGraphService():
    def __init__(self) -> None:
        pass

    def query(self, url: str, query: str, api_key: Optional[str] = None):
        # TODO Handle pagination
        response: Response = request(
            method = "POST",
            url = url,
            json = {
                "query": query
            },
            headers = {
                "X-API-KEY": api_key
            } if api_key else None
        )

        if response.status_code != 200:
            raise Exception(f"{response.status_code}: {response.reason}")

        return response.json()
        