import geodata
from api.city import serializers
from rest_framework.generics import ListAPIView
from rest_framework.generics import RetrieveAPIView


class CityList(ListAPIView):
    """
    Returns a list of IATI Cities stored in OIPA.

    ## Result details

    Each result item contains short information about city including URI
    to city details.

    URI is constructed as follows: `/api/cities/{city_id}`

    """
    queryset = geodata.models.City.objects.all()
    serializer_class = serializers.CitySerializer
    fields = ('url', 'id', 'name')


class CityDetail(RetrieveAPIView):
    """
    Returns detailed information about City.

    ## URI Format

    ```
    /api/cities/{city_id}
    ```

    ### URI Parameters

    - `city_id`: Numerical ID of desired City

    ## Request parameters

    - `fields` (*optional*): List of fields to display

    """
    queryset = geodata.models.City.objects.all()
    serializer_class = serializers.CitySerializer
