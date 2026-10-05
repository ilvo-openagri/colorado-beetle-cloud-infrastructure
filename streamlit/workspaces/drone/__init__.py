import requests


class IlvoDrone:
    """
    IlvoDrone is a class that provides an interface to interact with a drone system
    via HTTP requests. It allows checking the drone's status, starting the drone,
    and stopping the drone.
    """

    def __init__(self, url: str, port: int):
        self._url = url
        self._port = port

    def get_status(self) -> dict:
        """
        Get the status of the drone.
        Returns:
            dict: A dictionary containing the status of the drone.
        """
        response = requests.get(f"http://{self._url}:{self._port}/status")
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def start(self, project_id: int, flight_id: int, ads: str = "cloud") -> bool:
        """
        Start the drone.

        Args:
            project_id (int): The ID of the project to start the drone for.
            flight_id (int): The ID of the flight to start.
            ads (str): The ADS selection (cloud/edge)

        Returns:
            bool: True if the drone started successfully, False otherwise.
        """
        response = requests.post(
            f"http://{self._url}:{self._port}/start",
            json={
                "project_id": project_id,
                "flight_id": flight_id,
                "ads": ads,
            },
        )
        return response.status_code == 200

    def stop(self) -> bool:
        """
        Stop the drone.

        Returns:
            bool: True if the drone stopped successfully, False otherwise.
        """
        response = requests.post(f"http://{self._url}:{self._port}/stop")
        return response.status_code == 200
