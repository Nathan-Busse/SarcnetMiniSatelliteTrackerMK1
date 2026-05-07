def test_import():
    from geodude import geodude
    from geodude.reverse_geocode import GeocoderResultBaseModel

    gz = geodude()
    coordinates = [(-74.0060, 40.7128)]
    for data in gz.search(coordinates):
        assert isinstance(data, GeocoderResultBaseModel)
