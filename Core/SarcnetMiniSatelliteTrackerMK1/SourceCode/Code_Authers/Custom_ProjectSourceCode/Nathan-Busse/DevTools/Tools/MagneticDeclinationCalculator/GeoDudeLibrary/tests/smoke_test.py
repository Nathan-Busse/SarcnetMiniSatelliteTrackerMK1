def test_import():
    from GeoDude import GeoDude
    from GeoDude.reverse_geocode import GeocoderResultBaseModel

    gz = GeoDude()
    coordinates = [(-74.0060, 40.7128)]
    for data in gz.search(coordinates):
        assert isinstance(data, GeocoderResultBaseModel)
